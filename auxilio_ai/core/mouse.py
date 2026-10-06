import ctypes
import time

# --- ESTRUTURAS NATIVAS DE INPUT DO WINDOWS (USER32) ---
LONG = ctypes.c_long
DWORD = ctypes.c_ulong
ULONG_PTR = ctypes.POINTER(ctypes.c_ulong)

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", LONG),
        ("dy", LONG),
        ("mouseData", DWORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", DWORD),
        ("mi", MOUSEINPUT)
    ]

MOUSE_MOVED = 0x0001

class MouseController:
    def __init__(
        self,
        smoothing: float = 0.40,
        humanizer_speed: float = 2000.0,
    ) -> None:
        """
        Gerencia a velocidade de movimento da mira e a intensidade da resposta.
        """
        self.smoothing = smoothing
        self.humanizer_speed = humanizer_speed
        self._last_move_at = time.perf_counter()
        self._pending_x = 0.0
        self._pending_y = 0.0

    def mover_relativo(self, x_offset: float, y_offset: float) -> None:
        """
        Envia os sinais binários de movimento direto para a fila do sistema do Windows.
        """
        extra = ctypes.c_ulong(0)
        ii_ = INPUT()
        ii_.type = 0  # INPUT_MOUSE
        ii_.mi = MOUSEINPUT(int(x_offset), int(y_offset), 0, MOUSE_MOVED, 0, ctypes.pointer(extra))
        
        # Injeção de hardware via chamada nativa
        ctypes.windll.user32.SendInput(1, ctypes.pointer(ii_), ctypes.sizeof(ii_))

    def mirar_no_alvo(
        self,
        alvo_local_x: int,
        alvo_local_y: int,
        tamanho_fov: int = 320,
    ) -> None:
        """
        Calcula o movimento até o alvo, aplicando intensidade e limite de velocidade.
        """
        centro_fov = tamanho_fov // 2
        
        # Descobre a distância exata em pixels que falta para cravar no alvo
        distancia_x = alvo_local_x - centro_fov
        distancia_y = alvo_local_y - centro_fov
        
        # Smoothing controls the response strength; humanizer_speed independently
        # caps how many pixels can be traversed per second.
        passo_x = distancia_x * self.smoothing
        passo_y = distancia_y * self.smoothing
        now = time.perf_counter()
        elapsed = min(max(now - self._last_move_at, 0.0), 0.1)
        self._last_move_at = now
        max_distance = self.humanizer_speed * elapsed
        distance = (passo_x * passo_x + passo_y * passo_y) ** 0.5
        if distance > max_distance and distance > 0:
            scale = max_distance / distance
            passo_x *= scale
            passo_y *= scale

        self._pending_x += passo_x
        self._pending_y += passo_y
        move_x = int(self._pending_x)
        move_y = int(self._pending_y)
        if move_x or move_y:
            self._pending_x -= move_x
            self._pending_y -= move_y
            self.mover_relativo(move_x, move_y)
