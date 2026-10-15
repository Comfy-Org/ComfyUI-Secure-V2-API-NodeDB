from .._annotator import common_annotator_call
from .._diffusionedge.schema_helpers import define_preprocessor_inputs, INPUT
from .selection import require_constructor
import os, sys
import subprocess, threading

def install_deps():
    require_constructor()

class Media_Pipe_Face_Mesh_Preprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return define_preprocessor_inputs(
            max_faces=INPUT.INT(default=10, min=1, max=50), #Which image has more than 50 detectable faces?
            min_confidence=INPUT.FLOAT(default=0.5, min=0.1),
            resolution=INPUT.RESOLUTION()
        )
        
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "detect"

    CATEGORY = "ControlNet Preprocessors/Faces and Poses Estimators"

    def detect(self, image, max_faces=10, min_confidence=0.5, resolution=512):
        #Ref: https://github.com/Fannovel16/comfy_controlnet_preprocessors/issues/70#issuecomment-1677967369
        install_deps()
        from .detector import MediapipeFaceDetector
        return (common_annotator_call(MediapipeFaceDetector(), image, max_faces=max_faces, min_confidence=min_confidence, resolution=resolution), )

NODE_CLASS_MAPPINGS = {
    "MediaPipe-FaceMeshPreprocessor": Media_Pipe_Face_Mesh_Preprocessor
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MediaPipe-FaceMeshPreprocessor": "MediaPipe Face Mesh"
}