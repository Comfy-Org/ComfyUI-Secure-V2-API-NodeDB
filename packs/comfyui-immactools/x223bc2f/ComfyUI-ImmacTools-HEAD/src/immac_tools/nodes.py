from typing_extensions import override
from collections.abc import Sequence

from comfy_api.latest import io
from .forwarding_nodes import ForwardAnyNode, ForwardConditioningNode, ForwardModelNode
import torch
import numpy as np

class ConcatenateSigmasNode(io.ComfyNode):
    """
    ConcatenateSigmasNode
    A ComfyUI-compatible node that concatenates two "sigmas" inputs into a single 1D sigma tensor.

    Inputs:
    - sigmas_1: torch.Tensor or tensor-like (1D or scalar). May be None.
    - sigmas_2: torch.Tensor or tensor-like (1D or scalar). May be None.

    Output:
    - io.NodeOutput containing the concatenated torch.Tensor, or the single non-None input, or None if both inputs are None.

    Notes and edge cases:
    - If inputs have more than 1 dimension, concatenation occurs along the first dimension; the remaining dimensions must match.
    - If inputs are on different devices or have incompatible dtypes/shapes, torch.cat will raise an error. Convert or move tensors to a common device/dtype before feeding them to this node if necessary.
    - The node's check_lazy_status does not request any additional lazy evaluation; all provided inputs are processed directly.

    Edge cases and recommendations:
    - When inputs are on different devices (CPU vs GPU) or have different dtypes, callers should coerce them to a common device/dtype before connecting to this node; otherwise torch.cat will raise.
    - If inputs have trailing dimensions (i.e. dim() > 1), those trailing shapes must match exactly; the node will concatenate along dim=0.

    Examples:
    - Given sigmas_1 = torch.tensor([0.1, 0.2]) and sigmas_2 = torch.tensor([0.3]), the output is tensor([0.1, 0.2, 0.3]).
    - Given sigmas_1 = 0.5 (scalar) and sigmas_2 = [0.6, 0.7], the output is tensor([0.5, 0.6, 0.7]) after conversion and unsqueezing.
    """
    @classmethod
    def define_schema(cls) -> io.Schema:
        """
            Return a schema which contains all information about the node.
            Some types: "Model", "Vae", "Clip", "Conditioning", "Latent", "Image", "Int", "String", "Float", "Combo".
            For outputs the "io.Model.Output" should be used, for inputs the "io.Model.Input" can be used.
            The type can be a "Combo" - this will be a list for selection.
        """
        return io.Schema(
            node_id="ConcatenateSigmasImmacTools",
            display_name="Concatenate Sigmas Node",
            category="Example",
            inputs=[
                io.Sigmas.Input("sigmas_1"),
                io.Sigmas.Input("sigmas_2"),
            ],
            outputs=[
                io.Sigmas.Output(),
            ],
        )

    @classmethod
    def check_lazy_status(cls, sigmas_1, sigmas_2):
        """
            Return a list of input names that need to be evaluated.

            This function will be called if there are any lazy inputs which have not yet been
            evaluated. As long as you return at least one field which has not yet been evaluated
            (and more exist), this function will be called again once the value of the requested
            field is available.

            Any evaluated inputs will be passed as arguments to this function. Any unevaluated
            inputs will have the value None.
        """
        return []

    @classmethod
    def execute(cls, sigmas_1, sigmas_2) -> io.NodeOutput:
        if sigmas_1 is None:
            return io.NodeOutput(sigmas_2)
        if sigmas_2 is None:
            return io.NodeOutput(sigmas_1)

        if not isinstance(sigmas_1, torch.Tensor):
            sigmas_1 = torch.as_tensor(sigmas_1)
        if not isinstance(sigmas_2, torch.Tensor):
            sigmas_2 = torch.as_tensor(sigmas_2)

        if sigmas_1.dim() == 0:
            sigmas_1 = sigmas_1.unsqueeze(0)
        if sigmas_2.dim() == 0:
            sigmas_2 = sigmas_2.unsqueeze(0)

        # If the last value of sigmas_1 is very close to the first value of sigmas_2,
        # avoid duplicating that boundary sigma so the concatenated schedule has
        # exactly one sample at the splice point.
        # Ensure both tensors are on the same device/dtype for comparison
        try:
            sig1_last = sigmas_1[-1]
            sig2_first = sigmas_2[0]
        except Exception:
            # If indexing fails (shouldn't for non-empty 1D tensors), fall back to simple concat
            out = torch.cat((sigmas_1, sigmas_2), dim=0)
            return io.NodeOutput(out)

        # Move comparison tensors to a common dtype/device for isclose
        comp_dtype = sigmas_1.dtype
        comp_device = sigmas_1.device
        if sigmas_2.device != comp_device:
            sigmas_2 = sigmas_2.to(comp_device)
            sig2_first = sig2_first.to(comp_device)
        if sigmas_2.dtype != comp_dtype:
            sigmas_2 = sigmas_2.to(dtype=comp_dtype)
            sig2_first = sig2_first.to(dtype=comp_dtype)

        # Use a relative tolerance based on magnitude plus a small absolute tolerance
        atol = 1e-6
        rtol = 1e-4
        if torch.isclose(sig1_last, sig2_first, atol=atol, rtol=rtol):
            # Concatenate but skip the duplicated first value of sigmas_2
            if sigmas_2.numel() > 1:
                out = torch.cat((sigmas_1, sigmas_2[1:]), dim=0)
            else:
                # sigmas_2 only contained the duplicated boundary, so result is just sigmas_1
                out = sigmas_1.clone()
        else:
            out = torch.cat((sigmas_1, sigmas_2), dim=0)

        return io.NodeOutput(out)

    """
        The node will always be re executed if any of the inputs change but
        this method can be used to force the node to execute again even when the inputs don't change.
        You can make this node return a number or a string. This value will be compared to the one returned the last time the node was
        executed, if it is different the node will be executed again.
        This method is used in the core repo for the LoadImage node where they return the image hash as a string, if the image hash
        changes between executions the LoadImage node is executed again.
    """

    #@classmethod
    #def fingerprint_inputs(s, image, string_field, int_field, float_field, print_to_screen):
    #    return ""

class SpliceSigmasAtNode(io.ComfyNode):
    """
    Splice two sigma schedules at a relative point of the first schedule.

    Inputs:
        - sigmas_a: first sigma schedule (descending)
        - sigmas_b: second sigma schedule
        - boundary: float in [0.0, 1.0] representing where to splice relative to the first sigma (0 -> start, 1 -> end)

    Outputs:
        - full concatenated sigma (first_part + second_part without duplicated boundary)
        - first_part (prefix of sigmas_a up to the boundary, boundary appended if needed)
        - second_part (boundary prepended then suffix of sigmas_b <= boundary)
    
        Edge cases and behavior:
        - If `boundary` is outside [0.0, 1.0], it is clamped to the range [0.0, 1.0].
        - The `boundary` value is interpreted as a fraction of the starting sigma value (sigmas_a[0] * (1.0 - boundary)).
            For example, `boundary=0.0` results in a boundary equal to `sigmas_a[0]` (i.e. start), and `boundary=1.0` results in a boundary of 0.
        - If no values in `sigmas_a` are >= boundary value, `first_part` will be empty (unless `include_boundary` is True, in which case the boundary value will be appended).
        - If no values in `sigmas_b` are <= boundary value, `second_part` will be empty (unless `include_boundary` is True, in which case the boundary value will be prepended).
        - When `include_boundary` is True but both schedules do not contain the boundary, the boundary will be inserted into both `first_part` and `second_part` (so `full` will contain the boundary once).
        - If the inputs are on different devices or have different dtypes, callers should coerce them to a common device/dtype before connecting to this node; the node assumes inputs are compatible for comparisons and concatenation.
    """
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SpliceSigmasAtImmacTools",
            display_name="Splice Sigmas At %",
            category="Example",
            inputs=[
            io.Sigmas.Input("sigmas_a"),
            io.Sigmas.Input("sigmas_b"),
            io.Float.Input("boundary", default=0.5, min=0.0, max=1.0, step=0.005),
            io.Boolean.Input(
                "include_boundary",
                display_name="include boundary?",
                tooltip="If enabled, the boundary sigma is included at the splice point, which can smooth transitions but adds an extra step."
            )
            ],
            outputs=[
            io.Sigmas.Output("full","spliced_sigmas"),
            io.Sigmas.Output("first_part","first_part"),
            io.Sigmas.Output("second_part","second_part"),
            ],
        )

    @classmethod
    def check_lazy_status(cls, sigmas_a, sigmas_b, boundary, include_boundary):
        # Signature matches the defined inputs: (sigmas_a, sigmas_b, boundary, include_boundary)
        return []

    @classmethod
    def execute(cls, sigmas_a, sigmas_b, boundary, include_boundary) -> io.NodeOutput:
        # If either schedule missing, pass through sensible defaults
        if sigmas_a is None and sigmas_b is None:
            return io.NodeOutput(None, None, None)
        if sigmas_a is None:
            return io.NodeOutput(sigmas_b, None, sigmas_b)
        if sigmas_b is None:
            return io.NodeOutput(sigmas_a, sigmas_a, None)

        # Ensure tensors and 1D
        if not isinstance(sigmas_a, torch.Tensor):
            sigmas_a = torch.as_tensor(sigmas_a)
        if not isinstance(sigmas_b, torch.Tensor):
            sigmas_b = torch.as_tensor(sigmas_b)
        if sigmas_a.dim() == 0:
            sigmas_a = sigmas_a.unsqueeze(0)
        if sigmas_b.dim() == 0:
            sigmas_b = sigmas_b.unsqueeze(0)

        # Clamp boundary to [0,1]
        try:
            p = float(boundary)
        except Exception:
            p = 0.5
        p = max(0.0, min(1.0, p))

        # Boundary value: interpreted as the remaining fraction of the initial sigma
        # (example: boundary=0.5 => boundary = sigmas_a[0] * 0.5)
        start_val = float(sigmas_a[0].item())
        boundary_val = start_val * (1.0 - p)

        dtype = sigmas_a.dtype
        device = sigmas_a.device
        boundary_tensor = torch.as_tensor([boundary_val], dtype=dtype, device=device)

        # Build first part: all values from sigmas_a >= boundary, then ensure boundary appended if needed
        mask_a = sigmas_a >= boundary_val
        if mask_a.any():
            last_idx = torch.nonzero(mask_a, as_tuple=True)[0][-1].item()
            first_part = sigmas_a[: last_idx + 1].clone()
        else:
            first_part = torch.empty((0,), dtype=dtype, device=device)

        # Build second part: include values from sigmas_b <= boundary
        mask_b = sigmas_b <= boundary_val
        if mask_b.any():
            suffix_b = sigmas_b[mask_b].clone()
        else:
            suffix_b = torch.empty((0,), dtype=dtype, device=device)

        if include_boundary:
            # Append boundary to first_part if not present
            if first_part.numel() == 0 or not torch.isclose(first_part[-1], boundary_tensor[0], atol=1e-6):
                first_part = torch.cat((first_part, boundary_tensor))
            # Prepend boundary to second_part
            second_part = torch.cat((boundary_tensor, suffix_b))
            # Concatenate without duplicating the boundary value
            if second_part.numel() > 1:
                full = torch.cat((first_part, second_part[1:]))
            else:
                full = torch.cat((first_part, second_part[0:0]))  # just first_part if second_part has only boundary
        else:
            # No boundary is added, so just use first_part and suffix_b directly
            second_part = suffix_b
            # Concatenate first_part and second_part directly
            full = torch.cat((first_part, second_part))

        return io.NodeOutput(full, first_part, second_part)

class ResampleSigmas(io.ComfyNode):
    """
    ResampleSigmas

    Resample / re-interpret a sigma schedule to a requested number of steps.

        Inputs:
        - sigmas: torch.Tensor or tensor-like (1D or scalar). May be None.
        - steps: int - number of steps to produce (clamped to >= 1)

        Output:
        - io.NodeOutput containing the resampled torch.Tensor (shape: [steps + 1, ...]) or None if input sigmas is None

        Behavior:
        - The node interprets `steps` as the number of intervals; the returned schedule includes both endpoints and
            therefore has length `steps + 1`.
        - If `sigmas` is scalar, the output is a length-`steps + 1` tensor filled with that value.
        - If `sigmas` is 1D (T,), output is produced by linear interpolation of the curve defined by the T points at
            positions [0..T-1] sampled at `steps + 1` evenly spaced positions in that same range.
    - If `sigmas` has trailing dimensions (T, ...), interpolation is applied across the first (time) dimension and
      trailing dimensions are preserved.
    - Dtype and device of the output match the input.
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ResampleSigmasImmacTools",
            display_name="Resample Sigmas",
            category="Example",
            inputs=[
                io.Sigmas.Input("sigmas"),
                io.Int.Input("steps", default=10, min=1),
            ],
            outputs=[
                io.Sigmas.Output(),
            ],
        )

    @classmethod
    def check_lazy_status(cls, sigmas, steps):
        return []

    @classmethod
    def execute(cls, sigmas, steps) -> io.NodeOutput:
        # Pass-throughs
        if sigmas is None:
            return io.NodeOutput(None)

        # Ensure steps is an int and at least 1
        try:
            s = int(steps)
        except Exception:
            s = 1
        s = max(1, s)
        # We interpret `steps` as the number of intervals; the returned sigma schedule
        # should include both endpoints, so it has length `s + 1`.
        out_len = s + 1

        # Ensure tensor
        if not isinstance(sigmas, torch.Tensor):
            sigmas = torch.as_tensor(sigmas)

        # Defensive: ensure we have a floating dtype for linspace and interpolation.
        # If sigmas is integer or non-floating, cast to the default floating dtype
        # while keeping device. This prevents unexpected integer linspace behavior.
        if not torch.is_floating_point(sigmas):
            sigmas = sigmas.to(dtype=torch.get_default_dtype())

        # If scalar -> repeat the single value for each timestep including endpoints
        if sigmas.dim() == 0:
            out = sigmas.unsqueeze(0).repeat(out_len)
            return io.NodeOutput(out)

        # Work along first dimension (time). Preserve trailing dims.
        T = sigmas.shape[0]
        dtype = sigmas.dtype
        device = sigmas.device

        # If only one input time point, just repeat that point for each output timestep
        if T == 1:
            out = sigmas.unsqueeze(0).repeat(out_len, *([1] * (sigmas.dim() - 1)))
            return io.NodeOutput(out)

        # Flatten trailing dims so we can vectorize interpolation
        trailing_shape = sigmas.shape[1:]
        D = 1
        for d in trailing_shape:
            D *= d
        sig_flat = sigmas.contiguous().view(T, D)

        # Source x positions and target x positions
        src_x = torch.linspace(0.0, float(T - 1), steps=T, dtype=dtype, device=device)
        # Target positions: produce `out_len` samples evenly spaced across [0, T-1]
        tgt_x = torch.linspace(0.0, float(T - 1), steps=out_len, dtype=dtype, device=device)

        # For each target position find right-side index
        idx = torch.searchsorted(src_x, tgt_x)
        # idx in [0..T]; left = clamp(idx-1,0), right = clamp(idx, T-1)
        right = torch.clamp(idx, 0, T - 1)
        left = torch.clamp(right - 1, 0, T - 1)

        xL = src_x[left]
        xR = src_x[right]

        # Gather yL/yR -> shape (out_len, D)
        yL = sig_flat[left]  # indexing with (out_len,) yields (out_len, D)
        yR = sig_flat[right]

        # Avoid division by zero where xR == xL (shouldn't happen except maybe at boundaries)
        denom = (xR - xL)
        # Where denom==0, set weight to 0 to pick yL
        denom_safe = denom.clone()
        denom_safe[denom_safe == 0] = 1.0
        weight = ((tgt_x - xL) / denom_safe).unsqueeze(1)
        weight = weight.clamp(0.0, 1.0)

        out_flat = yL * (1.0 - weight) + yR * weight

        out = out_flat.view((out_len,) + trailing_shape)

        return io.NodeOutput(out)


class SkipEveryNthImages(io.ComfyNode):
    """
    Skip every nth image in a batch.

    Accepts a batch of images (list/tuple of frames or torch tensor with batch dim) and drops the nth item while preserving order of the rest. Outputs the filtered batch and the indices that were removed.
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SkipEveryNthImagesImmacTools",
            display_name="Skip Every Nth Image",
            category="Example",
            inputs=[
                io.AnyType.Input("images", display_name="images", tooltip="Batch of images/frames (list or tensor)."),
                io.Int.Input("n", default=2, min=1, tooltip="Skip every nth image; n<=0 yields empty output."),
            ],
            outputs=[
                io.AnyType.Output("filtered", display_name="images"),
                io.AnyType.Output("removed_indices", display_name="removed indices"),
            ],
        )

    @classmethod
    def check_lazy_status(cls, images, n):
        return []

    @classmethod
    def execute(cls, images, n) -> io.NodeOutput:
        # Normalize n; if invalid, treat as <=0 and drop everything
        try:
            step = int(n)
        except Exception:
            step = 0

        # Torch tensor batch: slice along batch dim
        if isinstance(images, torch.Tensor):
            total = images.shape[0] if images.dim() > 0 else 0
            if total == 0 or step <= 0:
                empty = images.new_empty((0,) + tuple(images.shape[1:]))
                removed = list(range(total))
                return io.NodeOutput(empty, removed)

            keep_mask = torch.ones(total, dtype=torch.bool, device=images.device)
            keep_mask[step - 1 :: step] = False  # zero-based index for the nth elements
            filtered = images[keep_mask] if total > 0 else images.new_empty((0,) + tuple(images.shape[1:]))
            removed = [i for i in range(total) if (i + 1) % step == 0]
            return io.NodeOutput(filtered, removed)

        # Sequence (list/tuple) batch: iterate and filter
        if isinstance(images, Sequence) and not isinstance(images, (str, bytes)):
            total = len(images)
            if step <= 0:
                removed = list(range(total))
                return io.NodeOutput([], removed)

            kept = []
            removed = []
            for idx, img in enumerate(images):
                if (idx + 1) % step == 0:
                    removed.append(idx)
                else:
                    kept.append(img)
            return io.NodeOutput(kept, removed)

        # Fallback: unsupported type, pass through unchanged
        return io.NodeOutput(images, [])


# ---------------------------------------------------------------------------
# Histogram matching helpers
# ---------------------------------------------------------------------------

def _match_histograms_channel(src: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Match the histogram of *src* to that of *ref*.

    Both arrays must be float32 in [0, 1] and can have any shape.
    The mapping is built by aligning the cumulative distribution functions (CDFs)
    of the two arrays.  We quantise to uint16 (65 536 levels) which gives
    sub-0.002 % precision while keeping the LUT small and fast.

    Returns a float32 array with the same shape as *src*.
    """
    src_u = np.clip(np.round(src * 65535.0), 0, 65535).astype(np.uint16)
    ref_u = np.clip(np.round(ref * 65535.0), 0, 65535).astype(np.uint16)

    src_hist = np.bincount(src_u.ravel(), minlength=65536)
    ref_hist = np.bincount(ref_u.ravel(), minlength=65536)

    src_cdf = np.cumsum(src_hist, dtype=np.float64) / float(src_u.size)
    ref_cdf = np.cumsum(ref_hist, dtype=np.float64) / float(ref_u.size)

    # For each source quantisation level, find the reference level whose CDF
    # value is closest (i.e. has the same mass to the left).
    lut = np.searchsorted(ref_cdf, src_cdf, side="left")
    lut = np.clip(lut, 0, 65535).astype(np.uint16)

    matched_u = lut[src_u]
    return matched_u.astype(np.float32) / 65535.0


# ---- pure-numpy sRGB <-> linear <-> XYZ <-> LAB helpers (D65) ----

def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def _linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1.0 / 2.4) - 0.055)

_M_RGB_TO_XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
], dtype=np.float64)

_M_XYZ_TO_RGB = np.array([
    [ 3.2404542, -1.5371385, -0.4985314],
    [-0.9692660,  1.8760108,  0.0415560],
    [ 0.0556434, -0.2040259,  1.0572252],
], dtype=np.float64)

_D65 = np.array([0.95047, 1.00000, 1.08883], dtype=np.float64)


def _f_lab(t: np.ndarray) -> np.ndarray:
    delta = 6.0 / 29.0
    return np.where(t > delta ** 3, np.cbrt(t), t / (3.0 * delta ** 2) + 4.0 / 29.0)


def _f_lab_inv(t: np.ndarray) -> np.ndarray:
    delta = 6.0 / 29.0
    return np.where(t > delta, t ** 3, 3.0 * delta ** 2 * (t - 4.0 / 29.0))


def _rgb_to_lab(img: np.ndarray) -> np.ndarray:
    """Convert [H, W, 3] float32 sRGB image to CIE LAB."""
    lin = _srgb_to_linear(img.astype(np.float64))
    xyz = lin @ _M_RGB_TO_XYZ.T
    xyz_n = xyz / _D65
    f = _f_lab(xyz_n)
    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1).astype(np.float32)


def _lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    """Convert [H, W, 3] float32 CIE LAB image to sRGB [0, 1] float32."""
    lab64 = lab.astype(np.float64)
    L, a, b = lab64[..., 0], lab64[..., 1], lab64[..., 2]
    fy = (L + 16.0) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0
    xyz = np.stack([_f_lab_inv(fx), _f_lab_inv(fy), _f_lab_inv(fz)], axis=-1) * _D65
    lin = xyz @ _M_XYZ_TO_RGB.T
    return np.clip(_linear_to_srgb(lin), 0.0, 1.0).astype(np.float32)


class MatchContrastNode(io.ComfyNode):
    """
    MatchContrastNode

    Adjusts the contrast (tonal distribution) of *image* to match that of
    *reference* using CDF-based histogram matching.

    Inputs:
        image     – the image whose contrast will be adjusted  [B, H, W, C]
        reference – the image whose contrast is the target      [B, H, W, C]
        channel_mode:
            "rgb"       – match each R/G/B channel independently
            "luminance" – match only the L channel in CIE LAB space
                          (preserves the hue and saturation of *image*,
                           changes only brightness/contrast)

    Output:
        Adjusted image with the same spatial dimensions as *image*.

    Notes:
        • If *reference* contains fewer frames than *image*, the first frame
          of *reference* is used for all source frames.
        • The matching is done per-frame (not across the batch).
        • No external dependencies beyond NumPy and PyTorch.
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MatchContrastImmacTools",
            display_name="Match Contrast",
            category="image/adjust",
            inputs=[
                io.Image.Input("image", display_name="image"),
                io.Image.Input("reference", display_name="reference"),
                io.Combo.Input(
                    "channel_mode",
                    options=["rgb", "luminance"],
                    default="luminance",
                    display_name="channel mode",
                    tooltip=(
                        "rgb: match each R/G/B channel independently.  "
                        "luminance: match only the L channel in CIE LAB "
                        "(keeps source colours, adjusts brightness/contrast)."
                    ),
                ),
                io.Float.Input(
                    "strength",
                    default=1.0,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                    display_name="strength",
                    tooltip="Blend between the original image (0.0) and the fully matched image (1.0).",
                ),
            ],
            outputs=[
                io.Image.Output(display_name="image"),
            ],
        )

    @classmethod
    def check_lazy_status(cls, image, reference, channel_mode, strength):
        return []

    @classmethod
    def execute(cls, image: torch.Tensor, reference: torch.Tensor, channel_mode: str, strength: float) -> io.NodeOutput:
        # image / reference: [B, H, W, C] float32 in [0, 1]
        B = image.shape[0]
        ref_B = reference.shape[0]
        s = float(np.clip(strength, 0.0, 1.0))

        out_frames: list[np.ndarray] = []

        for i in range(B):
            src_np = image[i].cpu().numpy()               # [H, W, C]
            # Broadcast reference: use frame i if available, else frame 0
            ref_np = reference[min(i, ref_B - 1)].cpu().numpy()  # [H, W, C]

            if channel_mode == "luminance":
                matched = cls._match_luminance(src_np, ref_np)
            else:  # "rgb"
                matched = cls._match_rgb(src_np, ref_np)

            # Blend: 0.0 = original, 1.0 = fully matched
            blended = src_np * (1.0 - s) + matched * s
            out_frames.append(blended)

        result = torch.from_numpy(np.stack(out_frames, axis=0)).to(image.device)
        return io.NodeOutput(result)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _match_rgb(src: np.ndarray, ref: np.ndarray) -> np.ndarray:
        """Match each RGB channel of *src* to *ref* independently."""
        C = src.shape[-1]
        channels = [
            _match_histograms_channel(src[..., c], ref[..., c])
            for c in range(C)
        ]
        return np.stack(channels, axis=-1)

    @staticmethod
    def _match_luminance(src: np.ndarray, ref: np.ndarray) -> np.ndarray:
        """Match only the LAB L-channel of *src* to *ref*; keep src a/b."""
        src_lab = _rgb_to_lab(src)   # [H, W, 3]
        ref_lab = _rgb_to_lab(ref)

        # Normalise L from [0, 100] to [0, 1] for the histogram helper
        L_src = src_lab[..., 0] / 100.0
        L_ref = ref_lab[..., 0] / 100.0

        L_matched = _match_histograms_channel(L_src, L_ref) * 100.0  # back to [0,100]

        out_lab = src_lab.copy()
        out_lab[..., 0] = L_matched
        return _lab_to_rgb(out_lab)


class SwitchNode(io.ComfyNode):
    """
    SwitchNode
    A node that selects one of N optional inputs based on an integer index.
    The number of visible input slots is controlled by the `num_inputs` widget.

    Inputs:
    - num_inputs: int — how many input slots are shown (1–20).
    - index: int — which slot to return.
        * -1 always returns None (regardless of other settings).
        * Zero-indexed by default: 0 → first input, 1 → second input, …
        * When one_indexed is True: 1 → first input, 2 → second input, … (0 returns None).
    - one_indexed: bool — switches slot numbering to start at 1 instead of 0.
    - input_0 … input_19: optional AnyType slots (visibility controlled by num_inputs).

    Output:
    - The value at the selected slot, or None.
    """

    _MAX_INPUTS = 20

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SwitchImmacTools",
            display_name="Switch",
            category="immac/logic",
            inputs=[
                io.Int.Input(
                    "num_inputs",
                    default=5,
                    min=1,
                    max=cls._MAX_INPUTS,
                    display_name="# inputs",
                    tooltip="Number of visible input slots.",
                ),
                io.Int.Input(
                    "index",
                    default=0,
                    min=-1,
                    max=cls._MAX_INPUTS - 1,
                    display_name="index",
                    tooltip="Index of the input to select. -1 always returns None.",
                ),
                io.Boolean.Input(
                    "one_indexed",
                    default=False,
                    display_name="1-indexed",
                    tooltip=(
                        "When enabled, index 1 selects the first input slot. "
                        "Index 0 will return None when this is on."
                    ),
                ),
                *[
                    io.AnyType.Input(f"input_{i}", optional=True)
                    for i in range(cls._MAX_INPUTS)
                ],
            ],
            outputs=[
                io.AnyType.Output(display_name="value"),
            ],
        )

    @classmethod
    def check_lazy_status(cls, num_inputs, index, one_indexed, **kwargs):
        return []

    @classmethod
    def execute(cls, num_inputs: int, index: int, one_indexed: bool, **kwargs) -> io.NodeOutput:
        # -1 always returns None
        if index == -1:
            return io.NodeOutput(None)

        # Convert to zero-based internal slot index
        actual_index = (index - 1) if one_indexed else index

        # Negative slot (e.g. one_indexed=True and index=0) → None
        if actual_index < 0:
            return io.NodeOutput(None)

        # Out of range
        if actual_index >= num_inputs:
            return io.NodeOutput(None)

        value = kwargs.get(f"input_{actual_index}", None)
        return io.NodeOutput(value)


# Set the web directory, any .js file in that directory will be loaded by the frontend as a frontend extension
# WEB_DIRECTORY = "./somejs"

