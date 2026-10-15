# /ComfyUI/custom_nodes/Comfyui-ColorMatchNodes/ColorMatch2Refs.py

import torch
from concurrent.futures import ThreadPoolExecutor
from comfy_api.latest import io

METHODS = ["mkl", "hm", "reinhard", "mvgd", "hm-mvgd-hm", "hm-mkl-hm"]
EASING = ["linear", "ease_in", "ease_out", "ease_in_out", "smoothstep"]
MAX_THREADS = 2
MAX_BATCH = 64
MAX_SIDE = 4096
MAX_TENSOR_ELEMENTS = 16_777_216
MAX_WORK_ELEMENTS = 33_554_432


def _validate_method(method):
    if method not in METHODS:
        # The vendor raises BaseException for invalid names, which bypasses
        # normal guest RPC error handling. Fail closed with its same message.
        raise ValueError(f"Method type '{method}' not recognized")


def _bounded_images(*images):
    total = 0
    for image in images:
        if not isinstance(image, torch.Tensor) or image.ndim != 4:
            raise TypeError("images must be BHWC tensors")
        batch, height, width, channels = image.shape
        if (
            batch > MAX_BATCH
            or height > MAX_SIDE
            or width > MAX_SIDE
            or not 1 <= channels <= 4
        ):
            raise ValueError(
                "image shape exceeds the bounded batch/spatial/channel limits"
            )
        if image.numel() > MAX_TENSOR_ELEMENTS:
            raise ValueError("image exceeds the bounded tensor-element limit")
        total += image.numel()
    if total > MAX_WORK_ELEMENTS:
        raise ValueError("images exceed the bounded total-work limit")


def _image_inputs():
    return [
        io.Image.Input("image_ref_a"),
        io.Image.Input("image_ref_b"),
        io.Image.Input("image_target"),
        io.Combo.Input("method", options=METHODS, default="mkl"),
    ]


def _strength(name, default):
    return io.Float.Input(
        name, default=default, min=0.0, max=10.0, step=0.01, optional=True
    )


class ColorMatch2Refs(io.ComfyNode):
    """
    Color-match a target image to TWO references, then blend the two matched results.
    - For each target frame: matched_A = transfer(target, ref_A, method)
                              matched_B = transfer(target, ref_B, method)
      Output = target + strength * ( blend(matched_A, matched_B, weight_a) - target )
    Where blend = weight_a * matched_A + (1 - weight_a) * matched_B
    """

    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)
    DESCRIPTION = """"""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ColorMatch2Refs",
            display_name="Color Match 2Refs",
            category="Elyetis/image",
            description=cls.DESCRIPTION,
            inputs=_image_inputs()
            + [
                io.Float.Input("weight_a", default=0.5, min=0.0, max=1.0, step=0.01),
                _strength("strength", 1.0),
                io.Boolean.Input("multithread", default=True, optional=True),
            ],
            outputs=[io.Image.Output(display_name="image")],
        )

    @classmethod
    def execute(
        cls,
        image_ref_a,
        image_ref_b,
        image_target,
        method,
        weight_a,
        strength=1.0,
        multithread=True,
    ):
        _validate_method(method)
        _bounded_images(image_ref_a, image_ref_b, image_target)
        try:
            from color_matcher import ColorMatcher
        except Exception:
            raise Exception(
                "Can't import color-matcher. Install it first: pip install color-matcher"
            )

        # Ensure CPU tensors for numpy interop
        image_ref_a = image_ref_a.cpu()
        image_ref_b = image_ref_b.cpu()
        image_target = image_target.cpu()

        batch_size = image_target.size(0)

        # Squeeze potential singleton batch dims for numpy output, but keep indexing logic
        refs_a = image_ref_a.squeeze()
        refs_b = image_ref_b.squeeze()
        targs = image_target.squeeze()

        ref_a_np = refs_a.numpy()
        ref_b_np = refs_b.numpy()
        targ_np = targs.numpy()

        # Keep weight_b as 1 - weight_a
        weight_b = 1.0 - float(weight_a)

        def get_frame(arr, i, total_b, arr_b):
            """
            Helper to pick the right frame if 'arr' is batched (batch==total_b) or single (batch==1).
            - If arr batch == 1, reuse the single reference for all i.
            - Else, return arr[i].
            """
            if arr_b == 1:
                return arr
            # arr is expected shape [B, H, W, C] once squeezed might be [H, W, C] if B==1
            # Here we assume original (B, H, W, C), so when batch>1, no squeeze removed B.
            return arr[i]

        # Resolve batch sizes for refs
        ref_a_batch = image_ref_a.size(0)
        ref_b_batch = image_ref_b.size(0)

        def process(i):
            cm = ColorMatcher()

            targ_i = targ_np if batch_size == 1 else image_target[i].cpu().numpy()
            ref_a_i = ref_a_np if ref_a_batch == 1 else image_ref_a[i].cpu().numpy()
            ref_b_i = ref_b_np if ref_b_batch == 1 else image_ref_b[i].cpu().numpy()

            try:
                matched_a = cm.transfer(src=targ_i, ref=ref_a_i, method=method)
            except Exception as e:
                print(f"[ColorMatch2Refs] Thread {i} ref A failed: {e}")
                matched_a = targ_i  # fallback: no change

            try:
                matched_b = cm.transfer(src=targ_i, ref=ref_b_i, method=method)
            except Exception as e:
                print(f"[ColorMatch2Refs] Thread {i} ref B failed: {e}")
                matched_b = targ_i  # fallback: no change

            # Blend the two matched results
            blended = weight_a * matched_a + weight_b * matched_b

            # Apply 'strength' pull toward the blended result
            out = targ_i + strength * (blended - targ_i)

            return torch.from_numpy(out)

        if multithread and batch_size > 1:
            max_threads = min(MAX_THREADS, batch_size)
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                outs = list(executor.map(process, range(batch_size)))
        else:
            outs = [process(i) for i in range(batch_size)]

        out = torch.stack(outs, dim=0).to(torch.float32)
        out.clamp_(0, 1)
        return io.NodeOutput(out)


class ColorMatchBlendAutoWeights(io.ComfyNode):
    """
    Color-match a *batch* of target images to TWO references, with weight_a
    automatically changing per frame across the batch.

    Default ramp (batch size N):
        i = 0 .......... N-1
        weight_a(i) = 1 - i/(N-1)   (=> 1.00 ... 0.00)

    You can customize the ramp via start_weight_a/end_weight_a and easing.

    Output per frame:
        matched_a = transfer(target_i, ref_A, method)
        matched_b = transfer(target_i, ref_B, method)
        blended   = weight_a * matched_a + (1 - weight_a) * matched_b
        out_i     = target_i + strength * (blended - target_i)
    """

    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    DESCRIPTION = """
Auto-weighted two-reference color-match for batches.
- First frame leans to Ref A, last frame to Ref B (by default 1→0 linearly).
- Optional easing and start/end weights for custom ramps.
Requires: pip install color-matcher
"""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ColorMatchBlendAutoWeights",
            display_name="Color Match 2Refs Blend AutoWeights",
            category="Elyetis/image",
            description=cls.DESCRIPTION,
            inputs=_image_inputs()
            + [
                io.Combo.Input(
                    "ref_a_batch_mode",
                    options=["first frame", "last frame"],
                    default="last frame",
                    optional=True,
                ),
                io.Combo.Input(
                    "ref_b_batch_mode",
                    options=["first frame", "last frame"],
                    default="first frame",
                    optional=True,
                ),
                _strength("strength", 1.0),
                io.Combo.Input(
                    "strength_mode",
                    options=["constant", "u_shape"],
                    default="constant",
                    optional=True,
                ),
                _strength("mid_strength", 0.5),
                io.Combo.Input(
                    "strength_easing", options=EASING, default="linear", optional=True
                ),
                io.Boolean.Input("multithread", default=True, optional=True),
                io.Float.Input(
                    "start_weight_a",
                    default=1.0,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                    optional=True,
                ),
                io.Float.Input(
                    "end_weight_a",
                    default=0.0,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                    optional=True,
                ),
                io.Combo.Input(
                    "easing", options=EASING, default="linear", optional=True
                ),
                io.Float.Input(
                    "ease_power", default=2.0, min=1.0, max=5.0, step=0.1, optional=True
                ),
                io.Boolean.Input("debug_print", default=False, optional=True),
            ],
            outputs=[io.Image.Output(display_name="image")],
        )

    @staticmethod
    def _ease(t, mode, p):
        # t in [0,1]
        if mode == "linear":
            return t
        if mode == "smoothstep":
            # classic smoothstep
            return t * t * (3 - 2 * t)
        # power-based easings
        if mode == "ease_in":
            return t**p
        if mode == "ease_out":
            return 1.0 - (1.0 - t) ** p
        if mode == "ease_in_out":
            # symmetric ease with power p
            if t < 0.5:
                return 0.5 * (2 * t) ** p
            else:
                return 1.0 - 0.5 * (2 * (1.0 - t)) ** p
        return t

    @classmethod
    def execute(
        cls,
        image_ref_a,
        image_ref_b,
        image_target,
        method,
        strength=1.0,
        strength_mode="constant",
        mid_strength=0.5,
        strength_easing="linear",
        multithread=True,
        start_weight_a=1.0,
        end_weight_a=0.0,
        easing="linear",
        ease_power=2.0,
        ref_a_batch_mode="last frame",
        ref_b_batch_mode="first frame",
        debug_print=False,
    ):
        _validate_method(method)
        _bounded_images(image_ref_a, image_ref_b, image_target)
        try:
            from color_matcher import ColorMatcher
        except Exception:
            raise Exception(
                "Can't import color-matcher. Install it first: pip install color-matcher"
            )

        # Ensure CPU tensors for numpy interop
        image_ref_a = image_ref_a.cpu()
        image_ref_b = image_ref_b.cpu()
        image_target = image_target.cpu()

        batch_size = int(image_target.size(0))
        if batch_size < 1:
            raise ValueError("image_target batch is empty.")

        # If a reference batch is 1, reuse it for all targets; if it equals target batch, match per-frame.
        ref_a_batch = int(image_ref_a.size(0))
        ref_b_batch = int(image_ref_b.size(0))

        # Choose reference frame index for A
        if ref_a_batch <= 1:
            ref_a_index = 0
        else:
            ref_a_index = 0 if ref_a_batch_mode == "first frame" else (ref_a_batch - 1)

        if ref_b_batch <= 1:
            ref_b_index = 0
        else:
            ref_b_index = 0 if ref_b_batch_mode == "first frame" else (ref_b_batch - 1)

        # Precompute per-frame weights
        weights_a = []
        if batch_size == 1:
            # degenerate case: just use start_weight_a
            wa = float(start_weight_a)
            weights_a.append(max(0.0, min(1.0, wa)))
        else:
            for i in range(batch_size):
                t = i / (batch_size - 1)  # 0 → 1 across the batch
                t = cls._ease(t, easing, float(ease_power))  # apply easing
                wa = (1.0 - t) * float(start_weight_a) + t * float(end_weight_a)  # lerp
                wa = max(0.0, min(1.0, wa))
                weights_a.append(wa)

        if debug_print:
            print("------ ColorMatchBlendAutoWeights DEBUG ------")
            print(
                f"[ColorMatchBlendAutoWeights] weights_a (len={batch_size}): {weights_a}"
            )
            print(f"ref_a_batch_mode = {ref_a_batch_mode}")
            print(f"ref_b_batch_mode = {ref_b_batch_mode}")
            print(f"ref_a_batch size = {ref_a_batch}")
            print(f"ref_b_batch size = {ref_b_batch}")
            print(f"Chosen ref_a_index = {ref_a_index}")
            print(f"Chosen ref_b_index = {ref_b_index}")
            print("------------------------------------------------")
        # --- Per-frame strength curve ---
        strengths = []
        if strength_mode == "constant" or batch_size == 1:
            strengths = [float(strength)] * batch_size
        else:
            # U-shape: high at start/end (strength), low in the middle (mid_strength)
            edge = float(strength)
            mid = float(mid_strength)
            half = (batch_size - 1) / 2.0 if batch_size > 1 else 0.0

            for i in range(batch_size):
                if half > 0:
                    if i <= half:
                        frac = i / half  # 0 → 1 going from start to center
                    else:
                        frac = (
                            batch_size - 1 - i
                        ) / half  # 0 → 1 going from end to center
                else:
                    frac = 0.0

                # optional easing for the U-shape
                frac = cls._ease(frac, strength_easing, float(ease_power))

                # frac = 0 at edges, 1 near center
                s_i = edge + (mid - edge) * frac
                # avoid negative or insane values
                s_i = max(0.0, float(s_i))
                strengths.append(s_i)

        def process(i):
            cm = ColorMatcher()

            targ_i = image_target[i].cpu().numpy()
            # Select appropriate ref frame (broadcast if batch==1)
            ref_a_i = image_ref_a[ref_a_index].cpu().numpy()
            ref_b_i = image_ref_b[ref_b_index].cpu().numpy()

            try:
                matched_a = cm.transfer(src=targ_i, ref=ref_a_i, method=method)
            except Exception as e:
                print(f"[ColorMatchBlendAutoWeights] Thread {i} ref A failed: {e}")
                matched_a = targ_i  # fallback: no change

            try:
                matched_b = cm.transfer(src=targ_i, ref=ref_b_i, method=method)
            except Exception as e:
                print(f"[ColorMatchBlendAutoWeights] Thread {i} ref B failed: {e}")
                matched_b = targ_i  # fallback: no change

            wa = weights_a[i]
            wb = 1.0 - wa
            blended = wa * matched_a + wb * matched_b
            s = strengths[i]
            out = targ_i + float(s) * (blended - targ_i)
            return torch.from_numpy(out)

        if multithread and batch_size > 1:
            max_threads = min(MAX_THREADS, batch_size)
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                outs = list(executor.map(process, range(batch_size)))
        else:
            outs = [process(i) for i in range(batch_size)]

        out = torch.stack(outs, dim=0).to(torch.float32)
        out.clamp_(0, 1)
        return io.NodeOutput(out)
