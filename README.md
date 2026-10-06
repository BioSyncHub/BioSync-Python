# BioSync | AA HUB — Python Prototype

UI **CustomTkinter** estilo MW / Warzone + backend **vgamepad** (ViGEm).

## Atualizações recentes

Esta atualização integra e expande o Auxilio-AI no aplicativo BioSync:

- Painel Auxilio-AI integrado para iniciar e encerrar o motor ONNX sem fechar a janela principal.
- Página **Views** com configuração de ESP, filtros, linhas, marcadores, zonas corporais e classes-alvo lidas do modelo.
- Inferência ONNX com leitura de classes, dimensões, layout e tipo de entrada pelos metadados, usando DirectML, CUDA ou CPU conforme disponibilidade.
- Configurações e perfis do Auxilio-AI persistidos separadamente dos arquivos instalados, inclusive na build de pasta do Windows.
- Inicialização do runtime auxiliar sob demanda, com confirmação antes de instalar dependências, além de logs de setup e execução.
- Build de distribuição em pasta com PyInstaller e novos testes automatizados para inicialização, caminhos, inferência e configurações do Auxilio-AI.

Estas são notas da versão de desenvolvimento atual. Nenhum número de versão ou tag de release foi criado nesta atualização.

Pipeline de entrada/controle adaptado da referência C# ativa:

```
Windows Raw Input → Gain × Filter × Sens × Curve → Accel power-law
                  → Friction · Smoothing · Inverse Deadzone · Clamp ±32767
                  → macros · WASD→LS · Triggers LMB/RMB → vgamepad
```

No Windows, o app registra Raw Input para receber deltas físicos do mouse e usa
ViGEm/vgamepad para enviar os relatórios do controle. Em outras plataformas, a
captura de movimento continua usando `pynput`.

## Requisitos (Windows)

1. **Python 3.10+** (marcar *Add to PATH* na instalação)
2. **ViGEmBus** — https://github.com/nefarius/ViGEmBus/releases
3. Dependências Python (o app solicita autorização antes de instalá-las se estiverem ausentes)

## Como rodar

### Opção rápida
```
run.bat
```

### Manual
```bash
pip install -r requirements.txt
python main.py
```

### Build em EXE (Windows)
```bat
build_exe.bat
```

Este comando instala o PyInstaller e gera uma build de pasta em `dist\BioSync\BioSync.exe`. A pasta interna `_internal` fica oculta no Explorador do Windows, mas continua necessária: mantenha-a junto ao EXE ao distribuir. A build inclui a biblioteca nativa do vgamepad que conecta ao driver ViGEmBus. O formato de pasta evita extrair todo o aplicativo a cada inicialização, como ocorre com builds `--onefile`. A tela inicial mostra o progresso por etapas e mensagens visuais por até 5 segundos. O BioSync não limpa caches nem modifica o ReShade; a disponibilidade do controle virtual não interrompe a abertura do menu e só é solicitada ao tentar ativar o motor.

O motor ONNX é iniciado quando solicitado na aba Auxílio-AI. Se um ambiente ONNX funcional já estiver ao lado do projeto/build, ele é reutilizado; caso contrário, o app pede autorização antes de baixar/instalar o runtime isolado Python 3.11. Se o Python Launcher/3.11 estiver ausente, oferece abrir a página oficial de download. O andamento e erros ficam no `setup.log` em `%LOCALAPPDATA%\BioSync\auxilio_ai`. As configurações e logs do EXE também são gravados em `%LOCALAPPDATA%\BioSync`, não na pasta temporária interna do PyInstaller.

- **Insert** ou botão **ARM ENGINE** → liga captura + report do pad
- Abas: Home · Sensitivity · Mapping · Macros · Auxilio-Ai
- **Auxilio-Ai:** contém o painel integrado de configuração do ONNX, incluindo FOV, ponto de referência, atalhos e suavização, baseado no painel da referência.
- O overlay do Auxilio-AI reutiliza os itens gráficos do Canvas entre atualizações para reduzir criação e descarte repetidos de elementos visuais.
- **User:** espaço reservado para futura integração de autenticação pwfauth; nenhuma conexão de autenticação é feita atualmente.
- Janela fixa em **1000 × 720**; minimizar e fechar continuam disponíveis.
- Configuração ativa: `config/config.json` em modo fonte; na build EXE, `%LOCALAPPDATA%\BioSync\config\config.json`
- Perfis nomeados: na aba **Sensitivity**, use o card **PERFIS DE CONFIGURAÇÃO** abaixo dos ajustes X, Y e dinâmica para salvar e carregar suas preferências.

## Painéis de configuração

- **Sensibilidade:** controles agrupados em cartões para os eixos X e Y e para dinâmica/suavização.
- **Mapeamento:** clique em um campo e pressione a tecla que deseja associar ao botão virtual; a alteração é salva na configuração.
- **Macros:** controles agrupados para YY, Slide Cancel, Auto Ping, No Recoil e assistência rotacional, com chaves liga/desliga. O No Recoil da **VOYAK KT-3** usa a curva definida em `config/recoil_profiles.json` (subida vertical → gancho direito → wiggle no topo) enquanto o botão de disparo está pressionado; ADS não é obrigatório. O modo **Constante** volta à puxada fixa dos sliders.
- As abas de configuração são compactadas para exibir as opções sem rolagem na janela padrão.

## Identidade visual

| Elemento | Valor |
|----------|--------|
| Accent (brush MW) | `#FFCF00` |
| Fundo noturno | `#0A0A0F` |
| Painel / cards | `#1A191E` / `#2E2D33` |
| Título sidebar | **BioSync \| MENU** |
| Fonte do título | `assets/fonts/MODERN WARFARE.otf` |

## Estrutura

```
BioSync-Python/
├── main.py
├── run.bat
├── requirements.txt
├── README.md
├── assets/
│   └── fonts/MODERN WARFARE.otf
├── config/
│   ├── config.json
│   └── recoil_profiles.json
├── core/
│   ├── config.py
│   ├── engine.py
│   ├── input_capture.py
│   ├── raw_input.py
│   └── recoil.py
├── tests/
│   ├── test_engine.py
│   ├── test_profiles.py
│   └── test_recoil.py
├── ui/
│   ├── app.py
│   └── theme.py
└── auxilio_ai/
    ├── main.py
    ├── setup.bat
    ├── config.ini
    ├── requirements.txt
    ├── core/
    ├── gui/
    ├── models/BioSync-Warzone.onnx
    ├── models/BioSync-Fortnite.onnx
    └── profiles/
```

Os perfis salvos pelo usuário ficam em `config/profiles.json` no modo fonte ou `%LOCALAPPDATA%\BioSync\config\profiles.json` no EXE, criado automaticamente ao salvar o primeiro perfil.
Os presets rápidos de sensibilidade ficam definidos diretamente na aba **Mapping**.

## Auxilio-AI integrado

O código-fonte, o modelo ONNX e os arquivos de configuração da referência ficam em `auxilio_ai/`. A página **AUXILIO-AI** incorpora os controles do painel original; as configurações são salvas em `auxilio_ai/profiles/active.json` no modo fonte ou `%LOCALAPPDATA%\BioSync\auxilio_ai\profiles\active.json` no EXE.

Na primeira utilização, **Iniciar Aux-AI** solicita autorização para criar o ambiente Python 3.11 isolado e instalar as dependências; após a instalação, inicia o motor automaticamente. É necessário ter o Python Launcher e Python 3.11 instalados. **Iniciar Aux-AI** abre o HUD e inicia captura/inferência ONNX em processo isolado. **Encerrar Aux-AI** para o processo de captura e inferência e fecha somente o HUD auxiliar; a janela principal BioSync continua aberta. Os ajustes de FOV atualizam captura e overlay enquanto o motor está ativo; **Aplicar** envia os demais ajustes ao processo sem reiniciá-lo, reiniciando-o somente quando o perfil ONNX muda. Logs ficam em `auxilio_ai/biosync-runtime.log` e `auxilio_ai/setup.log`.

Na aba **AUXILIO-AI**, use o seletor **Aim / Views** para alternar entre mira e visuais. Em **Aim**, a área de detecção reúne o ponto de referência, a silhueta tática e os indicadores de cabeça, peito e barriga; ao lado, o card de resposta mantém a suavização e oferece um slider **Humanizer** independente, que limita a velocidade do movimento em pixels por segundo. Em **Views**, o perfil do modelo é escolhido entre os ONNX carregados da pasta `auxilio_ai/models`; os perfis principais são **BioSync-Warzone** e **BioSync-Fortnite**. Ao trocar o modelo com o motor ativo e clicar em **Aplicar**, o motor reinicia para carregar o novo ONNX. Os demais cards de Views oferecem ESP, filtros, linhas, marcadores, zonas corporais e FOV.

O motor de referência pode automatizar movimentos de mira. Use-o apenas em ambientes autorizados e respeite as regras do jogo; o BioSync não contorna sistemas anti-cheat nem garante ausência de sanções. Consulte também `auxilio_ai/README.md`.

## Latência

Loop soft ~1 kHz em Python. Adequado para protótipo de UI e tuning de presets.
