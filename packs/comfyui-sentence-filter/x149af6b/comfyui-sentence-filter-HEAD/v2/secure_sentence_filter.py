"""Scalar IO adapter; computation, diagnostics and errors remain upstream's."""

from comfy_api.latest import io

from .sentence_filter_node import SentenceFilterNode as _OriginalSentenceFilterNode


class SentenceFilterNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SentenceFilterNode",
            display_name="Sentence Filter ✂️",
            category="text/processing",
            inputs=[
                io.String.Input(
                    "text", multiline=True, default="",
                    placeholder="Input text from workflow",
                ),
                io.String.Input(
                    "delete_words", optional=True, multiline=False, default="",
                    placeholder='Words to delete sentence, e.g. "Watermark" or "blonde, straight, young"',
                ),
                io.String.Input(
                    "replace_words", optional=True, multiline=False, default="",
                    placeholder='Words to find sentence for replacement, e.g. "blonde, straight"',
                ),
                io.String.Input(
                    "replacement_sentence", optional=True, multiline=True, default="",
                    placeholder="Replacement sentence (used when replace_words match)",
                ),
                io.Boolean.Input(
                    "case_sensitive", optional=True, default=False,
                    label_on="Case Sensitive", label_off="Case Insensitive",
                ),
            ],
            outputs=[
                io.String.Output(display_name="text"),
                io.Int.Output(display_name="sentences_deleted"),
                io.Int.Output(display_name="sentences_replaced"),
            ],
        )

    @classmethod
    def execute(
        cls,
        text: str,
        delete_words: str = "",
        replace_words: str = "",
        replacement_sentence: str = "",
        case_sensitive: bool = False,
    ) -> io.NodeOutput:
        return io.NodeOutput(*_OriginalSentenceFilterNode().filter_text(
            text, delete_words, replace_words, replacement_sentence, case_sensitive,
        ))
