"""Explicit selection/setup refusal before NEW MediaPipe imports/RPC/engine."""
from .selection import selected_construction

async def execute(image, max_faces=10, min_confidence=0.5, resolution=512):
    selected_construction()
    from .wrapper import Media_Pipe_Face_Mesh_Preprocessor
    return Media_Pipe_Face_Mesh_Preprocessor().detect(image, max_faces, min_confidence, resolution)
