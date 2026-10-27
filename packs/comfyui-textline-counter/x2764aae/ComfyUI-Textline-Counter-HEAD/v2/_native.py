class TextLineCounter:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text_input": ("STRING", {
                    "multiline": True,
                    "default": ""
                })
            }
        }

    # 修改返回类型和名称，增加一个处理后的文本输出
    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("original_text", "line_count", "processed_text")
    FUNCTION = "process_text_and_count_lines" # 建议修改函数名以反映新功能
    CATEGORY = "Text Processing"

    def process_text_and_count_lines(self, text_input):
        # 将输入文本按行分割
        lines = text_input.splitlines()
        
        # 过滤掉空行和只包含空白字符的行
        non_empty_lines = [line for line in lines if line.strip()]
        
        # 计算非空行的数量
        line_count = len(non_empty_lines)
        
        # 将非空行重新组合成一个新的字符串，用换行符连接
        processed_text = "\n".join(non_empty_lines)
        
        # 返回三个值：原始文本、行数、处理后的文本
        return (text_input, line_count, processed_text)

# 节点映射
NODE_CLASS_MAPPINGS = {
    "TextLineCounter": TextLineCounter
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TextLineCounter": "Text Line Counter"
}
