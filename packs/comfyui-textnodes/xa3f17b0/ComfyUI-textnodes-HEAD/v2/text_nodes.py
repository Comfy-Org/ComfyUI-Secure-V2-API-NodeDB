import re
from comfy_api.latest import io

MAX_TEXT_BYTES = 65_536
MAX_LIST_ITEMS = 4096
MAX_OUTPUT_BYTES = 131_072


def _check_text(text):
    if isinstance(text, str) and len(text.encode("utf-8", errors="surrogatepass")) > MAX_TEXT_BYTES:
        raise ValueError("text exceeds the 64 KiB input limit")
    if isinstance(text, list) and len(text) > MAX_LIST_ITEMS:
        raise ValueError("text exceeds the 4096-item list limit")


def _output(text):
    if len(text.encode("utf-8", errors="surrogatepass")) > MAX_OUTPUT_BYTES:
        raise ValueError("text exceeds the 128 KiB output limit")
    return io.NodeOutput(text)


class TidyTags(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Tidy Tags", display_name="Tidy Tags", category="utils",
            inputs=[io.String.Input("string", multiline=True, force_input=True, default="")],
            outputs=[io.String.Output(display_name="string")],
        )

    @classmethod
    def execute(cls, string):
        _check_text(string)
        if not string or not isinstance(string, (str, list)):
            # Upstream returned bare "" here; normalize its intended STRING
            # socket into a valid V2 output, without inventing an output value.
            return _output("")
        if isinstance(string, list):
            chunks = []
            total_bytes = 0
            for value in string:
                chunk = str(value)
                total_bytes += len(chunk.encode("utf-8", errors="surrogatepass")) + bool(chunks)
                if total_bytes > MAX_TEXT_BYTES:
                    raise ValueError("text exceeds the 64 KiB input limit")
                chunks.append(chunk)
            string = ",".join(chunks)

        while True:
            new_text = re.sub(r"[,\s\t\n]*,[,\s\t\n]*", ",", string)
            new_text = re.sub(r"\s\s+", " ", new_text)
            if new_text == string:
                break
            string = new_text
        string = string.strip(" ,\t\r\n")
        tags = string.split(",")
        seen = set()
        result = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                result.append(tag)
        string = ", ".join(result)
        string = re.sub(r"[,\s\n]*BREAK[,\s\n]*", " BREAK ", string)
        return _output(string)


class PromptTruncate(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Prompt Truncate", display_name="Prompt Truncate", category="utils",
            inputs=[io.Int.Input("number_of_tokens", default=0), io.String.Input("string", default="")],
            outputs=[io.String.Output(display_name="string")],
        )

    @classmethod
    def execute(cls, number_of_tokens, string):
        _check_text(string)
        if not string or not isinstance(string, (str, list)):
            return _output("")
        # Non-empty lists deliberately retain upstream's .strip AttributeError.
        string = string.strip(" ,\t\r\n")
        tags = string.split(",")
        string = ", ".join(tags[:number_of_tokens])
        string = re.sub(r"[,\s\n]*BREAK[,\s\n]*", " BREAK ", string)
        return _output(string)


NODE_CLASS_MAPPINGS = {"Tidy Tags": TidyTags, "Prompt Truncate": PromptTruncate}
