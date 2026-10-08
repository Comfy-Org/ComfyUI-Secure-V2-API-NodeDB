"""Secure V2 entrypoint; legacy modules remain archival and unexecuted."""
from .loader_nodes import SimpleReadableMetadataMAXSG, SimpleReadableMetadataSG, SimpleReadableMetadataVideoSG
from .text_nodes import SimpleReadableMetadataTextViewerSG, SimpleReadableMetadataSaveTextSG, SavePositivePromptSG, SaveNegativePromptSG

NODE_CLASS_MAPPINGS = {
    "SimpleReadableMetadataMAXSG": SimpleReadableMetadataMAXSG,
    "SimpleReadableMetadataSG": SimpleReadableMetadataSG,
    "Simple Readable Metadata Text Viewer-SG": SimpleReadableMetadataTextViewerSG,
    "SimpleReadableMetadataSaveTextSG": SimpleReadableMetadataSaveTextSG,
    "SimpleReadableMetadataVideoSG": SimpleReadableMetadataVideoSG,
    "SavePositivePromptSG": SavePositivePromptSG,
    "SaveNegativePromptSG": SaveNegativePromptSG
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SimpleReadableMetadataMAXSG": "Simple Readable Metadata MAX-SG",
    "SimpleReadableMetadataSG": "Simple Readable Metadata-SG",
    "Simple Readable Metadata Text Viewer-SG": "Simple Readable Metadata 🧾 Text Viewer-SG",
    "SimpleReadableMetadataSaveTextSG": "Simple Readable Metadata Save Text-SG",
    "SimpleReadableMetadataVideoSG": "Simple Readable Metadata (VIDEO)-SG",
    "SavePositivePromptSG": "Simple_Readable_Metadata_Save_Prompt (POSITIVE)-SG",
    "SaveNegativePromptSG": "Simple_Readable_Metadata_Save_Prompt (NEGATIVE)-SG"
}

WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
