"""Original Light Tool PIL processing after a managed import supplies bytes.

No URL/network/filesystem access and no image re-encoding in this boundary.
The shared importer and its status policy remain SDK-owner responsibilities.
"""
import io
import json
from PIL import Image, ImageOps
from .nodes.light_tool_utils import pil2tensor


def image_from_encoded(payload, keep_alpha_channel):
    image = Image.open(io.BytesIO(payload))
    image = ImageOps.exif_transpose(image)
    has_alpha = 'A' in image.getbands()
    if has_alpha and keep_alpha_channel:
        image = image.convert('RGBA')
    else:
        image = image.convert('RGB')
    return pil2tensor(image)


def metadata_from_encoded(payload):
    try:
        source_img = Image.open(io.BytesIO(payload))
        source_metadata = source_img.info
    except json.JSONDecodeError:
        source_metadata = {}
    return json.dumps(source_metadata, ensure_ascii=False)
