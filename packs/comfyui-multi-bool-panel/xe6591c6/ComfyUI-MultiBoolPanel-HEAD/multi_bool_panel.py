"""
Multi Bool Panel — 1ノードで他ノードへの一括boolean操作 (widgets/bypass/mute) を
行うComfyUIカスタムノード。出力ソケットは持たず、操作はフロントエンド拡張
(web/js/multi_bool_panel.js) が担当する。
"""


class SolidlimeMultiBoolPanel:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"mode": (["widgets", "bypass", "mute"], {"default": "widgets"})}
        }

    RETURN_TYPES = ()
    RETURN_NAMES = ()
    OUTPUT_NODE = False
    FUNCTION = "execute"
    CATEGORY = "Logic"

    def execute(self, **kwargs):
        return ()


NODE_CLASS_MAPPINGS = {"SolidlimeMultiBoolPanel": SolidlimeMultiBoolPanel}
NODE_DISPLAY_NAME_MAPPINGS = {"SolidlimeMultiBoolPanel": "Multi Bool Panel"}
