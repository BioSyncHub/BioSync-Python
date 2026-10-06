import sys
import ctypes
import os
import json
import configparser
import re
import queue
import threading
import tkinter as tk
from pathlib import Path
import win32api

# Importa as classes modulares e universais criadas no ecossistema BioSync
from core.capture import ScreenCapture
from core.inference import InferenceEngine
from core.mouse import MouseController
from gui.overlay import GameOverlay
from gui.settings_menu import HOTKEY_CODES, MENU_HOTKEY_CODES
from gui.modern_settings_menu import SettingsMenu
from gui.view_settings import DEFAULT_VIEW_SETTINGS, merge_view_settings

BASE_DIR = Path(
    os.environ.get(
        "BIOSYNC_AUX_DATA_DIR",
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent,
    )
).resolve()
RESOURCE_DIR = Path(
    os.environ.get(
        "BIOSYNC_AUX_RESOURCE_DIR",
        getattr(sys, "_MEIPASS", Path(__file__).resolve().parent),
    )
).resolve()

if sys.stdout is None:
    try:
        sys.stdout = open(BASE_DIR / 'biosync-runtime.log', 'a', encoding='utf-8', buffering=1)
    except OSError:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    try:
        sys.stderr = open(BASE_DIR / 'biosync-runtime-error.log', 'a', encoding='utf-8', buffering=1)
    except OSError:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(errors='replace')

os.chdir(BASE_DIR)

# --- CONFIGURAÇÃO VISUAL DO CONSOLE ---
if sys.platform == "win32":
    ctypes.windll.kernel32.SetConsoleTitleW("BioSync")

print("BioSync")
EMBEDDED = "--embedded" in sys.argv

# 1. Carregador e Analisador do arquivo de Configurações (config.ini)
config = configparser.ConfigParser()
caminho_config = RESOURCE_DIR / "config.ini"

if os.path.exists(caminho_config):
    config.read(caminho_config)
    print("[OK] Configuracoes carregadas.")
else:
    print(f"[ERRO] Arquivo de configuracao nao encontrado: {caminho_config}")
    sys.exit()

arquivo_ajustes_ativos = BASE_DIR / 'profiles' / 'active.json'
try:
    with open(arquivo_ajustes_ativos, 'r', encoding='utf-8') as arquivo_ajustes:
        ajustes_ativos = json.load(arquivo_ajustes)
except FileNotFoundError:
    ajustes_ativos = {}
except (json.JSONDecodeError, OSError) as erro:
    print(f"[AVISO] Perfil ativo ignorado: {erro}")
    ajustes_ativos = {}

# Extrai os valores do perfil ativo, usando config.ini como padrao inicial.
TAMANHO_FOV = int(ajustes_ativos.get('fov', config['Object Search window resolution']['detection_window_width']))
SMOOTHING = float(ajustes_ativos.get('smoothing', config['Mouse settings']['mouse_smoothing']))
HUMANIZER_SPEED = float(ajustes_ativos.get(
    'humanizer_speed',
    config.getfloat('Mouse settings', 'humanizer_speed', fallback=2000),
))
CAMINHO_MODELO = Path(ajustes_ativos.get(
    'model_path', config['AI options']['AI_model_path'],
))
if not CAMINHO_MODELO.is_absolute():
    CAMINHO_MODELO = RESOURCE_DIR / CAMINHO_MODELO
CAMINHO_MODELO = CAMINHO_MODELO.resolve()
if not CAMINHO_MODELO.is_file():
    raise FileNotFoundError(f"Modelo ONNX nao encontrado: {CAMINHO_MODELO}")
CONF_ALVO = float(config['AI options']['AI_conf'])
IOU_ALVO = config.getfloat('AI options', 'AI_iou', fallback=0.45)
MAX_DETECTIONS = config.getint('AI options', 'AI_max_det', fallback=5)
configured_target_classes = ajustes_ativos.get(
    'target_classes',
    config.get('AI options', 'target_classes', fallback=''),
)
if isinstance(configured_target_classes, str):
    CLASSES_ALVO = [name.strip() for name in configured_target_classes.split(',') if name.strip()]
else:
    CLASSES_ALVO = list(configured_target_classes or ())
PONTO_MIRA = ajustes_ativos.get('aim_point', config.get('Aim settings', 'aim_point', fallback='chest'))
TECLA_MIRA = ajustes_ativos.get('aim_key', config.get('Hot keys', 'auto_aim_key', fallback='Right mouse'))
TECLA_MENU = ajustes_ativos.get('menu_key', 'X')
if TECLA_MENU not in MENU_HOTKEY_CODES:
    TECLA_MENU = 'X'
EXIBIR_FOV = ajustes_ativos.get('show_fov', config.getboolean('Overlay settings', 'show_fov', fallback=True))
COR_FOV = ajustes_ativos.get('fov_color', config.get('Overlay settings', 'fov_color', fallback='#32D7A0'))
OPACIDADE_OVERLAY = int(ajustes_ativos.get('overlay_opacity', config.getint('Overlay settings', 'overlay_opacity', fallback=85)))

VIEW_SETTINGS = {}
for setting_name, default_value in DEFAULT_VIEW_SETTINGS.items():
    if setting_name == 'min_confidence':
        configured_fallback = config.get('AI options', 'AI_conf', fallback=str(default_value))
    elif setting_name == 'iou_threshold':
        configured_fallback = config.get('AI options', 'AI_iou', fallback=str(default_value))
    elif setting_name == 'max_detections':
        configured_fallback = config.get('AI options', 'AI_max_det', fallback=str(default_value))
    else:
        configured_fallback = str(default_value)
    raw_value = config.get('Views', setting_name, fallback=configured_fallback)
    try:
        if isinstance(default_value, bool):
            VIEW_SETTINGS[setting_name] = config.getboolean('Views', setting_name, fallback=default_value)
        elif isinstance(default_value, int):
            VIEW_SETTINGS[setting_name] = int(raw_value)
        elif isinstance(default_value, float):
            VIEW_SETTINGS[setting_name] = float(raw_value)
        else:
            VIEW_SETTINGS[setting_name] = raw_value
    except ValueError as erro:
        print(f"[AVISO] Opcao Views/{setting_name} invalida; usando padrao {default_value}: {erro}")
        VIEW_SETTINGS[setting_name] = default_value
VIEW_SETTINGS.update({
    'show_fov': EXIBIR_FOV,
    'fov_color': COR_FOV,
    'overlay_opacity': OPACIDADE_OVERLAY,
})
VIEW_SETTINGS = merge_view_settings({**VIEW_SETTINGS, **ajustes_ativos})
for setting_name, default_value in DEFAULT_VIEW_SETTINGS.items():
    if setting_name.endswith('_color'):
        configured_color = VIEW_SETTINGS[setting_name]
        if not isinstance(configured_color, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', configured_color):
            print(f"[AVISO] Cor invalida em Views/{setting_name}; usando {default_value}.")
            VIEW_SETTINGS[setting_name] = default_value
        else:
            VIEW_SETTINGS[setting_name] = configured_color.upper()
CONF_ALVO = float(VIEW_SETTINGS['min_confidence'])
IOU_ALVO = float(VIEW_SETTINGS['iou_threshold'])
MAX_DETECTIONS = int(VIEW_SETTINGS['max_detections'])
EXIBIR_FOV = bool(VIEW_SETTINGS['show_fov'])
COR_FOV = VIEW_SETTINGS['fov_color']
OPACIDADE_OVERLAY = int(VIEW_SETTINGS['overlay_opacity'])

HOTKEY_GATILHO = HOTKEY_CODES.get(TECLA_MIRA, HOTKEY_CODES['Right mouse'])
HOTKEY_MENU = MENU_HOTKEY_CODES[TECLA_MENU]

# 2. Inicialização Síncrona dos Componentes Universais de Engenharia
print("[INFO] Preparando captura e modelo...")
capturador = ScreenCapture(tamanho_fov=TAMANHO_FOV)
inteligencia = InferenceEngine(model_path=CAMINHO_MODELO, target_classes=CLASSES_ALVO)
print("[OK] Modelo ONNX carregado.")
try:
    metadata_path = BASE_DIR / 'profiles' / 'model_metadata.json'
    metadata_path.write_text(
        json.dumps({
            'model_path': str(CAMINHO_MODELO),
            'class_names': inteligencia.class_names,
        }, indent=2),
        encoding='utf-8',
    )
except OSError as erro:
    print(f"[AVISO] Nao foi possivel salvar metadata de classes do modelo: {erro}")
mouse = MouseController(
    smoothing=SMOOTHING,
    humanizer_speed=HUMANIZER_SPEED,
)

# O HUD flutuante calcula sozinho o tamanho do monitor e se expande nativamente
hud = GameOverlay(tamanho_fov=TAMANHO_FOV)
icone_app = RESOURCE_DIR / 'BioSync_AI-ico.ico'
if icone_app.is_file():
    hud.root.iconbitmap(str(icone_app))
hud.configurar_visual(TAMANHO_FOV, EXIBIR_FOV, COR_FOV, OPACIDADE_OVERLAY)
hud.configurar_views(VIEW_SETTINGS)
print("[OK] Captura, modelo ONNX e HUD prontos.")

def aplicar_configuracoes(valores):
    global TAMANHO_FOV, PONTO_MIRA, HOTKEY_GATILHO, TECLA_MENU, HOTKEY_MENU
    global EXIBIR_FOV, COR_FOV, OPACIDADE_OVERLAY, CONF_ALVO, IOU_ALVO, MAX_DETECTIONS
    global VIEW_SETTINGS, CLASSES_ALVO

    valores.setdefault('model_path', str(CAMINHO_MODELO))
    novo_fov = int(valores['fov'])
    if novo_fov != TAMANHO_FOV:
        capturador.definir_fov(novo_fov)
        TAMANHO_FOV = novo_fov

    mouse.smoothing = float(valores['smoothing'])
    mouse.humanizer_speed = max(
        200.0,
        min(4000.0, float(valores.get('humanizer_speed', HUMANIZER_SPEED))),
    )
    PONTO_MIRA = valores['aim_point']
    HOTKEY_GATILHO = HOTKEY_CODES[valores['aim_key']]
    TECLA_MENU = valores['menu_key']
    HOTKEY_MENU = MENU_HOTKEY_CODES[TECLA_MENU]
    VIEW_SETTINGS = merge_view_settings(valores)
    EXIBIR_FOV = VIEW_SETTINGS['show_fov']
    COR_FOV = VIEW_SETTINGS['fov_color']
    OPACIDADE_OVERLAY = int(VIEW_SETTINGS['overlay_opacity'])
    CONF_ALVO = float(VIEW_SETTINGS['min_confidence'])
    IOU_ALVO = float(VIEW_SETTINGS['iou_threshold'])
    MAX_DETECTIONS = int(VIEW_SETTINGS['max_detections'])
    configured_classes = valores.get('target_classes', CLASSES_ALVO)
    if isinstance(configured_classes, str):
        CLASSES_ALVO = [name.strip() for name in configured_classes.split(',') if name.strip()]
    else:
        CLASSES_ALVO = list(configured_classes or ())
    inteligencia.set_target_classes(CLASSES_ALVO)
    hud.configurar_visual(TAMANHO_FOV, EXIBIR_FOV, COR_FOV, OPACIDADE_OVERLAY)
    hud.configurar_views(VIEW_SETTINGS)

    arquivo_ajustes_ativos.parent.mkdir(parents=True, exist_ok=True)
    with open(arquivo_ajustes_ativos, 'w', encoding='utf-8') as arquivo_ajustes:
        json.dump(valores, arquivo_ajustes, indent=2)


encerrando_app = False

def encerrar_aplicacao():
    global encerrando_app
    encerrando_app = True
    hud.root.destroy()


if not EMBEDDED:
    menu = SettingsMenu(hud.root, {
        'fov': TAMANHO_FOV,
        'smoothing': SMOOTHING,
        'humanizer_speed': HUMANIZER_SPEED,
        'aim_point': PONTO_MIRA,
        'aim_key': TECLA_MIRA,
        'menu_key': TECLA_MENU,
        'show_fov': EXIBIR_FOV,
        'fov_color': COR_FOV,
        'overlay_opacity': OPACIDADE_OVERLAY,
        **VIEW_SETTINGS,
    }, aplicar_configuracoes, on_force_close=encerrar_aplicacao)
else:
    menu = None
    command_queue = queue.Queue()

    def read_host_commands():
        for command in sys.stdin:
            normalized = command.strip()
            if normalized.upper() == "STOP":
                command_queue.put("STOP")
                return
            try:
                parsed_command = json.loads(normalized)
            except json.JSONDecodeError:
                print(f"[AVISO] Comando do host ignorado: {normalized!r}")
                continue
            if isinstance(parsed_command, dict) and parsed_command.get("type") in ("fov", "settings"):
                command_queue.put(parsed_command)
        command_queue.put("STOP")

    threading.Thread(
        target=read_host_commands,
        name="Auxilio-AI-Host-Control",
        daemon=True,
    ).start()

estado_tecla_menu = False
runtime_exit_code = 0

print(f"[OK] Captura e modelo prontos. FOV: {TAMANHO_FOV}px.")
print(f"[INFO] Velocidade: {SMOOTHING:.2f} | ponto de mira: {PONTO_MIRA}.")
print(f"[INFO] Menu: {TECLA_MENU} abre/fecha, Esc oculta | ativacao: {TECLA_MIRA}.")
print("[AVISO] A assistencia automatiza a mira; use apenas onde isso for permitido.")
print("[STATUS] BioSync pronto.\n")

# 3. O Loop Contínuo Mestre (Captura -> Inferência -> Decisão -> Mira -> HUD)
try:
    while not encerrando_app:
        if EMBEDDED:
            try:
                host_command = command_queue.get_nowait()
            except queue.Empty:
                pass
            else:
                if host_command == "STOP":
                    encerrando_app = True
                    break
                if host_command.get("type") == "fov":
                    novo_fov = max(160, min(640, int(host_command['value'])))
                    if novo_fov != TAMANHO_FOV:
                        capturador.definir_fov(novo_fov)
                        TAMANHO_FOV = novo_fov
                        hud.configurar_visual(
                            TAMANHO_FOV, EXIBIR_FOV, COR_FOV, OPACIDADE_OVERLAY
                        )
                elif host_command.get("type") == "settings":
                    aplicar_configuracoes(host_command["settings"])
        else:
            tecla_menu_pressionada = win32api.GetAsyncKeyState(HOTKEY_MENU) < 0
            if tecla_menu_pressionada and not estado_tecla_menu:
                menu.toggle()
            estado_tecla_menu = tecla_menu_pressionada

        # Passo 1: Captura o frame atual direto da VRAM do computador via DirectX
        frame = capturador.capturar_frame()
        if frame is None:
            # Atualiza os loops de janelas do Windows mesmo em frames vazios para evitar congelar
            hud.atualizar_interface()
            continue

        # Passo 2: Verifica o gatilho antes da inferência para manter o mesmo alvo enquanto mira
        hotkey_pressionada = win32api.GetAsyncKeyState(HOTKEY_GATILHO) < 0

        # Passo 3: Executa a inferência na GPU (AMD, NVIDIA ou Intel) através do DirectML
        # Retorna se há alvo válido e os pixels locais (X, Y) mapeados dentro do quadrado do FOV
        alvo_visivel, alvo_x, alvo_y = inteligencia.processar_frame(
            frame,
            img_size=TAMANHO_FOV,
            conf_threshold=CONF_ALVO,
            lock_target=hotkey_pressionada,
            aim_point=PONTO_MIRA,
            iou_threshold=IOU_ALVO,
            max_det=MAX_DETECTIONS,
            filter_distance=VIEW_SETTINGS['distance_filter'],
            min_distance=VIEW_SETTINGS['min_distance'],
            max_distance=VIEW_SETTINGS['max_distance'],
            ignore_small=VIEW_SETTINGS['ignore_small_targets'],
            min_box_area=VIEW_SETTINGS['min_box_area'],
            ignore_large=VIEW_SETTINGS['ignore_large_targets'],
            max_box_area=VIEW_SETTINGS['max_box_area'],
        )

        hud.desenhar_deteccoes_hud(
            inteligencia.last_detections,
            alvo_x if alvo_visivel else None,
            alvo_y if alvo_visivel else None,
        )
        if alvo_visivel:
            # Passo 4: Movimentação - Executa o controle físico apenas sob ativação do gatilho
            if hotkey_pressionada:
                mouse.mirar_no_alvo(alvo_local_x=alvo_x, alvo_local_y=alvo_y, tamanho_fov=TAMANHO_FOV)
            
            # Passo 5: Renderização - Projeta o quadrado indicador vermelho por cima da tela
        # Atualiza a renderização de quadros e limpa a fila do vidro transparente do HUD
        hud.atualizar_interface()

except KeyboardInterrupt:
    print("\n[INFO] BioSync encerrado.")

except tk.TclError as e:
    try:
        janela_ativa = bool(hud.root.winfo_exists())
    except tk.TclError:
        janela_ativa = False
    if not janela_ativa:
        print("\n[INFO] Janela do BioSync encerrada.")
    else:
        print(f"\n[X] Erro na interface: {e}")

except Exception as e:
    print(f"\n[X] Ocorreu uma interrupção falha na execução do Loop Mestre: {e}")
    if EMBEDDED:
        runtime_exit_code = 1

finally:
    if EMBEDDED:
        try:
            hud.limpar_alvos()
            hud.root.destroy()
        except tk.TclError:
            pass
    print("[INFO] Sessao finalizada.")
if runtime_exit_code:
    raise SystemExit(runtime_exit_code)
