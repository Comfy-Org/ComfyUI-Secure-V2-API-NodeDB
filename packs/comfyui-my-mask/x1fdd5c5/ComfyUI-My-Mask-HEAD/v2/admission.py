"""Shape-only preflight before materializing a managed mask."""
import math
MAX_ELEMENTS = 1_048_576
MAX_DIMENSION = 4096
MAX_PROJECTED_BYTES = 128 * 1024 * 1024
def geometry(description):
    shape = description.get("shape")
    if type(shape) is not list or not 2 <= len(shape) <= 3:
        raise ValueError("My-Mask admits rank2/rank3 dense mask geometry")
    if any(type(n) is not int or not 0 <= n <= MAX_DIMENSION for n in shape):
        raise ValueError("My-Mask dimension budget exceeded")
    elements = math.prod(shape)
    # Worst16B element snapshots, packed contours/hierarchy/points/hull,
    # uint8 conversion, source output and publication.
    projected = elements * 116 + sum(shape) * 64
    if elements > MAX_ELEMENTS or projected > MAX_PROJECTED_BYTES:
        raise ValueError("My-Mask projected ownership/work budget exceeded")
    return shape
