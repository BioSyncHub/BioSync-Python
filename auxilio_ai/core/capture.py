import ctypes
import bettercam
import numpy as np
from numpy.typing import NDArray

class ScreenCapture:
    def __init__(self, tamanho_fov: int = 320) -> None:
        self.tamanho_fov = tamanho_fov
        
        # Puxa dinamicamente a resolução real do monitor principal do usuário no Windows
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware() # Garante a leitura correta mesmo com escala de zoom do Windows ativa
        
        self.largura_real = user32.GetSystemMetrics(0)
        self.altura_real = user32.GetSystemMetrics(1)
        
        self.regiao = self._calcular_regiao(tamanho_fov)
        self.camera: bettercam.BetterCam | None = self._criar_camera(self.regiao)

    @staticmethod
    def _criar_camera(region: tuple[int, int, int, int]) -> bettercam.BetterCam:
        return bettercam.create(region=region, output_color="RGB")

    def _calcular_regiao(self, tamanho_fov: int) -> tuple[int, int, int, int]:
        centro_x = self.largura_real // 2
        centro_y = self.altura_real // 2
        metade = tamanho_fov // 2
        return (centro_x - metade, centro_y - metade, centro_x + metade, centro_y + metade)

    def definir_fov(self, tamanho_fov: int) -> None:
        tamanho_fov = int(tamanho_fov)
        if tamanho_fov == self.tamanho_fov:
            return

        nova_regiao = self._calcular_regiao(tamanho_fov)
        if self.camera is not None:
            self.camera.release()
            self.camera = None

        self.regiao = nova_regiao
        self.tamanho_fov = tamanho_fov
        self.camera = self._criar_camera(nova_regiao)

    def capturar_frame(self) -> NDArray[np.uint8] | None:
        """Retorna o frame atual da VRAM"""
        if self.camera is None:
            raise RuntimeError("A câmera BetterCam não está inicializada.")
        return self.camera.grab()
