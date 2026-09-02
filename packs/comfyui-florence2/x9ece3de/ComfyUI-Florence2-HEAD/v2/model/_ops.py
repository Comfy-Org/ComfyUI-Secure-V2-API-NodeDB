"""Boundary equivalents for the host operations Florence-2 was built against.

Upstream constructs the model with ``comfy.ops.manual_cast`` and reaches into
``comfy.ldm.modules.attention`` and ``comfy.utils``.  Those are core surface,
refused inside the secure guest, so the same policies are expressed here with
plain torch and nothing else.

Each class mirrors the behaviour of its host counterpart rather than merely
resembling it:

* ``manual_cast.Linear`` / ``LayerNorm`` / ``Conv2d`` cast weight and bias to
  the *input's* dtype and device at forward time -- that is precisely what
  ``comfy_cast_weights = True`` means.
* ``manual_cast.Embedding`` moves the table to the input's device but keeps a
  half-precision table in its own dtype, matching
  ``Embedding.forward_comfy_cast_weights`` where ``out_dtype`` is forced to
  ``None`` for float16/bfloat16 weights.
* ``attention_small_input`` is the function
  ``optimized_attention_for_device(..., small_input=True)`` selects when
  PyTorch attention is available, restricted to the one call shape DaViT uses
  (``skip_reshape=True``, no mask).

No host module is imported here, and nothing in this file is configurable
from a workflow.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F


def cast_to_input(weight, input, non_blocking=False, copy=True):
    """Mirror ``comfy.ops.cast_to_input``."""
    return weight.to(
        dtype=input.dtype, device=input.device,
        non_blocking=non_blocking, copy=copy,
    )


def _cast(param, input):
    if param is None:
        return None
    if param.dtype == input.dtype and param.device == input.device:
        return param
    return param.to(dtype=input.dtype, device=input.device)


class manual_cast:
    """The ``comfy.ops.manual_cast`` weight policy, in plain torch."""

    class Linear(torch.nn.Linear):
        def forward(self, input):
            return F.linear(input, _cast(self.weight, input), _cast(self.bias, input))

    class Conv2d(torch.nn.Conv2d):
        def forward(self, input):
            return self._conv_forward(
                input, _cast(self.weight, input), _cast(self.bias, input))

    class LayerNorm(torch.nn.LayerNorm):
        def forward(self, input):
            return F.layer_norm(
                input, self.normalized_shape,
                _cast(self.weight, input), _cast(self.bias, input), self.eps)

    class Embedding(torch.nn.Embedding):
        def forward(self, input, out_dtype=None):
            output_dtype = out_dtype
            if self.weight.dtype in (torch.float16, torch.bfloat16):
                out_dtype = None
            weight = self.weight
            target = weight.dtype if out_dtype is None else out_dtype
            if weight.device != input.device or weight.dtype != target:
                weight = weight.to(device=input.device, dtype=target)
            return F.embedding(
                input, weight, self.padding_idx, self.max_norm,
                self.norm_type, self.scale_grad_by_freq, self.sparse,
            ).to(dtype=output_dtype)


def attention_small_input(
    q, k, v, heads, mask=None, skip_reshape=True, skip_output_reshape=False,
):
    """``attention_pytorch`` for the two shapes Florence-2 calls it with.

    Both call sites pass pre-reshaped BHND tensors.  The host function also
    has a batched fallback that splits the call above ``SDP_BATCH_LIMIT``;
    that path chunks the same computation for memory and returns identical
    values, so it is not reproduced here.
    """
    if not skip_reshape:
        raise ValueError("Florence-2 always passes pre-reshaped attention inputs")
    b, _, _, dim_head = q.shape
    if mask is not None:
        if mask.ndim == 2:
            mask = mask.unsqueeze(0)
        if mask.ndim == 3:
            mask = mask.unsqueeze(1)
    out = F.scaled_dot_product_attention(
        q, k, v, attn_mask=mask, dropout_p=0.0, is_causal=False)
    if skip_output_reshape:
        return out
    return out.transpose(1, 2).reshape(b, -1, heads * dim_head)


class ProgressBar:
    """A ``comfy.utils.ProgressBar`` stand-in.

    Generation progress is reported to the user through the brokered progress
    channel by the node, not from inside the model, so the decode loop's own
    counter has nothing to publish and simply counts.
    """

    def __init__(self, total):
        self.total = int(total)
        self.current = 0

    def update(self, value=1):
        self.current += int(value)

    def update_absolute(self, value, total=None, preview=None):
        if total is not None:
            self.total = int(total)
        self.current = int(value)


__all__ = [
    "ProgressBar",
    "attention_small_input",
    "cast_to_input",
    "manual_cast",
]
