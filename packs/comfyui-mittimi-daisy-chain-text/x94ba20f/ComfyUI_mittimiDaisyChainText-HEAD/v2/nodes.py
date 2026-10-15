from comfy_api.latest import io

MAX_TEXT_BYTES = 65_536
MAX_SEQUENCE_ITEMS = 4096


def _bound(value):
    # Do not coerce malformed direct-call values: Python's native addition below
    # preserves the original errors and (out-of-schema) sequence behavior.
    if isinstance(value, str):
        if len(value.encode("utf-8", errors="surrogatepass")) > MAX_TEXT_BYTES:
            raise ValueError("text exceeds the 64 KiB input limit")
    elif isinstance(value, (list, tuple, bytes)) and len(value) > MAX_SEQUENCE_ITEMS:
        raise ValueError("value exceeds the sequence input limit")


class DaisyChainTextMittimi(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="DaisyChainTextMittimi",
            display_name="DaisyChainText",
            category="mittimiTools",
            inputs=[
                io.String.Input("text_that_comes_first"),
                io.String.Input("text", multiline=True),
                io.String.Input("text_that_comes_last", optional=True),
            ],
            outputs=[io.String.Output(display_name="text")],
        )

    @classmethod
    def execute(cls, text, text_that_comes_first="", text_that_comes_last=""):
        for value in (text_that_comes_first, text, text_that_comes_last):
            _bound(value)
        result = text_that_comes_first + text + text_that_comes_last
        return io.NodeOutput(result)
