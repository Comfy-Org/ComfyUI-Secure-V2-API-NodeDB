from .text_concatenate import TextConcatenateDJ

# 五名规则：单节点包，包名即功能 → Node ID = 文件夹名，不加后缀
NODE_CLASS_MAPPINGS = {"ComfyUI-DJ_TextConcat": TextConcatenateDJ}
NODE_DISPLAY_NAME_MAPPINGS = {"ComfyUI-DJ_TextConcat": "ComfyUI-DJ_TextConcat_文本拼接"}
