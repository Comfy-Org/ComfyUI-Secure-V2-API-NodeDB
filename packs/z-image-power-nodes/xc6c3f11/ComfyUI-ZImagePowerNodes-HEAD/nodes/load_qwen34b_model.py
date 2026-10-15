"""
File    : load_qwen34b_model.py
Purpose : Node to load the text encoder model (Qwen-3-4B) for use with Z-Image.
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Jul 22, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
"""
import torch
import nodes
import comfy.sd
import folder_paths
from comfy_api.latest import io
from .core.system  import logger


class LoadQwen34bModel(io.ComfyNode):
    xTITLE         = "Load Qwen3-4B Model (safetensors / gguf)"
    xDESCRIPTION   = (
        "Loads the Z-Image Text Encoder (Qwen3-4B) in safetensors or GGUF format. "
        "Note that the 'ComfyUI-GGUF' custom nodes by city96 must be installed "
        "for GGUF files to be detected by this node."
        )
    xCATEGORY      = ""
    xCOMFY_NODE_ID = ""
    xDEPRECATED    = False

    #__ INPUT / OUTPUT ____________________________________
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            display_name   = cls.xTITLE,
            description    = cls.xDESCRIPTION,
            category       = cls.xCATEGORY,
            node_id        = cls.xCOMFY_NODE_ID,
            is_deprecated  = cls.xDEPRECATED,
            search_aliases = [
                "load clip", "clip loader", "text encoder loader", "qwen", "qwen3", "llm loader", "gguf loader", "z-image"
            ],
            inputs=[
                io.Combo.Input  ("checkpoint", options=cls.text_encoders(),
                                 tooltip="The text encoder checkpoint, typically a variant of Qwen3-4B model."),
                io.Boolean.Input("file_filter", default=False, label_off="Show All Files", label_on="Qwen3-4B Checkpoints Only",
                                 tooltip="If True, all available checkpoints will be listed, including those that may not be compatible."),
                io.Boolean.Input("run_on_gpu", default=True,
                                 tooltip="If enabled, the text encoder will be executed on the CPU rather than the GPU. "
                                         "This will consume less VRAM but will be significantly slower."),
            ],
            outputs=[
                io.Clip.Output(tooltip="The loaded text-encoder model for encoding text prompts."),
            ]
        )

    #__ FUNCTION __________________________________________
    @classmethod
    def execute(cls,
                checkpoint : str,
                file_filter: bool = False,
                run_on_gpu : bool = False,
                ) -> io.NodeOutput:
        clip_device = "default" if run_on_gpu else "cpu"
        clip_output = cls.load_clip(checkpoint, type="lumina2", device=clip_device)
        return io.NodeOutput(clip_output, )


    #__ internal functions ________________________________

    @classmethod
    def text_encoders(cls) -> list[str]:
        """
        Get a list of available text encoders, including standard models and GGUF variants.

        Standard 'safetensors' checkpoints recognized by ComfyUI must be
        located within the "/text_encoders" directory.
        GGUF-formatted checkpoints are only visible if the custom nodes from
        https://github.com/city96/ComfyUI-GGUF are installed; the required
        directory for these files is managed by said custom nodes.
        """
        text_encoders : list[str] =  folder_paths.get_filename_list("text_encoders")
        text_encoders.extend( cls.text_encoders_gguf() )
        text_encoders.sort()
        return text_encoders


    @classmethod
    def text_encoders_gguf(cls) -> list[str]:
        """
        Get a list of available GGUF-formatted text encoder checkpoints.

        This method returns a list of filenames for GGUF-based checkpoints if
        the "ComfyUI-GGUF" nodes are installed; otherwise, an empty list.
        """
        UnetLoaderGGUF = nodes.NODE_CLASS_MAPPINGS.get("UnetLoaderGGUF")
        if UnetLoaderGGUF is None:
            return []
        return folder_paths.get_filename_list("clip_gguf")


    @classmethod
    def load_clip(cls, clip_name: str, *, type: str = "lumina2", device: str = "default"):
        """
        Load a text-encoder model, supporting both standard safetensors and GGUF formats.

        Args:
            clip_name : The filename or path of the text-encoder model to load.
            type      : The text-encoder model architecture type (e.g., 'lumina2', 'stable_diffusion').
                        Defaults to 'lumina2' for Z-Image process.
            device    : The target device for the model ('cpu' or 'default').
        Returns:
            The loaded text-encoder model checkpoint (CLIP for ComfyUI).
        """
        # handle GGUF format
        if clip_name.upper().endswith(".GGUF"):
            gguf_clip = cls.load_clip_gguf(clip_name, type=type)
            return gguf_clip[0] if isinstance(gguf_clip,tuple) else gguf_clip

        # default ComfyUI text-encoder loading
        clip_type = getattr(comfy.sd.CLIPType, type.upper(), comfy.sd.CLIPType.STABLE_DIFFUSION)
        model_options = {}
        if device == "cpu":
            model_options["load_device"] = model_options["offload_device"] = torch.device("cpu")
        clip_path = folder_paths.get_full_path_or_raise("text_encoders", clip_name)
        clip = comfy.sd.load_clip(ckpt_paths=[clip_path], embedding_directory=folder_paths.get_folder_paths("embeddings"), clip_type=clip_type, model_options=model_options)
        return clip


    @classmethod
    def load_clip_gguf(cls, clip_name: str, *, type: str = "lumina2"):
        """
        Locate, instantiate, and execute the "CLIPLoaderGGUF" node dynamically.

        Args:
            clip_name : The filename of the GGUF model to load.
            type      : The architecture identifier for the CLIP loader.
        Returns:
            The output provided by the GGUF loader node, typically a tuple containing the model instance.
        """
        # attempt to retrieve the CLIPLoaderGGUF node class from the global mapping
        CLIPLoaderGGUF = nodes.NODE_CLASS_MAPPINGS.get("CLIPLoaderGGUF")
        if CLIPLoaderGGUF is None:
            raise RuntimeError(
                "The 'CLIPLoaderGGUF' node is not available. "
                "Please ensure the city96 ComfyUI-GGUF custom nodes are installed.")

        # attempt to execute the node using modern API (direct class 'execute' method)
        if hasattr(CLIPLoaderGGUF, "execute") and callable(getattr(CLIPLoaderGGUF, "execute")):
            try:
                return CLIPLoaderGGUF.execute(clip_name=clip_name, type=type)
            except Exception as e:
                logger.warning(f"Failed to use the modern 'execute' method on CLIPLoaderGGUF: {e}")

        # safely instantiate the node for legacy use and brute-force approach
        try:
            node_instance = CLIPLoaderGGUF()
        except Exception as e:
            logger.warning(f"Could not instantiate CLIPLoaderGGUF class: {e}")
            node_instance = None

        # attempt legacy comfyui system execution via 'FUNCTION' property
        legacy_func_name = getattr(CLIPLoaderGGUF, "FUNCTION", None)
        if legacy_func_name and node_instance and hasattr(node_instance, legacy_func_name):
            method = getattr(node_instance, legacy_func_name)
            return method(clip_name=clip_name, type=type)

        # emergency brute-force discovery of execution methods
        for method_name in ["load_clip", "execute"]:
            # attempt instance method
            if node_instance and hasattr(node_instance, method_name):
                emergency_method = getattr(node_instance, method_name)
                return emergency_method(clip_name=clip_name, type=type)

            # attempt class method
            elif hasattr(CLIPLoaderGGUF, method_name):
                emergency_method = getattr(CLIPLoaderGGUF, method_name)
                return emergency_method(clip_name=clip_name, type=type)

        raise AttributeError("CLIPLoaderGGUF found, but no compatible execution method was found.")
