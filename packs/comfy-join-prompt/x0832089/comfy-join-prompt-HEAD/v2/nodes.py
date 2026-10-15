"""Pinned Join Prompt algorithms, with bounded pack-local scalar computation."""
import json

from comfy_api.latest import io

MAX_TEXT_BYTES = 65536
MAX_OUTPUT_BYTES = 1048576


def _bound_text(value):
    # Malformed non-strings retain the algorithm's native failure/falsey paths.
    if isinstance(value, str) and len(value.encode("utf-8", errors="surrogatepass")) > MAX_TEXT_BYTES:
        raise ValueError("Join Prompt: 64 KiB input limit")


class JoinStrings(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()
    ESCAPED_DELIMITERS = {r"\n": "\n", r"\r": "\r", r"\t": "\t"}

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="jupo.JoinPrompt.JoinStrings", display_name="Join Strings", category="jupo/JoinPrompt",
            inputs=[
                io.Autogrow.Input("texts", template=io.Autogrow.TemplatePrefix(
                    io.String.Input("text"), prefix="text_", min=1, max=50)),
                io.String.Input("delimiter", default="", advanced=True),
                io.Boolean.Input("cleanup", default=False, advanced=True),
            ], outputs=[io.String.Output()],
        )

    @classmethod
    def execute(cls, texts: io.Autogrow.Type, delimiter="", cleanup=False):
        return io.NodeOutput(cls.join_strings(texts.values(), delimiter, cleanup))

    @classmethod
    def parse_delimiter(cls, delimiter):
        for escaped, value in cls.ESCAPED_DELIMITERS.items():
            delimiter = delimiter.replace(escaped, value)
        return delimiter

    @classmethod
    def cleanup_by_comma(cls, text):
        lines = text.split("\n")
        to_join = []
        for line in lines:
            cleaned_tags = []
            tags = line.split(",")
            for tag in tags:
                cleaned_tags.append(tag.strip())
            cleaned_line = ", ".join(cleaned_tags)
            to_join.append(cleaned_line)
        return "\n".join(to_join)

    @classmethod
    def join_strings(cls, to_join, delimiter, cleanup):
        to_join = list(to_join)
        if len(to_join) > 50:
            raise ValueError("Join Prompt: at most 50 text inputs")
        _bound_text(delimiter)
        for text in to_join:
            _bound_text(text)
        if cleanup:
            to_join = [cls.cleanup_by_comma(text) for text in to_join]
        delimiter = cls.parse_delimiter(delimiter)
        # Inspect only real strings; malformed values still fail in native join.
        if isinstance(delimiter, str) and all(isinstance(text, str) for text in to_join):
            size = sum(len(text.encode("utf-8", errors="surrogatepass")) for text in to_join)
            size += max(0, len(to_join) - 1) * len(delimiter.encode("utf-8", errors="surrogatepass"))
            if size > MAX_OUTPUT_BYTES:
                raise ValueError("Join Prompt: 1 MiB projected output limit")
        return delimiter.join(to_join)


class JoinPrompt(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="jupo.JoinPrompt.JoinPrompt", display_name="Join Prompt", category="jupo/JoinPrompt",
            inputs=[
                io.String.Input("prev", optional=True, force_input=True),
                io.String.Input("text", multiline=True),
                io.String.Input("options", extra_dict={"hidden": True}, default="", optional=True),
            ], outputs=[io.String.Output()],
        )

    @classmethod
    def execute(cls, text, prev="", options=""):
        _bound_text(options)
        _bound_text(text)
        _bound_text(prev)
        to_join = []
        if prev:
            to_join.append(prev)
        if text:
            to_join.append(text)
        try:
            options_dict = json.loads(options)
        except Exception:
            options_dict = {}
        delimiter = options_dict.get("delimiter", "")
        cleanup = options_dict.get("cleanup", False)
        return io.NodeOutput(JoinStrings.join_strings(to_join, delimiter, cleanup))
