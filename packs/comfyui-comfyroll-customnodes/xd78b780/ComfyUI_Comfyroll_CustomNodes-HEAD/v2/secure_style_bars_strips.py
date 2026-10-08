"""Render-local repeated-axis artist for the pinned Matplotlib3.11.1 Agg contract.

The source's virtual cubic shape and affine resampling footprint are preserved;
only repeated RGBA storage is streamed. This does not prove a hard native heap
limit or equality to an allocated pristine512 image.
"""
import math
import matplotlib
import matplotlib.image as mimage
from matplotlib.image import AxesImage
from matplotlib.backends.backend_agg import RendererAgg
from matplotlib.transforms import Affine2D, Bbox, TransformedBbox
from .secure_matplot import np, STYLES

LIMIT = 128 * 1024 * 1024
VERSION = "3.11.1"


def compatible(values):
    """Unsupported small workloads remain on the bounded literal source path."""
    return (
        matplotlib.__version__ == VERSION
        and matplotlib.rcParams["image.origin"] == "upper"
        and matplotlib.rcParams["image.interpolation"] == "auto"
        and matplotlib.rcParams["image.interpolation_stage"] == "auto"
        and matplotlib.rcParams["image.resample"] is True
        and matplotlib.rcParams["figure.dpi"] == 100
        and matplotlib.rcParams["savefig.dpi"] in ("figure", 100)
        and matplotlib.rcParams["savefig.bbox"] is None
        and type(values["width"]) is int and type(values["height"]) is int
        and values["width"] >= 2 and values["height"] >= 2
        and values["mode"] in ("color bars", "sin wave", "gradient bars")
        and values["orientation"] in ("vertical", "horizontal")
        and values["bar_style"] in STYLES
        and type(values["bar_frequency"]) in (int, float)
        and math.isfinite(values["bar_frequency"]) and values["bar_frequency"] != 0
    )


def allocation_plan(width, height, vertical):
    """Checked before axis/figure/strip/result/PNG/output allocations.

Reserve TWO maximum contiguous RGBA strips (native-copy allowance even though
the previous Python strip is explicitly deleted),192B/output pixel for float
result/quantization/canvas/PIL/PNG/Torch/wire ownership,128B/axis sample and8MiB
fixed figure/native overhead. This is conservative accounting, not an enforced
native allocator or complete interpreter heap profile.
"""
    axis = width if vertical else height
    repeated = width * height
    max_support = max(width, height) + 6
    strip_samples = min(repeated, 2 * max_support + 1)
    strip_bytes = strip_samples * axis * 4 * 8
    pixels = width * height
    total = 2 * strip_bytes + pixels * 192 + axis * 128 + 8 * 1024 * 1024
    if total > LIMIT:
        raise ValueError("StyleBars simultaneous strip/result/renderer/PNG/output workload exceeds bound")
    return dict(width=width, height=height, axis=axis, repeated=repeated,
                max_support=max_support, strip_bytes=strip_bytes,
                output_bytes=pixels * 4 * 8, projected_bytes=total)


class _RepeatedAxisImage(AxesImage):
    """Private instance, no global artist/kernel monkeypatch or persistent data."""

    def __init__(self, ax, values, vertical, plan, style):
        rows, cols = ((plan["repeated"], plan["width"]) if vertical
                      else (plan["height"], plan["repeated"]))
        # imshow explicitly forwards resample=None (rcParams policy); direct
        # AxesImage's omitted argument instead defaults False.
        super().__init__(ax, cmap=style, origin="upper", resample=None,
                         extent=(-.5, cols-.5, rows-.5, -.5))
        self._virtual_shape = (rows, cols)
        self._axis_values = values
        self._vertical = vertical
        self._plan = plan
        self.set_data(values[None, :] if vertical else values[:, None])
        self.set_clip_path(ax.patch)
        self.set_extent(self.get_extent())

    def _contract(self):
        if (matplotlib.__version__ != VERSION or self.origin != "upper"
                or self.get_interpolation() != "auto"
                or self.get_interpolation_stage() != "auto"
                or self.get_resample() is not True or self.get_alpha() is not None
                or self.get_filterrad() != 4 or self.get_filternorm() is not True
                or not self.get_clip_on() or not self.get_transform().is_affine
                or self.axes.get_xscale() != "linear" or self.axes.get_yscale() != "linear"
                or type(self.norm) is not matplotlib.colors.Normalize):
            raise ValueError("StyleBars native artist/interpolation/alpha contract unavailable")

    def make_image(self, renderer, magnification=1.0, unsampled=False):
        self._contract()
        if type(renderer) is not RendererAgg:
            raise ValueError("StyleBars native Agg renderer contract unavailable")
        if unsampled or magnification != 1.0:
            raise ValueError("StyleBars native renderer magnification contract unavailable")
        rows, cols = self._virtual_shape
        x1, x2, y1, y2 = self.get_extent()
        bbox = Bbox(np.array([[x1, y1], [x2, y2]]))
        transformed = TransformedBbox(bbox, self.get_transform())
        clip = self.get_clip_box() or self.axes.bbox
        clipped = Bbox.intersection(transformed, clip)
        if clipped is None:
            return None, 0, 0, None
        ext = clipped.extents * magnification
        rounded = Bbox.from_extents([
            np.floor(ext[0]+.5), np.ceil(ext[1]-.5-1e-8),
            np.floor(ext[2]+.5+1e-8), np.ceil(ext[3]-.5)])
        if not rounded.width or not rounded.height:
            return None, 0, 0, None
        t0 = Affine2D().translate(0, -rows).scale(1, -1)
        t0 += (Affine2D().scale(bbox.width / cols, bbox.height / rows)
               .translate(bbox.x0, bbox.y0) + self.get_transform())
        transform = t0 + Affine2D().scale(magnification).translate(-rounded.x0, -rounded.y0)
        shape = (int(rounded.height), int(rounded.width))
        if shape != (self._plan["height"], self._plan["width"]):
            raise ValueError("StyleBars native canvas shape contract unavailable")
        matrix = transform.get_matrix()
        if (not np.isfinite(matrix).all() or matrix[0, 1] != 0 or matrix[1, 0] != 0
                or matrix[0, 0] <= 0 or matrix[1, 1] >= 0):
            raise ValueError("StyleBars native axis transform contract unavailable")
        inverse = transform.inverted()
        sx = abs(inverse.get_matrix()[0, 0])
        sy = abs(inverse.get_matrix()[1, 1])
        # Full source dimensions imply RGBA-stage downsampling and Hanning.
        if (min(sx, sy) < .5 or max(sx, sy) <= 1
                or max(sx, sy) > max(self._plan["width"], self._plan["height"]) + 2):
            raise ValueError("StyleBars native downsampling scale contract unavailable")
        support = math.ceil(max(sx, sy)) + 4
        if support > self._plan["max_support"]:
            raise ValueError("StyleBars support exceeds preflight")
        rgba_axis = self.to_rgba(self._axis_values)
        if (rgba_axis.shape != (self._plan["axis"], 4) or rgba_axis.dtype != np.float64
                or not np.isfinite(rgba_axis).all() or not np.all(rgba_axis[:, 3] == 1)):
            raise ValueError("StyleBars native colormap/alpha contract unavailable")
        output = np.zeros(shape + (4,), dtype=np.float64)
        try:
            length = shape[0] if self._vertical else shape[1]
            repeated = rows if self._vertical else cols
            for index in range(length):
                point = ((.5, index+.5) if self._vertical else (index+.5, .5))
                center = inverse.transform(point)[1 if self._vertical else 0]
                low = max(0, int(math.floor(center))-support)
                high = min(repeated, int(math.ceil(center))+support+1)
                if high <= low or (high-low) * self._plan["axis"] * 32 > self._plan["strip_bytes"]:
                    raise ValueError("StyleBars strip exceeds preflight")
                # Previous strip has already been explicitly deleted.
                tile = (np.tile(rgba_axis[None, :, :], (high-low, 1, 1)) if self._vertical
                        else np.tile(rgba_axis[:, None, :], (1, high-low, 1)))
                try:
                    local = (Affine2D().translate(0, low) + transform
                             + Affine2D().translate(0, -index)) if self._vertical else (
                             Affine2D().translate(low, 0) + transform
                             + Affine2D().translate(-index, 0))
                    native_shape = (1, shape[1]) if self._vertical else (shape[0], 1)
                    row = mimage._resample(self, tile, native_shape, local)
                    try:
                        if self._vertical:
                            output[index:index+1] = row
                        else:
                            output[:, index:index+1] = row
                    finally:
                        del row
                finally:
                    del tile
            np.divide(output[:, :, :3], output[:, :, 3:], out=output[:, :, :3],
                      where=output[:, :, 3:] != 0)
            rendered = self.to_rgba(output, bytes=True, norm=False)
        finally:
            del output
            del rgba_axis
        return rendered, rounded.x0/magnification, rounded.y0/magnification, transform


def add_artist(ax, values, vertical, plan, style):
    ax.set_aspect("auto")
    artist = _RepeatedAxisImage(ax, values, vertical, plan, style)
    ax.add_image(artist)
    return artist
