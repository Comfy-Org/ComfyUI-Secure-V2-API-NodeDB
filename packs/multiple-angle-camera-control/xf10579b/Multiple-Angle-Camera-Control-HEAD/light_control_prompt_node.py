"""
Light Control Prompt Node for ComfyUI
Generates lighting direction prompts for image relighting

Author: Lorenzo Mercu
Description: Light control prompt generator for relighting workflows
Features: Multi-directional light source control, bilingual prompts
"""


class RelightingPromptNode:
    """
    Nodo che genera il prompt ottimizzato per il relighting
    basandosi sulla direzione della luce selezionata
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "light_direction": ([
                    "front",           # 前方
                    "front_left",      # 左前方
                    "left",            # 左方
                    "back_left",       # 左后方
                    "back",            # 后方
                    "back_right",      # 右后方
                    "right",           # 右方
                    "front_right",     # 右前方
                    "above",           # 上方
                    "below"            # 下方
                ], {"default": "front"}),
                "use_chinese": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "generate_prompt"
    CATEGORY = "relighting"

    def generate_prompt(self, light_direction, use_chinese):
        """Genera il prompt basato sulla direzione della luce"""

        # Mappatura direzioni luce - Cinese
        light_directions_cn = {
            "front": "光源来自前方",
            "front_left": "光源来自左前方",
            "left": "光源来自左方",
            "back_left": "光源来自左后方",
            "back": "光源来自后方",
            "back_right": "光源来自右后方",
            "right": "光源来自右方",
            "front_right": "光源来自右前方",
            "above": "光源来自上方",
            "below": "光源来自下方"
        }

        # Mappatura direzioni luce - Inglese
        light_directions_en = {
            "front": "light source from the front",
            "front_left": "light source from the front left",
            "left": "light source from the left",
            "back_left": "light source from the back left",
            "back": "light source from the back",
            "back_right": "light source from the back right",
            "right": "light source from the right",
            "front_right": "light source from the front right",
            "above": "light source from above",
            "below": "light source from below"
        }

        # Genera il prompt nella lingua selezionata
        if use_chinese:
            direction_text = light_directions_cn.get(light_direction, "光源来自前方")
            final_prompt = f"使用图2的亮度贴图对图1重新照明({direction_text})"
        else:
            direction_text = light_directions_en.get(light_direction, "light source from the front")
            final_prompt = f"Relight Figure 1 using the luminance map from Figure 2 ({direction_text})"

        return (final_prompt,)


# Mappings per ComfyUI
NODE_CLASS_MAPPINGS = {
    "RelightingPromptNode": RelightingPromptNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RelightingPromptNode": "Relighting Prompt Generator"
}
