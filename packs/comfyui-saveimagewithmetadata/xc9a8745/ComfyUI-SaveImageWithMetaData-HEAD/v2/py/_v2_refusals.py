"""Behaviours of the original that Secure Nodes V2 cannot reproduce exactly; each is refused
by name instead of being changed silently (SECURE_CONVERSION.md, "Known differences")."""

PACK = "ComfyUI-SaveImageWithMetaData"


class SecureConversionRefusal(RuntimeError):
    """A behaviour of the original that the Secure Nodes V2 conversion refuses by name."""


JPEG = (
    f"{PACK}/SaveImageWithMetaData: file_format 'jpeg' is not supported on Secure Nodes V2. "
    "The original encodes JPEG with Pillow's default 4:2:0 chroma subsampling and inserts a piexif "
    "EXIF block; the managed image writer encodes JPEG with 4:4:4 subsampling and its own EXIF layout, "
    "so the image would differ. Use png or webp."
)

OVERWRITE = (
    f"{PACK}/SaveImageWithMetaData: add_counter_to_filename=False would overwrite {{name!r}}. "
    "The original replaces an existing file of that name; the managed image writer never "
    "overwrites an output file. Turn add_counter_to_filename on, or use a filename_prefix "
    "that does not exist yet."
)

OVERWRITE_BATCH = (
    f"{PACK}/SaveImageWithMetaData: add_counter_to_filename=False with a batch of {{count}} images "
    "writes every image to {name!r}. The original overwrites that file once per image; the "
    "managed image writer never overwrites an output file. Turn add_counter_to_filename on."
)

BATCH_NUM = (
    f"{PACK}/SaveImageWithMetaData: filename_prefix contains '%batch_num%'. The original writes it "
    "literally into the file name; the managed image writer replaces it with the batch number, so "
    "the file name would differ. Remove '%batch_num%' from the prefix."
)

DOT_NAME = (
    f"{PACK}/SaveImageWithMetaData: filename_prefix {{prefix!r}} names no file (the original writes "
    "'._00001_.<ext>'); the managed image writer rejects '.' as a file name. Use a non-empty prefix."
)

EMBEDDINGS_CATALOGUE = (
    f"{PACK}/SaveImageWithMetaData: embedding {{name!r}} is not at the top of the embeddings folder, "
    "and the embeddings catalogue lists more than 4096 files, so its subfolders cannot be searched "
    "the way the original searched them. Reference the embedding with its subfolder "
    "(embedding:subfolder/name)."
)
