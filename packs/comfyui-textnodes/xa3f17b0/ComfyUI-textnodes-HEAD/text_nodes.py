import re

class TidyTags:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "string": ("STRING", {"multiline": True, "forceInput": True, "default": ""}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("string",)
    FUNCTION = "tidy_tags"
    CATEGORY = "utils"

    def tidy_tags(self, string):
        if not string or not isinstance(string,(str,list)):
            return ""
        
        # Convert list to string
        if isinstance(string,list):
            string = ",".join(map(str, string))

        
        while True:
            # Eliminate redundant commas and strip whitespace around commas
            new_text = re.sub(r"[,\s\t\n]*,[,\s\t\n]*", ",", string)

            # Fix double spaces
            new_text = re.sub(r"\s\s+", " ", new_text)
            if new_text == string:
                break
            string = new_text

        string = string.strip(" ,\t\r\n")
        tags = string.split(',')
        seen = set()
        result = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                result.append(tag)
        string = ", ".join(result)

        # Clean up BREAKs
        string = re.sub(r"[,\s\n]*BREAK[,\s\n]*"," BREAK ", string)
        return (string,)

class PromptTruncate:
    """Truncates a text string to n tokens"""

    def __init__(self) -> None:
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "number_of_tokens": ("INT", {"default": 0 }),
                "string": ("STRING", {"default": "" }),
            }
        }

    CATEGORY = "utils"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("string",)

    FUNCTION = "execute"

    def execute(self, number_of_tokens, string):
        if not string or not isinstance(string,(str,list)):
            return ("",)
        string = string.strip(" ,\t\r\n")
        tags = string.split(',')
        string = ', '.join(tags[:number_of_tokens])
        string = re.sub(r"[,\s\n]*BREAK[,\s\n]*"," BREAK ", string)
        return (string,)

NODE_CLASS_MAPPINGS = {
    "Tidy Tags": TidyTags,
    "Prompt Truncate": PromptTruncate,
}
