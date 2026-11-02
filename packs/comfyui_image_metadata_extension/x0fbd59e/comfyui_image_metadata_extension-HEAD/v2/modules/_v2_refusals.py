"""Behaviours of the original that Secure Nodes V2 cannot reproduce exactly; each is refused
by name instead of being changed silently (SECURE_CONVERSION.md, "Known differences")."""

PACK = "comfyui_image_metadata_extension"


class SecureConversionRefusal(RuntimeError):
    """A behaviour of the original that the Secure Nodes V2 conversion refuses by name."""


JPEG = (
    f"{PACK}/SaveImageWithMetaData: output_format {{fmt!r}} is not supported on Secure Nodes V2. The original "
    "encodes JPEG with Pillow's default chroma subsampling and inserts a piexif EXIF block; the managed image "
    "writer encodes JPEG with 4:4:4 subsampling and its own EXIF layout, so the file would differ. Use png, "
    "png_with_json, webp or webp_with_json."
)

SUBDIR_ESCAPE = (
    f"{PACK}/SaveImageWithMetaData: subdirectory_name {{name!r}} leaves the output folder. The original wrote "
    "there without a check; Secure Nodes V2 writes only inside the output folder. Use a relative folder name."
)

SUBDIR_BACKSLASH = (
    f"{PACK}/SaveImageWithMetaData: {{field}} {{name!r}} contains a backslash. On a Linux host the original "
    "kept it as part of a file or folder name; the managed image writer treats it as a folder separator. Use '/'."
)

SUBDIR_WITH_PREFIX_FOLDER = (
    f"{PACK}/SaveImageWithMetaData: filename_prefix {{prefix!r}} names a folder while subdirectory_name is set. "
    "The original then wrote into <subdirectory>/<prefix folder>/ only if that folder already existed (it "
    "created only the subdirectory); the managed image writer would create it. Put the folder in "
    "subdirectory_name instead."
)
