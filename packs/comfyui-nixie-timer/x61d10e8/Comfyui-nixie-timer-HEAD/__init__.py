# 辉光管计时器节点 —— 拖入工作流即显示可拖动的辉光管推理计时器
# 计时代理逻辑完全在前端(web extension),本节点仅作为"开关":存在则显示面板。

WEB_DIRECTORY = "./js"

TUBE_COLORS = ["红色", "绿色", "蓝色", "琥珀", "紫色", "青色", "白色"]


class NixieTimer:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "tube_color": (TUBE_COLORS, {"default": "红色"}),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "noop"
    CATEGORY = "utils"

    def noop(self, tube_color):
        return ()


NODE_CLASS_MAPPINGS = {"NixieTimer": NixieTimer}
NODE_DISPLAY_NAME_MAPPINGS = {"NixieTimer": "🕰️ 辉光管计时器"}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
