"""Owned catalogue routes; original list/version/error algorithms retained."""
import os
import re
import json
from .core.style import StyleSet
from .core.palette import PaletteSet
from .data.predefined_styles import PREDEFINED_STYLES
from .data.predefined_palettes import PREDEFINED_PALETTES

def _json_response(body, status=200):
    return {"status":status,"content_type":"application/json","body":json.dumps(body)}


def _styles_as_list(styles: StyleSet, add_none=False):
    """
    Generates a list of style data to be sent to the frontend.
    Args:
        styles: The `StyleSet` object containing the styles to be sent.
    Returns:
        list[list[str]]: A nested list where each inner list contains
                         the style information in the following format:

            [0] name        (str): The name of the style.
            [1] category    (str): The category to which the style belongs.
            [2] description (str): Description of the style.
            [3] tags        (str): Tags associated with the style, comma-separated
            [4] thumbnail   (str): The filename of the thumbnail image (e.g. "casual_photo.jpg")
    """
    result = []

    # add "none" option if requested
    if add_none:
        result.append(["none"])

    for style in styles:
        style_data : list[str] = [
            style.name,                  # 0: style name
            style.category,              # 1: category
            style.description,           # 2: description
            style.tags,                  # 3: comma-separated list of tags
            style.slug,                  # 4: url-friendly slug (used for thumbnail filenames)
        ]
        result.append(style_data)
    return result


def _palettes_as_list(palettes: PaletteSet, add_none=False) -> list[str]:
    """
    Generates a list of palette data to be sent to the frontend.
    Args:
        palettes: The `PaletteSet` object containing the palettes to be sent.
    Returns:
        list[list[str]]: A nested list where earch inner list contains
                         the palette information in the following format:

            [0] name        (str): The name of the palette.
            [1] description (str): Description of the palette.
            [2] tags        (str): Tags associated with the style, comma-separated
            [3] hex1        (str): The first color in hex format.
            [4] color1      (str): The name of the first color.
            [5] hex2        (str): The second color in hex format.
            [6] color2      (str): The name of the second color.
            ....
            [N*2+1] hexN   (str): The Nth color in hex format.
            [N*2+2] colorN (str): The name of the Nth color.
    """
    result = []

    # add "none" option if requested
    if add_none:
        result.append(["none"])

    for palette in palettes:
        palette_data : list[str] = [
            palette.name,        # 0: palette name
            palette.description, # 1: description
            palette.tags,        # 2: comma-separated list of tags
        ]
        for hex, color, _, _ in palette.items():
            palette_data.append( hex   )
            palette_data.append( color )
        result.append( palette_data )
    return result


def _sanitize_filename(filename: str) -> str:
    """
    Sanitizes a given filename to ensure it is valid and secure for most file systems.

    This function removes any characters from the filename that are not
    alphanumeric, underscores, or hyphens. This sanitization process helps
    in making filenames safe from potential security threats and reduces the
    risk of errors due to unsupported characters in different operating systems.

    Args:
        filename (str): The original filename to be sanitized.
    Returns:
        A sanitized version of the input filename,
        suitable for most file systems and secure against common threats.
    """
    name, ext = os.path.splitext( os.path.basename(filename) )
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', name) #< remove any non-alphanumeric characters from the name
    safe_ext  = re.sub(r'[^a-zA-Z0-9]'  , '', ext ) #< remove any non-alphanumeric characters from the extension
    return f"{safe_name}.{safe_ext}" if safe_ext else safe_name


async def get_palettes_by_version(request):
    """
    Retrieves a list of palettes based on the specified collection version.
    Example usage:
       GET /zi_power/palettes/by_version?v=1.2.3
    """
    query = request.get("query", {})

    # extract and clean the version parameter from the request query
    version = (query.get("v") or query.get("version") or "").strip()

    # check if the version parameter is provided
    if not version:
        return _json_response(
            {"error": "Missing required parameter: 'v' or 'version'"},
            status=400)

    # check if any palette exist for the specified version
    palettes = PREDEFINED_PALETTES.by_version(version)
    if not palettes:
        return _json_response(
            {"error": f"Palette version '{version}' not found"}, 
            status=404)

    # respond with the style data
    return _json_response( _palettes_as_list(palettes, add_none=True) )


async def get_styles_by_version(request):
    """
    Retrieves a list of styles based on the specified version.
    Example usage:
        GET /zi_power/styles/by_version?v=1.2.3
    """
    query = request.get("query", {})

    # extract and clean the version parameter from the request query
    version = (query.get("v") or query.get("version") or "").strip()

    # check if the version parameter is provided
    if not version:
        return _json_response(
            {"error": "Missing required parameter: 'v' or 'version'"},
            status=400)

    # check if any styles exist for the specified version
    styles = PREDEFINED_STYLES.by_version(version)
    if not styles:
        return _json_response(
            {"error": f"Style version '{version}' not found"}, 
            status=404)

    # respond with the style data
    return _json_response( _styles_as_list(styles, add_none=True) )
