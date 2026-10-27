import math

RATIO_PRESETS = [
    "1:1 (Square)",
    "2:3 (Portrait Photo)",
    "3:2 (Photo)",
    "3:4 (Portrait Standard)",
    "4:3 (Standard)",
    "9:16 (Portrait Widescreen)",
    "16:9 (Widescreen)",
    "21:9 (Ultrawide)"
]

class Wqx_DualRatioTools:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "asp": (RATIO_PRESETS, {"default":"9:16 (Portrait Widescreen)"}),
                "megapixels1": ("FLOAT", {"default":0.60, "min":0.1, "max":16.0, "step":0.05}),
                "megapixels2": ("FLOAT", {"default":2.00, "min":0.1, "max":16.0, "step":0.05}),
                "multiple": ("INT", {"default":32, "min":8, "max":128}),
            }
        }

    RETURN_TYPES = ("INT","INT","INT","INT","FLOAT")
    RETURN_NAMES = ("size1_w","size1_h","size2_w","size2_h","aspect_float")
    FUNCTION = "calc"
    CATEGORY = "Wqx/Tools"

    def calc(self, asp, megapixels1, megapixels2, multiple):
        part = asp.split(" ")[0]
        rw_str, rh_str = part.split(":")
        ratio_w = int(rw_str)
        ratio_h = int(rh_str)
        aspect_float = ratio_w / ratio_h

        def calc_size(mp):
            # ComfyUI内置节点：1 megapixel = 1024*1024，不是1000*1000！！
            area = mp * (1024 * 1024)
            ideal_w = math.sqrt(area * aspect_float)
            ideal_h = math.sqrt(area / aspect_float)
            w = round(ideal_w / multiple) * multiple
            h = round(ideal_h / multiple) * multiple
            return int(w), int(h)

        s1w, s1h = calc_size(megapixels1)
        s2w, s2h = calc_size(megapixels2)
        return (s1w, s1h, s2w, s2h, float(aspect_float))


NODE_CLASS_MAPPINGS = {
    "Wqx_DualRatioTools": Wqx_DualRatioTools
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Wqx_DualRatioTools": "Wqx 单比例双分辨率(统一multiple)"
}
