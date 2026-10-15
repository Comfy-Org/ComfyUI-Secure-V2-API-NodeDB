"""Owned text/value algorithms and scoped managed output annotations."""
import json
from comfy_api.latest import io, sdk
from .filename import parse_filename
from .limits import text as bounded_text, logical_label, json_work


class SimpleReadableMetadataTextViewerSG(io.ComfyNode):
    SDK_PERMISSIONS = ()
    FUNCTION = "execute"

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="Simple Readable Metadata Text Viewer-SG",
            display_name="Simple Readable Metadata 🧾 Text Viewer-SG", category="text/utils",
            inputs=[io.String.Input("text", default="", force_input=True)],
            outputs=[io.String.Output("text")], is_output_node=True)

    @classmethod
    def execute(cls, text):
        bounded_text(text)
        return io.NodeOutput(text, ui={"text": [text]})


class SavePositivePromptSG(io.ComfyNode):
    SDK_PERMISSIONS = ("output",)
    FUNCTION = "execute"
    POLARITY = "Positive"

    @classmethod
    def define_schema(cls):
        side = "POSITIVE" if cls.POLARITY == "Positive" else "NEGATIVE"
        return io.Schema(node_id=cls.__name__,
            display_name=f"Simple_Readable_Metadata_Save_Prompt ({side})-SG",
            category="utils/metadata", is_output_node=True,
            # Trusted execution-context bindings only: never function arguments
            # or hidden prompt export. The public owner annotation uses these.
            hidden=[io.Hidden.unique_id, io.Hidden.prompt, io.Hidden.extra_pnginfo],
            inputs=[io.String.Input("text", force_input=True,
                tooltip=f"FINAL TEXT to be connected to CLIP Text Encode {cls.POLARITY} node's box")],
            outputs=[io.String.Output("connect_to_CLIP_text_encode",
                tooltip=f"Connect this to your {side} CLIP Text Encode node input.")])

    @classmethod
    async def execute(cls, text):
        bounded_text(text)
        await sdk.ctx().output.record_text_input("text",
            title=f"{cls.POLARITY} Prompt (Saved)", metadata_prefix=f"{cls.POLARITY}Prompt")
        return io.NodeOutput(text, ui={"text": [text]})


class SaveNegativePromptSG(SavePositivePromptSG):
    POLARITY = "Negative"


class SimpleReadableMetadataSaveTextSG(io.ComfyNode):
    SDK_PERMISSIONS = ("assets", "output")
    FUNCTION = "execute"

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="SimpleReadableMetadataSaveTextSG",
            display_name="Simple Readable Metadata Save Text-SG", category="utils",
            inputs=[io.String.Input("text", force_input=True, multiline=True),
                    io.String.Input("filename_prefix", default="ComfyUI_text"),
                    io.Combo.Input("file_format", options=["txt", "json", "md"], default="txt"),
                    io.Boolean.Input("pretty_json", default=True)],
            outputs=[], is_output_node=True)

    @classmethod
    async def execute(cls, text, filename_prefix="ComfyUI_text", file_format="txt", pretty_json=True):
        bounded_text(text)
        bounded_text(filename_prefix, 1024)
        if file_format not in ("txt", "json", "md"):
            raise ValueError("declared text format required")
        filename_prefix = logical_label(parse_filename(filename_prefix))
        content = text
        if file_format == "json" and pretty_json:
            json_work(text)
            try:
                content = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                pass
        bounded_text(content)
        # Exact source first-free names, with a finite local scan profile.
        # Managed new_only publication never overwrites a racing writer.
        for counter in range(1, 4097):
            filename = f"{filename_prefix}_{counter:05d}.{file_format}"
            logical_label(filename)
            if not await sdk.ctx().assets.exists("output", filename):
                await sdk.ctx().output.write_text(content, filename, folder="output", mode="new_only")
                subfolder, _, basename = filename.rpartition("/")
                return io.NodeOutput(ui={"text_files": [{"filename": basename,
                    "subfolder": subfolder, "type": "output"}]})
        raise ValueError("first-free filename scan workload exceeded")
