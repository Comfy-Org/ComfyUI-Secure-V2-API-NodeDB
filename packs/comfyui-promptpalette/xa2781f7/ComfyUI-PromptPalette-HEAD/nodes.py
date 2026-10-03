import os


class PromptPalette:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": (
                    "STRING",
                    {"default": "", "multiline": True},
                ),
                "delimiter": (
                    ["comma", "space", "none"],
                    {"default": "comma"},
                ),
                "line_break": (
                    "BOOLEAN",
                    {"default": True},
                ),
            },
            "optional": {"prefix": ("STRING", {"forceInput": True})},
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "process"
    CATEGORY = "utils"

    def process(self, text, delimiter, line_break, prefix=None):
        lines = text.split("\n")
        filtered_lines = []
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
            # Skip commented lines
            if line.strip().startswith("//"):
                continue
            # Remove inline comments
            if "//" in line:
                line = line.split("//")[0].rstrip()
            # Add suffix based on delimiter setting
            if delimiter == "comma":
                line = line + ", "
            elif delimiter == "space":
                line = line + " "
            # "none" adds nothing
            filtered_lines.append(line)

        # Join lines based on line_break setting
        if line_break:
            result = "\n".join(filtered_lines)
        else:
            result = "".join(filtered_lines)

        # Add prefix if provided
        if prefix:
            if result:
                if line_break:
                    result = prefix + "\n" + result
                else:
                    result = prefix + result
            else:
                result = prefix

        return (result,)


NODE_CLASS_MAPPINGS = {"PromptPalette": PromptPalette}
NODE_DISPLAY_NAME_MAPPINGS = {"PromptPalette": "Prompt Palette"}
WEB_DIRECTORY = os.path.join(os.path.dirname(os.path.realpath(__file__)), "web")
