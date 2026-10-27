"""5つの文字列を改行で結合する ComfyUI カスタムノード。"""


class StringConcatenate5:
    """5入力の文字列を改行区切りで1つに結合し、文字列出力とプレビューを返すノード。"""

    @classmethod
    def INPUT_TYPES(cls):
        """ノードの入力ソケットとウィジェット定義を返す。"""
        string_input = ("STRING", {"default": "", "multiline": True})
        return {
            "required": {
                "string_1": string_input,
                "string_2": string_input,
                "string_3": string_input,
                "string_4": string_input,
                "string_5": string_input,
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("text", "preview")
    FUNCTION = "concatenate"
    CATEGORY = "text"
    OUTPUT_NODE = True
    DESCRIPTION = "5つの文字列を改行で結合。ノード上でプレビュー表示。出力は未接続でもエラーになりません。"

    def concatenate(self, string_1, string_2, string_3, string_4, string_5):
        """5つの文字列を改行で結合し、UIプレビュー付きで2つの同一文字列を返す。"""
        result = "\n".join((string_1, string_2, string_3, string_4, string_5))
        return {"ui": {"text": [result]}, "result": (result, result)}


# ComfyUI が読み込むノードクラス登録
NODE_CLASS_MAPPINGS = {
    "StringConcatenate5": StringConcatenate5,
}

# ノード一覧に表示する名称
NODE_DISPLAY_NAME_MAPPINGS = {
    "StringConcatenate5": "5文字列改行結合",
}
