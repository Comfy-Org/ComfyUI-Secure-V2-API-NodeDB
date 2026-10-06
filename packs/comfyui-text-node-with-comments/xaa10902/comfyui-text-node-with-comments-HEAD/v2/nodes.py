from comfy_api.latest import io
from .remove_comments import remove_comments

MAX_TEXT_BYTES = 65_536


class CDXOO_TextNodeWithComments(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="text-node-with-comments",
            display_name="Text Node With Comments (@cdxoo)",
            category="primitives",
            inputs=[io.String.Input("string", default="", multiline=True)],
            outputs=[io.String.Output()],
        )

    @classmethod
    def execute(cls, string):
        # Preserve upstream's TypeError for non-text inputs instead of coercing.
        if isinstance(string, str) and len(string.encode("utf-8", errors="surrogatepass")) > MAX_TEXT_BYTES:
            raise ValueError("string exceeds the 64 KiB text limit")
        result = remove_comments(string)
        if len(result.encode("utf-8", errors="surrogatepass")) > MAX_TEXT_BYTES:
            raise ValueError("result exceeds the 64 KiB text limit")
        return io.NodeOutput(result)
