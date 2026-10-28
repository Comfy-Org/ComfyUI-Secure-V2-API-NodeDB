import re


class MargeStringList:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "forceInput": True,
                    "multiline": True,
                }),
                "separator": ("STRING", {
                    "default": ", ",
                }),
                "sort_tags": ("BOOLEAN", {
                    "default": False,
                }),
                "case_sensitive": ("BOOLEAN", {
                    "default": False,
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "merge"
    CATEGORY = "text/tags"

    # Receive ComfyUI list outputs, such as WD14 Tagger's STRING list,
    # as one Python list instead of letting ComfyUI expand them downstream.
    INPUT_IS_LIST = True

    def _first(self, value, default=None):
        if isinstance(value, list):
            return value[0] if value else default
        return value

    def _flatten_texts(self, value):
        result = []

        if isinstance(value, list):
            for item in value:
                result.extend(self._flatten_texts(item))
        elif value is not None:
            result.append(str(value))

        return result

    def _split_tags(self, text):
        # WD14 Tagger usually returns comma-separated tags:
        # "tag_a, tag_b, tag_c"
        parts = text.split(",")
        tags = []

        for part in parts:
            tag = part.strip()

            # Remove empty entries caused by trailing commas.
            if not tag:
                continue

            # Normalize repeated whitespace without changing underscores.
            tag = re.sub(r"\s+", " ", tag)
            tags.append(tag)

        return tags

    def merge(self, text, separator=", ", sort_tags=False, case_sensitive=False):
        separator = self._first(separator, ", ")
        sort_tags = bool(self._first(sort_tags, False))
        case_sensitive = bool(self._first(case_sensitive, False))

        texts = self._flatten_texts(text)

        seen = set()
        merged = []

        for one_text in texts:
            for tag in self._split_tags(one_text):
                key = tag if case_sensitive else tag.lower()

                if key in seen:
                    continue

                seen.add(key)
                merged.append(tag)

        if sort_tags:
            merged.sort(key=lambda x: x.lower())

        result = separator.join(merged)

        return {
            "ui": {
                "text": [result],
            },
            "result": (result,),
        }


NODE_CLASS_MAPPINGS = {
    "MargeStringList": MargeStringList,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MargeStringList": "Merge String List",
}
