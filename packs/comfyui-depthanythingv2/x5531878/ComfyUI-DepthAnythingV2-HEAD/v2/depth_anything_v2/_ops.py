"""Pack-side stand-in for ``comfy.ops.manual_cast``.

The vendored DepthAnythingV2 architecture was written against core's
``comfy.ops.manual_cast`` layers. A sandboxed guest cannot import ``comfy``,
and the layers are not something the host can hand over -- they are ordinary
``torch.nn`` modules whose only addition is a cast.

So the pack supplies its own. This is NOT a reimplementation of core's ops
module: only two layer types are used by this architecture (``Conv2d`` 16
times, ``Linear`` 3 times) and only one behaviour matters.

**What ``manual_cast`` does.** ``manual_cast.Linear`` / ``.Conv2d`` are
``disable_weight_init`` subclasses with ``comfy_cast_weights = True``. Their
forward casts the weight and bias to the *input's* dtype and device before
running the op, so a model whose weights are stored in one precision can be
driven with activations in another. That is exactly what this pack needs: it
loads fp16 or fp32 checkpoints and runs them under ``torch.autocast``.

``disable_weight_init`` additionally skips ``reset_parameters`` so
construction does not spend time initialising weights that the state dict is
about to overwrite. That is a load-time optimisation with no effect on
output, and it is reproduced here for the same reason.

`test_depthanything_pack_conversion.py` proves equivalence against the real
``comfy.ops.manual_cast`` layers on identical weights and inputs, rather than
asserting these are the same.
"""
import torch


class _CastWeights:
    """Cast weight/bias to the input's dtype and device, as core does."""

    def _cast(self, input):
        weight = self.weight.to(dtype=input.dtype, device=input.device)
        bias = (None if self.bias is None
                else self.bias.to(dtype=input.dtype, device=input.device))
        return weight, bias

    def reset_parameters(self):
        # Matches disable_weight_init: the state dict overwrites these anyway.
        return None


class manual_cast:
    class Linear(_CastWeights, torch.nn.Linear):
        def forward(self, input):
            weight, bias = self._cast(input)
            return torch.nn.functional.linear(input, weight, bias)

    class Conv2d(_CastWeights, torch.nn.Conv2d):
        def forward(self, input):
            weight, bias = self._cast(input)
            return self._conv_forward(input, weight, bias)


def optimized_attention(q, k, v, heads, mask=None, skip_reshape=False):
    """Pack-side equivalent of core's default ``attention_pytorch``.

    The vendored DINOv2 attention called core's ``optimized_attention``, which
    dispatches to whichever backend the host process selected. The guest
    cannot import that, and should not: backend selection is a host-wide
    policy, not something a depth model gets to reach for.

    Core's default backend IS ``scaled_dot_product_attention``, and this
    architecture only ever calls it one way -- ``skip_reshape=True``, no mask,
    no dropout, not causal -- so the pack reproduces exactly that path,
    including the output reshape core performs on the way out.

    `test_depthanything_pack_conversion.py` compares this against core's real
    ``optimized_attention`` on identical tensors.
    """
    if skip_reshape:
        b, _, _, dim_head = q.shape
    else:
        b, _, dim_head = q.shape
        dim_head //= heads
        q, k, v = (
            t.reshape(b, -1, heads, dim_head).transpose(1, 2) for t in (q, k, v)
        )

    out = torch.nn.functional.scaled_dot_product_attention(
        q, k, v, attn_mask=mask, dropout_p=0.0, is_causal=False)
    return out.transpose(1, 2).reshape(b, -1, heads * dim_head)
