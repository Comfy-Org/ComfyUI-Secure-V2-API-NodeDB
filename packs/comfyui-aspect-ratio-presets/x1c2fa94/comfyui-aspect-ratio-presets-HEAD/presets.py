# presets.py
# Grouped most -> least relevant in 2026 usage (Krea/Flux.2/Qwen-Image lead current mindshare;
# SDXL/SD1.5 kept for their LoRA ecosystems but pushed to the bottom), then within a model
# square -> landscape -> portrait, widest ratio first. Dims kept multiples of 8 for
# latent-space compatibility.

PRESETS = [
    # model, label, w, h

    # --- Flux Krea (dev, photoreal-tuned, shares Flux.1 native grid) ---
    ("Krea", "1:1 Square", 512, 512),
    ("Krea", "1:1 Square",     1024, 1024),
    ("Krea", "3:2 Landscape",  1216, 832),
    ("Krea", "4:3 Landscape",  1152, 896),
    ("Krea", "16:9 Landscape", 1344, 768),
    ("Krea", "2:3 Portrait",   832, 1216),
    ("Krea", "3:4 Portrait",   896, 1152),
    ("Krea", "9:16 Portrait",  768, 1344),

    # --- Flux.2 (dev/pro/flex, higher native ceiling, up to ~4MP) ---
    ("Flux.2", "1:1 Square", 512, 512),
    ("Flux.2", "1:1 Square",     2048, 2048),
    ("Flux.2", "3:2 Landscape",  1728, 1152),
    ("Flux.2", "4:3 Landscape",  1664, 1248),
    ("Flux.2", "16:9 Landscape", 1920, 1088),
    ("Flux.2", "21:9 Landscape", 2176, 960),
    ("Flux.2", "2:3 Portrait",   1152, 1728),
    ("Flux.2", "3:4 Portrait",   1248, 1664),
    ("Flux.2", "9:16 Portrait",  1088, 1920),
    ("Flux.2", "9:21 Portrait",  960, 2176),

    # --- Qwen-Image (native ~1.7MP, wide native AR set) ---
    ("Qwen-Image", "1:1 Square", 512, 512),
    ("Qwen-Image", "1:1 Square",     1328, 1328),
    ("Qwen-Image", "3:2 Landscape",  1584, 1056),
    ("Qwen-Image", "4:3 Landscape",  1472, 1136),
    ("Qwen-Image", "16:9 Landscape", 1664, 928),
    ("Qwen-Image", "2:3 Portrait",   1056, 1584),
    ("Qwen-Image", "3:4 Portrait",   1136, 1472),
    ("Qwen-Image", "9:16 Portrait",  928, 1664),

    # --- Flux.1 (dev/schnell/pro, native 1024, ~1MP) ---
    ("Flux.1", "1:1 Square", 512, 512),
    ("Flux.1", "1:1 Square",     1408, 1408),
    ("Flux.1", "3:2 Landscape",  1216, 832),
    ("Flux.1", "4:3 Landscape",  1664, 1216),
    ("Flux.1", "16:9 Landscape", 1920, 1088),
    ("Flux.1", "21:9 Landscape", 2176, 960),
    ("Flux.1", "2:3 Portrait",   832, 1216),
    ("Flux.1", "3:4 Portrait",   1216, 1664),
    ("Flux.1", "9:16 Portrait",  1088, 1920),
    ("Flux.1", "9:21 Portrait",  960, 2176),

    # --- Stable Diffusion XL (native 1024, ~1MP) ---
    ("SDXL", "1:1 Square", 512, 512),
    ("SDXL", "1:1 Square",     1024, 1024),
    ("SDXL", "3:2 Landscape",  1152, 768),
    ("SDXL", "4:3 Landscape",  1152, 864),
    ("SDXL", "16:9 Landscape", 1360, 768),
    ("SDXL", "2:3 Portrait",   768, 1152),
    ("SDXL", "3:4 Portrait",   864, 1152),
    ("SDXL", "9:16 Portrait",  768, 1360),

    # --- Stable Diffusion 1.5 (native 512, legacy) ---
    ("SD15", "1:1 Square",     512, 512),
    ("SD15", "3:2 Landscape",  768, 512),
    ("SD15", "4:3 Landscape",  768, 576),
    ("SD15", "16:9 Landscape", 912, 512),
    ("SD15", "2:3 Portrait",   512, 768),
    ("SD15", "3:4 Portrait",   576, 768),
    ("SD15", "9:16 Portrait",  512, 912),

    # Ideogram 4.0 and ERNIE are hosted API models (no local LATENT/diffusion sampling
    # in ComfyUI) — deliberately excluded so this node never implies false compatibility.
]
