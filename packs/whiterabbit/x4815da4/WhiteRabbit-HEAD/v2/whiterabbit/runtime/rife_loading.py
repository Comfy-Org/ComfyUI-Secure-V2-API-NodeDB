# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2025 ArtificialSweetener <artificialsweetenerai@proton.me>

"""Load and cache RIFE models through Comfy's model management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import torch
from torch import nn

from ..domain.rife import RifeModelSpec
from .rife_architecture import RifeInferenceModel


@dataclass(frozen=True)
class LoadedRifeModel:
    """A model, its Comfy patcher, and inference device metadata."""

    inference_model: RifeInferenceModel
    patcher: Any
    device: torch.device
    dtype: torch.dtype
    spec: RifeModelSpec


class RifeModelLoader:
    """Fail-closed placeholder replaced by the async secure weight loader."""

    def __init__(self, resolver: Any = None) -> None:
        del resolver

    def load(
        self,
        filename: str,
        frame_shape: tuple[int, ...] | None = None,
        scale_factor: float = 1.0,
    ) -> LoadedRifeModel:
        del filename, frame_shape, scale_factor
        raise RuntimeError(
            "RIFE weights must be prepared by the secure async loader")


__all__ = ["LoadedRifeModel", "RifeModelLoader"]
