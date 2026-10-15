"""
File    : load_zimage_model.py
Purpose : Node to load a Z-Image/Z-Image-Turbo diffusion model.
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Jul 22, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
"""
import nodes
import comfy.sd
import folder_paths
from comfy_api.latest import io
from .core.system import logger


class LoadZImageModel(io.ComfyNode):
    xTITLE         = "Load Z-Image Model (safetensors / gguf)"
    xDESCRIPTION   = (
        "Load the Z-Image Diffusion Model in safetensors and GGUF format. "
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
                "load model", "unet loader", "diffusion model loader", "z-image", "zimage", "gguf loader"
            ],
            inputs=[
                io.Combo.Input  ("checkpoint", options=cls.diffusion_models(),
                                 tooltip="The Z-Image generative diffusion model checkpoint."),
                io.Boolean.Input("file_filter", default=False, label_off="Show All Files", label_on="Z-Image Checkpoints Only",
                                 tooltip="If True, all available checkpoints will be listed, including those that may not be compatible."),
            ],
            outputs=[
                io.Model.Output(tooltip="The loaded Z-Image diffusion model."),
            ]
        )

    #__ FUNCTION __________________________________________
    @classmethod
    def execute(cls,
                checkpoint : str,
                file_filter: bool = False,
                ) -> io.NodeOutput:
        model_output = cls.load_unet(checkpoint)
        return io.NodeOutput(model_output, )


    #__ internal functions ________________________________

    @classmethod
    def diffusion_models(cls) -> list[str]:
        """
        Get a list of available diffusion models, including standard models and GGUF variants.
        """
        models : list[str] = folder_paths.get_filename_list("diffusion_models")
        models.extend( cls.diffusion_models_gguf() )
        models.sort()
        return models


    @classmethod
    def diffusion_models_gguf(cls) -> list[str]:
        """
        Get a list of available GGUF-formatted diffusion model checkpoints.
        """
        UnetLoaderGGUF = nodes.NODE_CLASS_MAPPINGS.get("UnetLoaderGGUF")
        if UnetLoaderGGUF is None:
            return []
        return folder_paths.get_filename_list("unet_gguf")


    @classmethod
    def load_unet(cls, unet_name: str):
        """
        Load a diffusion model, supporting both standard safetensors and GGUF formats.
        """
        # handle GGUF format using UnetLoaderGGUF
        if unet_name.upper().endswith(".GGUF"):
            gguf_model = cls.load_unet_gguf(unet_name)
            return gguf_model[0] if isinstance(gguf_model, tuple) else gguf_model

        # default comfyui diffusion model loading
        model_options = {}
        unet_path = folder_paths.get_full_path_or_raise("diffusion_models", unet_name)
        model = comfy.sd.load_diffusion_model(unet_path, model_options=model_options)
        return model


    @classmethod
    def load_unet_gguf(cls,
                       unet_name: str,
                       dequant_dtype  : str  | None = None,
                       patch_dtype    : str  | None = None,
                       patch_on_device: bool | None = None) -> tuple:
        """
        Locate, instantiate, and execute the "UnetLoaderGGUF" node dynamically.

        Args:
            unet_name      : Name of the GGUF UNET file to load.
            dequant_dtype  : Determines internal precision. Can be "default", "target"
                             (adapts to activation), or explicit type names like "float32",
                             "float16", "bfloat16" to force dequantization precision.
            patch_dtype    : Data type used to apply additional patches (e.g., LoRAs) onto the base
                             model. Note: "default" and "target" are supported. The ComfyUI-GGUF
                             code indicates that using custom types may affect image quality.
            patch_on_device: If True, attempts to apply additional patches (like LoRAs)
                             directly on the GPU device.
        Returns:
            A tuple containing the loaded UNET model object.
        """
        UnetLoaderGGUF = nodes.NODE_CLASS_MAPPINGS.get("UnetLoaderGGUF")
        if UnetLoaderGGUF is None:
            raise RuntimeError(
                "The 'UnetLoaderGGUF' node is not available. "
                "Please ensure the city96 ComfyUI-GGUF custom nodes are installed.")

        # arguments aligned with the expected function signature
        kwargs = {
            "unet_name"      : unet_name,
            "dequant_dtype"  : dequant_dtype,
            "patch_dtype"    : patch_dtype,
            "patch_on_device": patch_on_device,
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        # attempt to execute the node using modern V3 schema (direct class 'execute' method)
        if hasattr(UnetLoaderGGUF, "execute") and callable(getattr(UnetLoaderGGUF, "execute")):
            try:
                return UnetLoaderGGUF.execute(**kwargs)
            except Exception as e:
                logger.warning(f"Failed to use the modern 'execute' method on UnetLoaderGGUF: {e}")

        # safely instantiate the node for legacy execution and brute-force approach
        try:
            node_instance = UnetLoaderGGUF()
        except Exception as e:
            logger.warning(f"Could not instantiate UnetLoaderGGUF class: {e}")
            node_instance = None

        # attempt legacy node execution via the 'FUNCTION' class property
        legacy_func_name = getattr(UnetLoaderGGUF, "FUNCTION", None)
        if legacy_func_name and node_instance and hasattr(node_instance, legacy_func_name):
            method = getattr(node_instance, legacy_func_name)
            return method(**kwargs)

        # fallback to brute-force attempt using common method names
        for method_name in ["load_unet", "load_model", "execute"]:
            if node_instance and hasattr(node_instance, method_name):
                emergency_method = getattr(node_instance, method_name)
                return emergency_method(**kwargs)

            elif hasattr(UnetLoaderGGUF, method_name):
                emergency_method = getattr(UnetLoaderGGUF, method_name)
                return emergency_method(**kwargs)

        raise AttributeError("UnetLoaderGGUF found, but no compatible execution method was found.")