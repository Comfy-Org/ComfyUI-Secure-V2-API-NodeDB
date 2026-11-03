"""comfyui-vrgamedevgirl (pin 5f2882d835bf, v9.1.1): the six converted classes, copied verbatim.

Their original modules import host-only or absent code at the top (nodes.py: folder_paths, comfy,
librosa, torchaudio, av, requests, kornia; VRGDG_GeneralNodes2.py: server, aiohttp, folder_paths), so a
guest cannot import them. The class bodies below are AST source segments of the pristine files (line
ranges and file hashes in the comments). Boundary edits:
  - `comfy.model_management` is a local stand-in: the guest computes on its CPU torch device, so both
    device lookups answer CPU and every original device line stays byte-identical;
  - `kornia` is the vendored kornia 0.8.3 RGB<->Lab path (_vendor_kornia_color.py);
  - VRGDG_LUTS parses the bytes of its "vrgdg_luts" asset instead of opening a file in the pack folder.
Copied and edited:
#   nodes.py L172-220 FastFilmGrain
#   nodes.py L224-278 ColorMatchToReference
#   nodes.py L283-363 FastUnsharpSharpen
#   nodes.py L366-443 FastLaplacianSharpen
#   VRGDG_IV_Adjustments.py L7-7 LUTS_DIR
#   VRGDG_IV_Adjustments.py L8-8 SUPPORTED_LUT_EXTENSIONS
#   VRGDG_IV_Adjustments.py L25-36 _list_lut_files
#   edited: VRGDG_IV_Adjustments.py VRGDG_LUTS: 'def _load_lut(cls, lut_name):'
#   edited: VRGDG_IV_Adjustments.py VRGDG_LUTS: 'def _parse_cube_file(lut_path):'
#   edited: VRGDG_IV_Adjustments.py VRGDG_LUTS: 'with open(lut_path, "r", encoding="utf-8", errors="ignore") as handle:'
#   VRGDG_IV_Adjustments.py L140-361 VRGDG_LUTS
#   VRGDG_GeneralNodes2.py L2149-2191 VRGDG_MultiStringConcat
"""
import contextlib
import io as _stdio
import os
import types
from typing import Tuple

import numpy as np
import torch
import torch.nn.functional as F

from . import _vendor_kornia_color

kornia = types.SimpleNamespace(color=_vendor_kornia_color)
comfy = types.SimpleNamespace(model_management=types.SimpleNamespace(
    get_torch_device=lambda: torch.device("cpu"),
    intermediate_device=lambda: torch.device("cpu"),
))


@contextlib.contextmanager
def _text_lines(content):
    # The original opened the file in text mode: utf-8, errors="ignore", universal newlines.
    with _stdio.TextIOWrapper(_stdio.BytesIO(content), encoding="utf-8", errors="ignore") as handle:
        yield handle


# nodes.py L172-220 (pristine sha256 bd66c18be4ba14fde941f48af50da7e484270dbf8526c00828f7e4f599c64cab)
class FastFilmGrain:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "grain_intensity": (
                    "FLOAT", {"default": 0.04, "min": 0.001, "max": 1.0, "step": 0.001}
                ),
                "saturation_mix": (
                    "FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}
                ),
                "batch_size": (
                    "INT", {"default": 4, "min": 0, "max": 500, "step": 1}
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply_grain"
    CATEGORY = "video/enhancement"
    DESCRIPTION = "Adds lightweight film grain"

    def apply_grain(self, images, grain_intensity, saturation_mix, batch_size):
        device = comfy.model_management.get_torch_device()

        # batch_size==0 (allowed by INPUT_TYPES min) would crash range();
        # treat as "process everything in a single batch".
        step = batch_size if batch_size > 0 else images.shape[0]

        outputs = []
        for i in range(0, images.shape[0], step):
            batch = images[i:i + step].to(device)
            grain = torch.randn_like(batch)

            grain[:, :, :, 0] *= 2.0  # red
            grain[:, :, :, 2] *= 3.0  # blue

            gray = grain[:, :, :, 1].unsqueeze(3).repeat(1, 1, 1, 3)
            grain = saturation_mix * grain + (1.0 - saturation_mix) * gray

            output = batch + grain * grain_intensity
            output = output.clamp(0.0, 1.0)
            outputs.append(output.cpu())
            del batch, grain, gray, output

        output = torch.cat(outputs, dim=0)
        output = output.to(comfy.model_management.intermediate_device())
        return (output,)


# nodes.py L224-278 (pristine sha256 bd66c18be4ba14fde941f48af50da7e484270dbf8526c00828f7e4f599c64cab)
class ColorMatchToReference:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "reference_image": ("IMAGE",),
                "match_strength": (
                    "FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}
                ),
                "batch_size": (
                    "INT", {"default": 1, "min": 1, "max": 500, "step": 1}
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "match_color"
    CATEGORY = "video/enhancement"
    DESCRIPTION = "Matches the color tone of input image to a reference image using LAB mean/std alignment"

    def match_color(self, images, reference_image, match_strength, batch_size):
        device = comfy.model_management.get_torch_device()

        images = images.permute(0, 3, 1, 2)  # stays on CPU
        reference_image = reference_image.permute(0, 3, 1, 2).to(device)

        with torch.no_grad(), torch.cuda.amp.autocast():
            ref_lab = kornia.color.rgb_to_lab(reference_image)
            ref_mean = ref_lab.mean(dim=[2, 3], keepdim=True)
            ref_std = ref_lab.std(dim=[2, 3], keepdim=True) + 1e-5

        outputs = []

        with torch.no_grad(), torch.cuda.amp.autocast():
            for i in range(0, images.shape[0], batch_size):
                batch = images[i:i + batch_size].to(device)

                img_lab = kornia.color.rgb_to_lab(batch)
                img_mean = img_lab.mean(dim=[2, 3], keepdim=True)
                img_std = img_lab.std(dim=[2, 3], keepdim=True) + 1e-5

                matched_lab = (img_lab - img_mean) / img_std * ref_std + ref_mean
                blended_lab = match_strength * matched_lab + (1.0 - match_strength) * img_lab

                output = kornia.color.lab_to_rgb(blended_lab)

                outputs.append(output.cpu())
                del batch, img_lab, output
                torch.cuda.empty_cache()

        output = torch.cat(outputs, dim=0).clamp(0.0, 1.0)
        output = output.permute(0, 2, 3, 1)
        output = output.to(comfy.model_management.intermediate_device())
        return (output,)


# nodes.py L283-363 (pristine sha256 bd66c18be4ba14fde941f48af50da7e484270dbf8526c00828f7e4f599c64cab)
class FastUnsharpSharpen:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "strength": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.0,
                        "max": 10.0,
                        "step": 0.01,
                    },
                ),
                "use_gpu": (
                    "BOOLEAN",
                    {"default": False},
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply_unsharp"
    CATEGORY = "video/enhancement"
    DESCRIPTION = "Unsharp mask (CPU default, optional GPU path)."

    def apply_unsharp(
        self,
        images: torch.Tensor,
        strength: float,
        use_gpu: bool,
    ) -> Tuple[torch.Tensor]:

        # =========================
        # GPU PATH (explicit opt-in)
        # =========================
        if use_gpu:
            device = comfy.model_management.get_torch_device()

            x = images.to(device).permute(0, 3, 1, 2)

            blur = F.avg_pool2d(x, kernel_size=3, stride=1, padding=1)

            out = x + strength * (x - blur)
            out = out.clamp(0.0, 1.0)

            out = out.permute(0, 2, 3, 1)
            return (out.to(comfy.model_management.intermediate_device()),)

        # =========================
        # CPU PATH (default, safe)
        # =========================
        if images.is_cuda:
            images = images.cpu()
        images = images.contiguous()

        img = images.numpy()  # NHWC

        p = np.pad(
            img,
            ((0, 0), (1, 1), (1, 1), (0, 0)),
            mode="edge",
        )

        blur = (
            p[:, 0:-2, 0:-2] +
            p[:, 0:-2, 1:-1] +
            p[:, 0:-2, 2:  ] +
            p[:, 1:-1, 0:-2] +
            p[:, 1:-1, 1:-1] +
            p[:, 1:-1, 2:  ] +
            p[:, 2:  , 0:-2] +
            p[:, 2:  , 1:-1] +
            p[:, 2:  , 2:  ]
        ) / 9.0

        out = img + strength * (img - blur)
        np.clip(out, 0.0, 1.0, out=out)

        return (torch.from_numpy(out),)


# nodes.py L366-443 (pristine sha256 bd66c18be4ba14fde941f48af50da7e484270dbf8526c00828f7e4f599c64cab)
class FastLaplacianSharpen:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "strength": (
                    "FLOAT",
                    {"default": 0.5, "min": 0.0, "max": 2.0, "step": 0.01},
                ),
                "use_gpu": (
                    "BOOLEAN",
                    {"default": False},
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply_laplacian"
    CATEGORY = "video/enhancement"
    DESCRIPTION = "Laplacian sharpen (CPU default, optional GPU)."

    def apply_laplacian(
        self,
        images: torch.Tensor,
        strength: float,
        use_gpu: bool,
    ) -> Tuple[torch.Tensor]:

        # =========================
        # GPU PATH (explicit opt-in)
        # =========================
        if use_gpu:
            device = comfy.model_management.get_torch_device()

            x = images.to(device).permute(0, 3, 1, 2)

            kernel = torch.tensor(
                [[0, -1, 0],
                 [-1, 4, -1],
                 [0, -1, 0]],
                dtype=torch.float32,
                device=device,
            ).expand(3, 1, 3, 3)

            edges = F.conv2d(x, kernel, padding=1, groups=3)
            out = (x + strength * edges).clamp(0.0, 1.0)

            out = out.permute(0, 2, 3, 1)
            return (out.to(comfy.model_management.intermediate_device()),)

        # =========================
        # CPU PATH (default, safe)
        # =========================
        if images.is_cuda:
            images = images.cpu()
        images = images.contiguous()

        img = images.numpy()  # NHWC

        p = np.pad(
            img,
            ((0, 0), (1, 1), (1, 1), (0, 0)),
            mode="edge",
        )

        lap = (
            p[:, 1:-1, 0:-2] +
            p[:, 0:-2, 1:-1] +
            p[:, 2:  , 1:-1] +
            p[:, 1:-1, 2:  ] -
            4.0 * img
        )

        out = img + strength * lap
        np.clip(out, 0.0, 1.0, out=out)

        return (torch.from_numpy(out),)


# VRGDG_IV_Adjustments.py L7-7 (pristine sha256 610a97f999ddde19fe3bf941bd5098cd5616f6f18c32aa5ec37c3de7d8d557cc)
LUTS_DIR = os.path.join(os.path.dirname(__file__), "LUTS")


# VRGDG_IV_Adjustments.py L8-8 (pristine sha256 610a97f999ddde19fe3bf941bd5098cd5616f6f18c32aa5ec37c3de7d8d557cc)
SUPPORTED_LUT_EXTENSIONS = (".cube",)


# VRGDG_IV_Adjustments.py L25-36 (pristine sha256 610a97f999ddde19fe3bf941bd5098cd5616f6f18c32aa5ec37c3de7d8d557cc)
def _list_lut_files():
    if not os.path.isdir(LUTS_DIR):
        return ["No LUT files found"]

    files = [
        name
        for name in os.listdir(LUTS_DIR)
        if os.path.isfile(os.path.join(LUTS_DIR, name))
        and name.lower().endswith(SUPPORTED_LUT_EXTENSIONS)
    ]
    files.sort(key=str.lower)
    return files or ["No LUT files found"]


# VRGDG_IV_Adjustments.py L140-361 (pristine sha256 610a97f999ddde19fe3bf941bd5098cd5616f6f18c32aa5ec37c3de7d8d557cc)
class VRGDG_LUTS:
    CATEGORY = "VRGDG/IV Adjustments"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "apply_lut"

    _LUT_CACHE = {}

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "lut_name": (_list_lut_files(),),
                "device": (["auto", "cuda", "cpu"], {"default": "auto"}),
                "strength": ("FLOAT", {"default": 10.0, "min": 0.0, "max": 10.0, "step": 0.1}),
            }
        }

    @classmethod
    def IS_CHANGED(cls, image, lut_name, device, strength):
        if lut_name == "No LUT files found":
            return f"missing|{device}|{strength}"

        folder_state = cls._get_luts_folder_state()
        lut_path = os.path.join(LUTS_DIR, lut_name)
        if not os.path.isfile(lut_path):
            return f"{folder_state}|missing|{lut_name}|{device}|{strength}"

        return f"{folder_state}|{lut_name}|{os.path.getmtime(lut_path)}|{device}|{strength}"

    @staticmethod
    def _resolve_device(requested_device, image):
        requested = str(requested_device or "auto").strip().lower()
        if requested == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("VRGDG_LUTS: CUDA was selected, but CUDA is not available.")
            return torch.device("cuda")
        if requested == "cpu":
            return torch.device("cpu")

        if image.device.type != "cpu":
            return image.device
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    @staticmethod
    def _get_luts_folder_state():
        if not os.path.isdir(LUTS_DIR):
            return "missing"

        entries = []
        for name in _list_lut_files():
            if name == "No LUT files found":
                continue
            path = os.path.join(LUTS_DIR, name)
            try:
                entries.append(f"{name}:{os.path.getmtime(path)}:{os.path.getsize(path)}")
            except OSError:
                entries.append(f"{name}:missing")
        return "|".join(entries) if entries else "empty"

    @classmethod
    def _load_lut(cls, lut_name):
        if lut_name == "No LUT files found":
            raise ValueError("No LUT files were found in the LUTS folder.")

        # V2: the bytes of the resolved "vrgdg_luts" asset, set by the wrapper for this call. The
        # pack folder is not readable for user files, and nothing is cached between runs.
        lut_path = lut_name
        lut_data = cls._parse_cube_file(lut_path, cls._lut_bytes)
        return lut_data

    @staticmethod
    def _parse_cube_file(lut_path, content):
        size = None
        domain_min = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        domain_max = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        values = []

        with _text_lines(content) as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                upper = line.upper()
                if upper.startswith("TITLE "):
                    continue
                if upper.startswith("LUT_1D_SIZE"):
                    raise ValueError(f"1D LUTs are not supported: {os.path.basename(lut_path)}")
                if upper.startswith("LUT_3D_SIZE"):
                    parts = line.split()
                    if len(parts) != 2:
                        raise ValueError(f"Invalid LUT_3D_SIZE line in {lut_path}")
                    size = int(parts[1])
                    continue
                if upper.startswith("DOMAIN_MIN"):
                    parts = line.split()
                    if len(parts) != 4:
                        raise ValueError(f"Invalid DOMAIN_MIN line in {lut_path}")
                    domain_min = np.array([float(parts[1]), float(parts[2]), float(parts[3])], dtype=np.float32)
                    continue
                if upper.startswith("DOMAIN_MAX"):
                    parts = line.split()
                    if len(parts) != 4:
                        raise ValueError(f"Invalid DOMAIN_MAX line in {lut_path}")
                    domain_max = np.array([float(parts[1]), float(parts[2]), float(parts[3])], dtype=np.float32)
                    continue

                parts = line.split()
                if len(parts) != 3:
                    continue
                values.extend(float(part) for part in parts)

        if size is None:
            raise ValueError(f"Missing LUT_3D_SIZE in {lut_path}")

        expected_values = size * size * size * 3
        if len(values) != expected_values:
            raise ValueError(
                f"Invalid LUT data length in {lut_path}. Expected {expected_values} floats, got {len(values)}."
            )

        # .cube 3D LUT data is typically stored with red changing fastest,
        # then green, then blue. In C-order reshape that means [blue, green, red, rgb].
        lut = np.asarray(values, dtype=np.float32).reshape(size, size, size, 3)
        lut = torch.from_numpy(lut)

        return {
            "size": size,
            "lut": lut,
            "domain_min": torch.from_numpy(domain_min),
            "domain_max": torch.from_numpy(domain_max),
        }

    @staticmethod
    def _expand_index(index, channels):
        return index.unsqueeze(-1).expand(*index.shape, channels)

    @classmethod
    def _apply_cube_lut(cls, image, lut_tensor, domain_min, domain_max):
        if image.ndim != 4 or image.shape[-1] < 3:
            raise ValueError("VRGDG_LUTS expects IMAGE input shaped like [batch, height, width, channels].")

        source = image[..., :3].to(dtype=torch.float32)

        domain_span = torch.clamp(domain_max - domain_min, min=1e-6)
        normalized = (source - domain_min) / domain_span
        normalized = torch.clamp(normalized, 0.0, 1.0)

        max_index = lut_tensor.shape[0] - 1
        coords = normalized * max_index

        r = coords[..., 0]
        g = coords[..., 1]
        b = coords[..., 2]

        r0 = torch.floor(r).long()
        g0 = torch.floor(g).long()
        b0 = torch.floor(b).long()

        r1 = torch.clamp(r0 + 1, max=max_index)
        g1 = torch.clamp(g0 + 1, max=max_index)
        b1 = torch.clamp(b0 + 1, max=max_index)

        fr = (r - r0.float()).unsqueeze(-1)
        fg = (g - g0.float()).unsqueeze(-1)
        fb = (b - b0.float()).unsqueeze(-1)

        c000 = lut_tensor[b0, g0, r0]
        c001 = lut_tensor[b1, g0, r0]
        c010 = lut_tensor[b0, g1, r0]
        c011 = lut_tensor[b1, g1, r0]
        c100 = lut_tensor[b0, g0, r1]
        c101 = lut_tensor[b1, g0, r1]
        c110 = lut_tensor[b0, g1, r1]
        c111 = lut_tensor[b1, g1, r1]

        c00 = c000 * (1.0 - fb) + c001 * fb
        c01 = c010 * (1.0 - fb) + c011 * fb
        c10 = c100 * (1.0 - fb) + c101 * fb
        c11 = c110 * (1.0 - fb) + c111 * fb

        c0 = c00 * (1.0 - fg) + c01 * fg
        c1 = c10 * (1.0 - fg) + c11 * fg

        output_rgb = c0 * (1.0 - fr) + c1 * fr
        output_rgb = torch.clamp(output_rgb, 0.0, 1.0)

        if image.shape[-1] == 3:
            return output_rgb.to(dtype=image.dtype)

        output = image.clone()
        output[..., :3] = output_rgb.to(dtype=image.dtype)
        return output

    def apply_lut(self, image, lut_name, device, strength):
        lut_data = self._load_lut(lut_name)
        target_device = self._resolve_device(device, image)

        working_image = image.to(device=target_device)
        lut_tensor = lut_data["lut"].to(device=target_device)
        domain_min = lut_data["domain_min"].to(device=target_device, dtype=working_image.dtype)
        domain_max = lut_data["domain_max"].to(device=target_device, dtype=working_image.dtype)
        output = self._apply_cube_lut(working_image, lut_tensor, domain_min, domain_max)

        blend = max(0.0, min(10.0, float(strength))) / 10.0
        if blend <= 0.0:
            output = working_image
        elif blend < 1.0:
            output = (working_image * (1.0 - blend)) + (output * blend)

        return (output.to(device=image.device),)


# VRGDG_GeneralNodes2.py L2149-2191 (pristine sha256 c017d56417463b80c13d77d227f4c0fa6bde6482d60945b8f5f47e73408b3bec)
class VRGDG_MultiStringConcat:
    MAX_STRING_SLOTS = 20

    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "string_count": ("INT", {"default": 2, "min": 1, "max": cls.MAX_STRING_SLOTS, "step": 1}),
            "delimiter": (
                "STRING",
                {
                    "default": "\\n\\n",
                    "multiline": False,
                    "placeholder": "Text inserted between strings. Use \\n for newline.",
                    "tooltip": "Text inserted between each non-empty string. Use \\n for newline, \\t for tab, or clear for no delimiter.",
                },
            ),
        }
        for i in range(1, cls.MAX_STRING_SLOTS + 1):
            required[f"string_{i}"] = ("STRING", {"default": "", "multiline": True})
        return {"required": required}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "concat"
    CATEGORY = "VRGDG/General"
    DESCRIPTION = "Concatenates multiple multiline string widgets with an optional delimiter."

    @staticmethod
    def _normalize_delimiter(delimiter):
        return str(delimiter or "").replace("\\r\\n", "\r\n").replace("\\n", "\n").replace("\\t", "\t")

    def concat(self, string_count, delimiter, **kwargs):
        count = max(1, min(self.MAX_STRING_SLOTS, int(string_count or 1)))
        parts = []
        for i in range(1, count + 1):
            value = kwargs.get(f"string_{i}", "")
            if value is None:
                continue
            text = str(value)
            if text == "":
                continue
            parts.append(text)
        return (self._normalize_delimiter(delimiter).join(parts),)
