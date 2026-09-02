"""Secure, tensor-only detector providers for Impact Subpack."""
from __future__ import annotations

from typing import Any

from ._secure_runtime import SCHEMAS, bind_node, sdk


_PERSON_FACE = sdk.HuggingFaceWeight(
    repo_id="iitolstykh/YOLO-Face-Person-Detector",
    filename="model.safetensors",
    folder="detection",
    revision="b3d071aedccd46a3b2d4b40609da6880a815f395",
    sha256="278524fbd3c5b736493294983f91ef49a3fe91b5c97188ec8cc8be58288577fd",
    on_demand=True,
)

_MODELS = {
    "bbox/yolov8x_person_face.safetensors": _PERSON_FACE,
}


async def _provider(model_name: str, **_kwargs: Any):
    try:
        weight = _MODELS[str(model_name)]
    except KeyError as error:
        raise ValueError(
            "Impact Subpack accepts only its declared tensor-only detector "
            f"weights; unknown model {model_name!r}"
        ) from error
    installed = await sdk.ctx().models.download_huggingface_weights(
        repo_id=weight.repo_id,
        filename=weight.filename,
        folder=weight.folder,
        revision=weight.revision,
        sha256=weight.sha256,
    )
    if installed != weight.catalogue_name:
        raise RuntimeError("the detector weight provider returned the wrong asset")
    bbox = {
        "secure_kind": "impact.ultralytics_bbox",
        "weight": installed,
        "architecture": "yolov8x",
        "input_size": 640,
        "classes": ["person", "face"],
    }
    # This declared model is bounding-box-only, matching the upstream
    # provider's NO_SEGM_DETECTOR result for bbox/* selections.
    return bbox, None


NODE_CLASS_MAPPINGS = {
    "UltralyticsDetectorProvider": bind_node(
        "UltralyticsDetectorProvider",
        _provider,
        permissions=("models.download",),
        required_weights=(_PERSON_FACE,),
    ),
}

NODE_DISPLAY_NAME_MAPPINGS = {}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "SCHEMAS"]
