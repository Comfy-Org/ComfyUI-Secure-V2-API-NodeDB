"""TEST-only exact STRING consumer; forwards the seeded ImageRef unchanged."""
from comfy_api.latest import io, sdk


class NedSentenceFilterStringOracle(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="NedSentenceFilterStringOracle", category="tests/SentenceFilter",
            inputs=[
                io.String.Input("actual", multiline=True, default="", placeholder="Input text from workflow"),
                io.String.Input("expected", multiline=True, default="", placeholder="Input text from workflow"),
                io.Image.Input("image"),
            ],
            outputs=[io.Image.Output()],
        )

    @classmethod
    def execute(cls, actual, expected, image):
        if type(actual) is not str or type(expected) is not str:
            raise AssertionError("SentenceFilter TEST exact string type mismatch")
        if actual != expected:
            raise AssertionError("SentenceFilter TEST exact string mismatch")
        if not isinstance(image, sdk.ImageRef):
            raise AssertionError("SentenceFilter TEST seed must be ImageRef")
        return io.NodeOutput(image)
