"""Shape metadata of a ref, answered by the host: no buffer enters the guest.

Upstream's *SizeAndCount nodes read nothing but ``.shape`` and return their
input object unchanged. A converted node therefore needs neither ``raw()`` nor
``_from_raw()``: it asks the host for the shape through the public
``Ref.describe()`` (engine-scoped ``inspect`` capability, present on guest
bases 0b86765f and 0cd9adec) and returns the input ref itself.

``describe()`` is used rather than ``ImageRef.spatial_shape()`` /
``batch_size()`` because it reports the full shape of any tensor, exactly as
upstream's ``.shape`` does: the typed IMAGE ops refuse batches over 4096, a
channel count outside 1/3/4 and HWC tensors, all of which upstream accepts, and
MASK and LATENT have no typed shape op at all.
"""
from __future__ import annotations


class ShapeOnly:
    """Stand-in for a tensor whose upstream consumer reads only ``.shape``."""

    __slots__ = ("shape",)

    def __init__(self, shape) -> None:
        self.shape = tuple(shape)


async def described_shape(ref) -> tuple[int, ...]:
    """``ref``'s tensor shape (a LATENT's ``samples`` shape), read on the host."""
    info = await ref.describe()
    shape = info.get("shape") if isinstance(info, dict) else None
    if not isinstance(shape, (list, tuple)) or any(
            isinstance(dim, bool) or not isinstance(dim, int) for dim in shape):
        raise TypeError(
            f"{type(ref).__name__} does not hold a tensor whose shape the host "
            f"can describe (got {info!r:.200})")
    return tuple(shape)
