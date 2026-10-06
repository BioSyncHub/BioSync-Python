from typing import Literal

import numpy as np
from numpy.typing import NDArray

Region = tuple[int, int, int, int]
OutputColor = Literal["RGB", "RGBA", "BGR", "BGRA", "GRAY"]


class BetterCam:
    def grab(self, region: Region | None = ...) -> NDArray[np.uint8] | None: ...
    def release(self) -> None: ...


def create(
    device_idx: int = ...,
    output_idx: int | None = ...,
    region: Region | None = ...,
    output_color: OutputColor = ...,
    nvidia_gpu: bool = ...,
    max_buffer_len: int = ...,
) -> BetterCam: ...
