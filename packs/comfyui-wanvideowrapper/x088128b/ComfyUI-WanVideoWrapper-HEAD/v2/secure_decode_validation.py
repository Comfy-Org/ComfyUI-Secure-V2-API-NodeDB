"""Exact native WanVideoDecode tile validation; stdlib-only data logic.

No positivity/coercion/tiling flag policy is added to the source comparisons.
"""

def validate_decode_tiles(tile_x, tile_y, tile_stride_x, tile_stride_y):
    if tile_x <= tile_stride_x:
        return "Tile width must be larger than the tile stride width."
    if tile_y <= tile_stride_y:
        return "Tile height must be larger than the tile stride height."
    return True

