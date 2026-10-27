import json

class JSONExtractorFourWay:
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "json_string": ("STRING", {"multiline": True, "default": ""}),
                "key_1": ("STRING", {"default": "name"}),
                "key_2": ("STRING", {"default": "instruct"}),
                "key_3": ("STRING", {"default": "text"}),
                "key_4": ("STRING", {"default": "other"}),
                "delimiter": ("STRING", {"default": "\n"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("output_1", "output_2", "output_3", "output_4")
    FUNCTION = "extract_json"
    CATEGORY = "CustomNodes/TextProcessing"

    def extract_json(self, json_string, key_1, key_2, key_3, key_4, delimiter):
        try:
            # 处理可能的单引号问题
            clean_json = json_string.replace("'", '"')
            data = json.loads(clean_json)
            
            # 确保数据是列表格式
            if not isinstance(data, list):
                data = [data]
            
            # 初始化四个列表
            lists = [[] for _ in range(4)]
            keys = [key_1, key_2, key_3, key_4]
            
            for item in data:
                for i in range(4):
                    current_key = keys[i]
                    # 如果 key 存在则提取，否则跳过
                    if current_key in item:
                        lists[i].append(str(item[current_key]))
            
            # 合并结果
            results = [delimiter.join(lst) for lst in lists]
            
            return tuple(results)
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            return (error_msg, "", "", "")

NODE_CLASS_MAPPINGS = {
    "JSONExtractorFourWay": JSONExtractorFourWay
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "JSONExtractorFourWay": "ZFL JSON Extractor"
}