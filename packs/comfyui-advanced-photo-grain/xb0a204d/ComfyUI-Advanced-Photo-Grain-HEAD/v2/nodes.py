"""Secure Nodes V2 conversion of Advanced Photo Grain."""

from __future__ import annotations

import torch
import torch.nn.functional as F
import torchvision.transforms.functional as TF
from comfy_api.latest import ComfyExtension, io

GRAIN_TYPES = ["gaussian", "poisson", "perlin"]


class PhotoFilmGrain(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="PhotoFilmGrain",
            display_name="📸 Photo Film Grain",
            category="image/enhancement",
            description=(
                "Adds realistic film grain, vignette and RGB aberration to photos"
            ),
            inputs=[
                io.Image.Input("images"),
                io.Combo.Input("grain_type", options=GRAIN_TYPES, default="poisson"),
                io.Float.Input(
                    "grain_intensity",
                    default=0.022,
                    min=0.001,
                    max=1.0,
                    step=0.001,
                ),
                io.Float.Input(
                    "grain_size",
                    default=1.5,
                    min=1.0,
                    max=16.0,
                    step=0.1,
                ),
                io.Float.Input(
                    "saturation_mix",
                    default=0.22,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                ),
                io.Float.Input(
                    "adaptive_grain",
                    default=0.30,
                    min=0.0,
                    max=2.0,
                    step=0.01,
                ),
                io.Float.Input(
                    "halation_strength",
                    default=0.0,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                ),
                io.Float.Input(
                    "vignette_strength",
                    default=0.0,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                ),
                io.Float.Input(
                    "chromatic_aberration",
                    default=0.0,
                    min=0.0,
                    max=5.0,
                    step=0.1,
                ),
                io.Float.Input(
                    "lens_distortion",
                    default=0.0,
                    min=-0.5,
                    max=0.5,
                    step=0.01,
                ),
            ],
            outputs=[io.Image.Output()],
        )

    @classmethod
    def execute(
        cls,
        images,
        grain_type,
        grain_intensity,
        grain_size,
        saturation_mix,
        adaptive_grain,
        halation_strength,
        vignette_strength,
        chromatic_aberration,
        lens_distortion,
    ) -> io.NodeOutput:

        if grain_intensity > 0.0:
            if grain_type == "gaussian":
                grain = cls._generate_gaussian(images, grain_size)
            elif grain_type == "poisson":
                grain = cls._generate_poisson(images, grain_size)
            elif grain_type == "perlin":
                grain = cls._generate_perlin(images, grain_size)
            else:
                raise ValueError(f"Unsupported grain type: {grain_type}")

            gray = grain[:, :, :, 1].unsqueeze(3).repeat(1, 1, 1, 3)
            grain = saturation_mix * grain + (1.0 - saturation_mix) * gray

            if adaptive_grain > 0.0:
                luma = images.mean(dim=3, keepdim=True)
                gain = (1.0 - luma).pow(2.0) * 2.5
                grain = grain * (1.0 + adaptive_grain * gain)

            output = images + grain * grain_intensity
            output = output.clamp(0.0, 1.0)
        else:
            output = images

        if halation_strength > 0.0:
            output = cls._apply_halation(output, halation_strength)

        if lens_distortion != 0.0:
            output = cls._apply_lens_distortion(output, lens_distortion)

        if vignette_strength > 0.0:
            output = cls._apply_vignette(output, vignette_strength)

        if chromatic_aberration > 0.0:
            output = cls._apply_chromatic_aberration(output, chromatic_aberration)

        return io.NodeOutput(output)

    @staticmethod
    def _generate_gaussian(images, size):
        B, H, W, C = images.shape
        size = int(size)
        if size <= 1:
            noise = torch.randn_like(images)
        else:
            small_H, small_W = H // size, W // size
            noise = torch.randn(B, small_H, small_W, C, device=images.device)
            noise = noise.permute(0, 3, 1, 2)
            noise = F.interpolate(noise, size=(H, W), mode="nearest")
            noise = noise.permute(0, 2, 3, 1)

        noise[:, :, :, 0] *= 2.0
        noise[:, :, :, 2] *= 3.0
        return noise

    @staticmethod
    def _generate_poisson(images, size):
        B, H, W, _ = images.shape
        size = int(size)
        if size <= 1:
            target_images = images
        else:
            small_H, small_W = H // size, W // size
            target_images = F.interpolate(
                images.permute(0, 3, 1, 2),
                size=(small_H, small_W),
                mode="bilinear",
                align_corners=False,
            )
            target_images = target_images.permute(0, 2, 3, 1)

        scaled = torch.clamp(target_images * 255.0, 0, 255).round()
        noise = torch.poisson(scaled) - scaled
        grain = (noise / 255.0) * 16.0

        if size > 1:
            grain = grain.permute(0, 3, 1, 2)
            grain = F.interpolate(grain, size=(H, W), mode="nearest")
            grain = grain.permute(0, 2, 3, 1)

        grain[:, :, :, 0] *= 2.0
        grain[:, :, :, 2] *= 3.0
        return grain

    @classmethod
    def _generate_perlin(cls, images, size):
        B, H, W, _ = images.shape
        size = int(size)
        scale = max(4, 32 // size)

        perlin = cls._make_fractal_noise(B, H, W, scale, images.device)
        perlin = (perlin - 0.5) * 2.0

        perlin = perlin.unsqueeze(3).repeat(1, 1, 1, 3)
        return perlin

    @staticmethod
    def _make_fractal_noise(
        B,
        H,
        W,
        scale,
        device,
        octaves=4,
        persistence=0.5,
        lacunarity=2.0,
    ):
        total_noise = torch.zeros(B, H, W, device=device)
        frequency = 1.0
        amplitude = 1.0
        max_amplitude = 0.0

        for _ in range(octaves):
            current_scale = max(2, int(scale * frequency))
            coarse_noise = torch.rand(B, current_scale, current_scale, 1, device=device)
            upscaled_noise = F.interpolate(
                coarse_noise.permute(0, 3, 1, 2),
                size=(H, W),
                mode="bilinear",
                align_corners=False,
            ).squeeze(1)
            total_noise += upscaled_noise * amplitude
            max_amplitude += amplitude
            amplitude *= persistence
            frequency *= lacunarity

        if max_amplitude > 0:
            total_noise /= max_amplitude

        return total_noise

    @staticmethod
    def _apply_halation(image, strength):
        _, _, W, C = image.shape
        if C != 3:
            return image

        luma = image.mean(dim=3, keepdim=True)
        highlights_mask = torch.clamp((luma - 0.75) * 4, 0, 1)

        red_channel = image[:, :, :, 0:1]
        red_glow = red_channel * highlights_mask

        blur_radius = int(strength * (W / 25)) * 2 + 1
        if blur_radius < 3:
            return image

        red_glow_permuted = red_glow.permute(0, 3, 1, 2)
        red_glow_blurred = TF.gaussian_blur(red_glow_permuted, kernel_size=blur_radius)
        red_glow_blurred = red_glow_blurred.permute(0, 2, 3, 1)

        halation_layer = torch.cat(
            [
                red_glow_blurred,
                torch.zeros_like(red_glow_blurred),
                torch.zeros_like(red_glow_blurred),
            ],
            dim=3,
        )

        return (image + halation_layer * strength).clamp(0.0, 1.0)

    @staticmethod
    def _apply_lens_distortion(image, strength):
        B, H, W, _ = image.shape

        # Créer une grille de coordonnées normalisées de -1 à 1
        y, x = torch.meshgrid(
            torch.linspace(-1, 1, H, device=image.device),
            torch.linspace(-1, 1, W, device=image.device),
            indexing="ij",
        )
        grid = torch.stack((x, y), dim=-1).unsqueeze(0).repeat(B, 1, 1, 1)

        # Calculer la distance de chaque pixel au centre
        radius = torch.sqrt(grid[..., 0] ** 2 + grid[..., 1] ** 2)

        # Appliquer la formule de distorsion radiale
        # k est notre "strength". strength < 0 = barillet, strength > 0 = coussinet
        k = strength * -1  # Inverser pour un contrôle plus intuitif
        distortion_factor = 1.0 + k * radius.pow(2)

        # Appliquer la distorsion à la grille de coordonnées
        distorted_grid = grid * distortion_factor.unsqueeze(-1)

        # Échantillonner l'image originale en utilisant la nouvelle grille
        image_permuted = image.permute(0, 3, 1, 2)  # B, C, H, W
        distorted_image = F.grid_sample(
            image_permuted,
            distorted_grid,
            mode="bilinear",
            padding_mode="border",
            align_corners=False,
        )

        return distorted_image.permute(0, 2, 3, 1)

    @staticmethod
    def _apply_vignette(image, strength):
        _, H, W, _ = image.shape
        y = torch.linspace(-1, 1, H, device=image.device).view(1, H, 1, 1)
        x = torch.linspace(-1, 1, W, device=image.device).view(1, 1, W, 1)
        dist = torch.sqrt(x**2 + y**2)
        mask = 1.0 - strength * dist.clamp(0.0, 1.0)
        return image * mask

    @staticmethod
    def _apply_chromatic_aberration(image, strength):
        _, H, _, C = image.shape
        if C != 3 or strength <= 0:
            return image

        shift = max(1, round(strength * 2.5))

        r = F.pad(image[:, :, :, 0:1], (0, 0, shift, shift), mode="reflect")
        b = F.pad(image[:, :, :, 2:3], (0, 0, shift, shift), mode="reflect")
        g = image[:, :, :, 1:2]

        r = r[:, shift : H + shift, :, :]
        b = b[:, shift - 1 : H + shift - 1, :, :]

        min_H = min(r.shape[1], g.shape[1], b.shape[1])
        min_W = min(r.shape[2], g.shape[2], b.shape[2])

        r = r[:, :min_H, :min_W, :]
        g = g[:, :min_H, :min_W, :]
        b = b[:, :min_H, :min_W, :]

        return torch.cat([r, g, b], dim=3)


class FreqSeparationSharpen(io.ComfyNode):
    """Accentuation par separation de frequences, sur GPU.

    Separe l'image en basses frequences (flou gaussien) et hautes frequences
    (le reste), amplifie ces dernieres puis recombine. Contrairement a un
    unsharp mask global, les couleurs et le contraste general ne bougent pas :
    seul le micro-contraste est touche, ce qui convient bien pour recuperer
    le pique perdu par une quantification agressive.
    """

    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="FreqSeparationSharpen",
            display_name="Frequency Separation Sharpen",
            category="image/enhancement",
            description=(
                "Frequency separation sharpening (GPU, batch-aware) with "
                "noise threshold and halo limiter"
            ),
            inputs=[
                io.Image.Input("image"),
                io.Float.Input(
                    "radius",
                    default=2.0,
                    min=0.1,
                    max=50.0,
                    step=0.1,
                    tooltip=(
                        "Rayon du flou. Petit = detail fin, grand = structures larges."
                    ),
                ),
                io.Float.Input(
                    "strength",
                    default=1.0,
                    min=0.0,
                    max=10.0,
                    step=0.1,
                    tooltip=(
                        "1.0 = neutre. Au-dela, les hautes frequences sont amplifiees."
                    ),
                ),
                io.Float.Input(
                    "threshold",
                    default=0.0,
                    min=0.0,
                    max=0.2,
                    step=0.002,
                    tooltip=(
                        "Sous ce seuil les details restent intacts, au-dessus "
                        "ils sont accentues. Evite de renforcer le bruit. "
                        "0 = tout accentuer."
                    ),
                    optional=True,
                ),
                io.Float.Input(
                    "halo_limit",
                    default=0.0,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                    tooltip=(
                        "Plafonne l'amplitude des hautes frequences pour eviter "
                        "les lisereres sur les contours francs. 0 = desactive."
                    ),
                    optional=True,
                ),
            ],
            outputs=[io.Image.Output()],
        )

    @staticmethod
    def _gaussian_blur(x, sigma):
        """Flou gaussien separable : deux convolutions 1D au lieu d'une 2D.

        x : (B, C, H, W). Cout lineaire en rayon plutot que quadratique.
        """
        radius = max(1, int(3.0 * sigma + 0.5))
        coords = torch.arange(-radius, radius + 1, device=x.device, dtype=x.dtype)
        kernel = torch.exp(-(coords**2) / (2.0 * sigma * sigma))
        kernel = kernel / kernel.sum()

        C = x.shape[1]
        k_h = kernel.view(1, 1, 1, -1).expand(C, 1, 1, -1)
        k_v = kernel.view(1, 1, -1, 1).expand(C, 1, -1, 1)

        # 'reflect' evite l'assombrissement des bords
        x = F.pad(x, (radius, radius, 0, 0), mode="reflect")
        x = F.conv2d(x, k_h, groups=C)
        x = F.pad(x, (0, 0, radius, radius), mode="reflect")
        x = F.conv2d(x, k_v, groups=C)
        return x

    @classmethod
    def execute(
        cls,
        image,
        radius,
        strength,
        threshold=0.0,
        halo_limit=0.0,
    ) -> io.NodeOutput:
        if strength == 1.0 and threshold == 0.0 and halo_limit == 0.0:
            return io.NodeOutput(image)

        x = image.permute(0, 3, 1, 2).float()  # B,H,W,C -> B,C,H,W

        low = cls._gaussian_blur(x, radius)
        high = x - low

        # Le gain va de 1.0 (aucune amplification) sous le seuil a
        # "strength" au-dessus : les details faibles restent INTACTS au
        # lieu d'etre effaces, seul ce qui depasse le seuil est accentue.
        if threshold > 0.0 and strength != 1.0:
            mag = high.abs()
            t = ((mag - threshold) / max(threshold, 1e-6)).clamp(0.0, 1.0)
            t = t * t * (3.0 - 2.0 * t)  # smoothstep
            high = high * (1.0 + (strength - 1.0) * t)
        else:
            high = high * strength

        # Limiteur de halo : plafonne l'amplitude pour eviter les lisereres
        # aux transitions franches.
        if halo_limit > 0.0:
            high = high.clamp(-halo_limit, halo_limit)

        out = (low + high).clamp(0.0, 1.0)
        out = out.permute(0, 2, 3, 1)  # retour en B,H,W,C
        return io.NodeOutput(out)


NODE_CLASS_MAPPINGS = {
    "PhotoFilmGrain": PhotoFilmGrain,
    "FreqSeparationSharpen": FreqSeparationSharpen,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PhotoFilmGrain": "📸 Photo Film Grain",
    "FreqSeparationSharpen": "Frequency Separation Sharpen",
}


class AdvancedPhotoGrainExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [PhotoFilmGrain, FreqSeparationSharpen]


async def comfy_entrypoint() -> AdvancedPhotoGrainExtension:
    return AdvancedPhotoGrainExtension()


__all__ = [
    "GRAIN_TYPES",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "AdvancedPhotoGrainExtension",
    "FreqSeparationSharpen",
    "PhotoFilmGrain",
    "comfy_entrypoint",
]
