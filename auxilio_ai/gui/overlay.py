import tkinter as tk
from typing import Any, Literal, Mapping, Sequence

import win32gui
import win32con
import ctypes

class GameOverlay:
    def __init__(self, tamanho_fov: int = 320) -> None:
        """
        Cria uma tela transparente invisível ao clique por cima de qualquer resolução de monitor.
        """
        self.tamanho_fov = tamanho_fov
        
        # Descobre dinamicamente a resolução exata do monitor atual do usuário no Windows
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        self.largura_real = user32.GetSystemMetrics(0)
        self.altura_real = user32.GetSystemMetrics(1)
        
        # Inicializa a janela invisível do Tkinter
        self.root = tk.Tk()
        self.root.title("( BioSync | AI ) - HUD Visual")
        
        # Expande a janela exatamente sobre o tamanho do monitor detectado
        self.root.geometry(f"{self.largura_real}x{self.altura_real}+0+0")
        
        # Remove molduras e botões do Windows
        self.root.overrideredirect(True)
        self.root.lift()
        self.root.wm_attributes("-topmost", True)
        
        # Transforma a cor preta em transparência absoluta de vidro (Chroma Key)
        self.root.wm_attributes("-transparentcolor", "black")
        
        # Cria a camada de desenho fluida
        self.canvas = tk.Canvas(self.root, width=self.largura_real, height=self.altura_real, bg="black", highlightthickness=0)
        self.canvas.pack()
        self.elementos_alvo: list[int] = []
        self._element_pools: dict[str, list[int]] = {
            "rectangle": [], "line": [], "oval": [],
        }
        self._element_cursors: dict[str, int] = {}
        self.id_circulo_fov = None
        self.exibir_fov = True
        self.cor_fov = "#32D7A0"
        self.opacidade = 85
        self.view_settings: dict[str, Any] = {}
        
        # Aplica o filtro de clique passivo (Click-Through)
        self.configurar_estilo_transparente()
        
        # Desenha a circunferência inicial de calibração do FOV
        self.atualizar_circulo_fov()
        self.definir_opacidade(self.opacidade)

    def configurar_estilo_transparente(self) -> None:
        """Aplica as regras de Kernel para a janela ignorar cliques do mouse e focar no jogo"""
        hwnd = win32gui.FindWindow(None, "( BioSync | AI ) - HUD Visual")
        estilo_janela = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, estilo_janela | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT)

    def atualizar_circulo_fov(self) -> None:
        """Atualiza o círculo de FOV no centro matemático do monitor."""
        if self.id_circulo_fov is not None:
            self.canvas.delete(self.id_circulo_fov)
            self.id_circulo_fov = None
        if not self.exibir_fov:
            return

        centro_x = self.largura_real // 2
        centro_y = self.altura_real // 2
        raio = self.tamanho_fov // 2
        
        self.id_circulo_fov = self.canvas.create_oval(
            centro_x - raio, centro_y - raio,
            centro_x + raio, centro_y + raio,
            outline=self.cor_fov, width=2
        )

    def configurar_visual(
        self,
        tamanho_fov: int,
        exibir_fov: bool,
        cor_fov: str,
        opacidade: int,
    ) -> None:
        self.tamanho_fov = int(tamanho_fov)
        self.exibir_fov = bool(exibir_fov)
        self.cor_fov = cor_fov
        self.atualizar_circulo_fov()
        self.definir_opacidade(opacidade)

    def configurar_views(self, settings: Mapping[str, Any]) -> None:
        self.view_settings = dict(settings)

    def definir_opacidade(self, opacidade: int) -> None:
        self.opacidade = max(10, min(100, int(opacidade)))
        self.root.wm_attributes("-alpha", self.opacidade / 100)

    def desenhar_alvo_hud(self, alvo_local_x: int, alvo_local_y: int) -> None:
        """
        Recebe a coordenada local do modelo e projeta o quadrado indicador vermelho
        na posição global correta da tela por cima do jogo.
        """
        self._begin_draw()
        
        # Traduz a coordenada local de 320x320 para a posição real da tela do usuário
        centro_x_global = (self.largura_real // 2) - (self.tamanho_fov // 2) + alvo_local_x
        centro_y_global = (self.altura_real // 2) - (self.tamanho_fov // 2) + alvo_local_y
        
        tamanho_marcador = 10
        self._draw_item(
            "rectangle",
            (
                centro_x_global - tamanho_marcador,
                centro_y_global - tamanho_marcador,
                centro_x_global + tamanho_marcador,
                centro_y_global + tamanho_marcador,
            ),
            outline="#FF0000",
            fill="",
            width=2,
            stipple="",
        )
        self._end_draw()

    def desenhar_deteccoes_hud(
        self,
        detections: Sequence[tuple[int, int, int, int, float, int]],
        alvo_local_x: int | None = None,
        alvo_local_y: int | None = None,
    ) -> None:
        self._begin_draw()
        origin_x = (self.largura_real - self.tamanho_fov) // 2
        origin_y = (self.altura_real - self.tamanho_fov) // 2
        settings = self.view_settings
        selected = None

        for x, y, width, height, _, _ in detections:
            left = origin_x + x
            top = origin_y + y
            right = left + width
            bottom = top + height
            opacity = max(0, min(100, int(settings.get("esp_opacity", 45))))
            color = self._apply_opacity(settings.get("esp_color", "#FF3030"), opacity)
            thickness = max(1, int(settings.get("esp_thickness", 2)))
            style = settings.get("esp_style", "Normal")

            if settings.get("esp_enabled", False) and opacity > 0:
                if style == "Filled":
                    self._draw_item(
                        "rectangle",
                        (left, top, right, bottom),
                        fill=settings.get("esp_color", "#FF3030"),
                        outline=color,
                        width=thickness,
                        stipple=self._opacity_stipple(opacity),
                    )
                elif style == "Corner":
                    corner_w = max(4, width // 4)
                    corner_h = max(4, height // 4)
                    for x1, y1, x2, y2 in (
                        (left, top, left + corner_w, top),
                        (left, top, left, top + corner_h),
                        (right - corner_w, top, right, top),
                        (right, top, right, top + corner_h),
                        (left, bottom, left + corner_w, bottom),
                        (left, bottom - corner_h, left, bottom),
                        (right - corner_w, bottom, right, bottom),
                        (right, bottom - corner_h, right, bottom),
                    ):
                        self._draw_item(
                            "line", (x1, y1, x2, y2), fill=color, width=thickness,
                        )
                else:
                    self._draw_item(
                        "rectangle",
                        (left, top, right, bottom),
                        fill="",
                        outline=color,
                        width=thickness,
                        stipple="",
                    )

                if settings.get("show_body_zones", False):
                    for ratio, zone_color in (
                        (0.2, settings.get("head_color", "#F06464")),
                        (0.43, settings.get("chest_color", "#32C7D7")),
                        (0.65, settings.get("belly_color", "#F2C94C")),
                    ):
                        zone_y = top + int(height * ratio)
                        self._draw_item(
                            "line",
                            (left, zone_y, right, zone_y),
                            fill=zone_color,
                            width=1,
                        )

            if alvo_local_x is not None and alvo_local_y is not None:
                if x <= alvo_local_x <= x + width and y <= alvo_local_y <= y + height:
                    selected = (origin_x + alvo_local_x, origin_y + alvo_local_y)

        if selected is not None:
            target_x, target_y = selected
            if settings.get("snap_line", False):
                self._draw_item(
                    "line",
                    (
                        self.largura_real // 2,
                        self.altura_real // 2,
                        target_x,
                        target_y,
                    ),
                    fill=settings.get("snap_line_color", "#32D7A0"),
                    width=max(1, int(settings.get("snap_line_thickness", 2))),
                )
            if settings.get("show_aim_marker", True):
                marker_size = 5
                self._draw_item(
                    "oval",
                    (
                        target_x - marker_size,
                        target_y - marker_size,
                        target_x + marker_size,
                        target_y + marker_size,
                    ),
                    outline=settings.get("marker_color", "#FF3030"),
                    fill="",
                    width=2,
                )
        self._end_draw()

    def _begin_draw(self) -> None:
        self._element_cursors = {item_type: 0 for item_type in self._element_pools}
        self.elementos_alvo.clear()

    def _draw_item(
        self,
        item_type: Literal["rectangle", "line", "oval"],
        coordinates: tuple[int, int, int, int],
        **options: Any,
    ) -> None:
        pool = self._element_pools[item_type]
        index = self._element_cursors[item_type]
        if index == len(pool):
            create = getattr(self.canvas, f"create_{item_type}")
            pool.append(create(*coordinates, state="hidden"))

        element = pool[index]
        self.canvas.coords(element, *coordinates)
        self.canvas.itemconfigure(element, state="normal", **options)
        self._element_cursors[item_type] = index + 1
        self.elementos_alvo.append(element)

    def _end_draw(self) -> None:
        for item_type, pool in self._element_pools.items():
            used = self._element_cursors[item_type]
            for element in pool[used:]:
                self.canvas.itemconfigure(element, state="hidden")

    def limpar_alvos(self) -> None:
        """Oculta os marcadores, preservando os itens do Canvas para a próxima atualização."""
        for pool in self._element_pools.values():
            for elemento in pool:
                self.canvas.itemconfigure(elemento, state="hidden")
        self.elementos_alvo.clear()
        self._element_cursors = {item_type: 0 for item_type in self._element_pools}

    @staticmethod
    def _apply_opacity(color: object, opacity: int) -> object:
        if not isinstance(color, str) or len(color) != 7 or not color.startswith("#"):
            return color
        try:
            channels = [int(color[index:index + 2], 16) for index in (1, 3, 5)]
        except ValueError:
            return color
        return "#" + "".join(f"{channel * opacity // 100:02X}" for channel in channels)

    @staticmethod
    def _opacity_stipple(opacity: int) -> str:
        if opacity >= 100:
            return ""
        if opacity <= 25:
            return "gray12"
        if opacity <= 50:
            return "gray25"
        if opacity <= 75:
            return "gray50"
        return "gray75"

    def atualizar_interface(self) -> None:
        """Executa a atualização de quadros visual da janela do overlay"""
        self.root.update()
