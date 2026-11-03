"""Named refusals of the WAS Node Suite conversion (SECURE_CONVERSION.md, "Known differences")."""

PACK = "was-ns"


class SecureConversionRefusal(RuntimeError):
    """A behaviour of the original that the Secure Nodes V2 conversion refuses by name."""


def not_converted(node_id):
    return f"{PACK}/{node_id} is not yet converted to Secure Nodes V2"


HOST_TOKEN = (
    f"{PACK}: the text uses the token {{token}}, which the original filled with information about the host "
    "machine (host name, user name or CUDA device). A Secure Nodes V2 node cannot read it. Remove the token."
)

IMAGE_SAVE_JPEG = (
    f"{PACK}/Image Save: extension {{ext!r}} is not supported on Secure Nodes V2. The original encodes JPEG with "
    "Pillow's default chroma subsampling and a DPI header; the managed image writer encodes JPEG with 4:4:4 "
    "subsampling, so the image would differ. Use png, webp, gif, tiff or bmp."
)

IMAGE_SAVE_WEBP_EMBED = (
    f"{PACK}/Image Save: extension 'webp' with embed_workflow 'true' cannot be written exactly for this prompt "
    "({why}). The original writes 'Prompt:' and 'Workflow:' text into EXIF tags 0x010F and 0x010E; the managed image "
    "writer writes the same tags only for a prompt with exactly one workflow entry, as JSON without NaN or Infinity, "
    "below 960 KiB in all. Set embed_workflow to 'false', or use png."
)

IMAGE_SAVE_HISTORY = (
    f"{PACK}/Image Save: show_history 'true' is not supported on Secure Nodes V2. The original lists earlier images "
    "from a history database it keeps in its pack folder; a V2 node has no such database. Set show_history to 'false'."
)

IMAGE_SAVE_PATH = (
    f"{PACK}/Image Save: output_path {{path!r}} is not a folder inside the output folder. The original also wrote to "
    "absolute paths anywhere on the host (and, on a Linux host, kept backslashes as name characters); Secure Nodes V2 "
    "writes only inside the output folder. Use a relative output_path with '/' separators."
)

IMAGE_SAVE_PREFIX = (
    f"{PACK}/Image Save: filename_prefix {{prefix!r}} contains a path separator. The original joined it to the "
    "folder as is; the managed image writer would create folders from it. Put folders in output_path."
)

IMAGE_SAVE_OVERWRITE = (
    f"{PACK}/Image Save: the image would replace the existing file {{name!r}}. The original overwrote it; the "
    "managed image writer never overwrites an output file. Change filename_prefix or overwrite_mode."
)

IMAGE_SAVE_LISTING = (
    f"{PACK}/Image Save: the host could not list output folder {{path!r}} ({{reason}}), so the next file number "
    "cannot be computed the way the original computed it. A Secure Nodes V2 node lists at most 4096 names at once."
)

NEEDS_SCIPY = (
    f"{PACK}/{{node}} is not available on Secure Nodes V2 yet: the original computes it with {{use}} from scipy, "
    "which the guest runtime for this pack does not provide yet."
)

NEEDS_PILGRAM = (
    f"{PACK}/{{node}} is not available on Secure Nodes V2 yet: the original computes it with the pilgram package "
    "({use}), which the guest runtime for this pack does not provide yet."
)

NO_NETWORK = (
    f"{PACK}/{{node}} is not available on Secure Nodes V2: the original fetches its prompts from an online search "
    "service when it runs, and a Secure Nodes V2 node has no network access."
)

LOAD_BATCH_PATH = (
    f"{PACK}/Load Image Batch: path {{path!r}} is outside ComfyUI's input folder. The original read any folder on the "
    "host; a Secure Nodes V2 node reads only the input folder. Put the images in a folder under input/ and enter its "
    "path as 'input/<folder>'."
)

LOAD_BATCH_PATTERN = (
    f"{PACK}/Load Image Batch: pattern {{pattern!r}} reaches outside the folder in path (it is absolute or has a '..' "
    "part). A Secure Nodes V2 node reads only ComfyUI's input folder: put the images in a folder under input/, enter "
    "that folder as path, and use a pattern inside it."
)

LOAD_BATCH_LISTING = (
    f"{PACK}/Load Image Batch: the host could not list {{path!r}} ({{reason}}). A Secure Nodes V2 node lists at most "
    "4096 files at once, and only files that stay inside ComfyUI's input folder (links out of it are not followed). "
    "Split a larger batch into folders under input/ of at most 4096 files each."
)

NEEDS_OPENCV = (
    f"{PACK}/{{node}} is not available on Secure Nodes V2: the original computes it with OpenCV ({{use}}), which the "
    "guest runtime for this pack does not provide."
)

CLIPSEG_WEIGHTS = (
    f"{PACK}/CLIPSeg Masking is not available on Secure Nodes V2 yet: the original downloads the CLIPSeg model with "
    "transformers when it runs, and a Secure Nodes V2 node has no network access. It needs a pinned copy of the "
    "weights provided by the host."
)

NSP_SOURCES = (
    f"{PACK}/CLIPTextEncode (NSP) is not available on Secure Nodes V2: in Noodle Soup Prompts mode the original "
    "downloads its prompt pantry from the network the first time it runs, and in Wildcards mode it reads wildcard "
    "files from a folder on the host."
)

TEXT_FILE_PATH = (
    f"{PACK}/{{node}}: file_path {{path!r}} is outside ComfyUI's input, output and temp folders. The original read any "
    "file on the host; a Secure Nodes V2 node reads only those folders. Put the file under input/ and enter its path "
    "as 'input/<file>'."
)

TEXT_FILE_LISTING = (
    f"{PACK}/{{node}}: the host could not check {{path!r}} ({{reason}})."
)

SAVE_TEXT_PATH = (
    f"{PACK}/Save Text File: path {{path!r}} is not a folder inside ComfyUI's output or temp folder. The original "
    "resolved it against ComfyUI's working directory and wrote only inside the input, output or temp folder; a "
    "Secure Nodes V2 node writes only inside the output or temp folder. Use 'output' or 'output/<folder>' (the "
    "default './ComfyUI/output/...' names the output folder only when ComfyUI runs from its parent folder)."
)

SAVE_TEXT_NAME = (
    f"{PACK}/Save Text File: the file name {{name!r}} cannot be written on Secure Nodes V2 ({{why}})."
)

SAVE_TEXT_ENCODING = (
    f"{PACK}/Save Text File: encoding {{encoding!r}} is not supported on Secure Nodes V2: the managed text writer "
    "writes UTF-8 only. Use utf-8."
)

SAVE_TEXT_LISTING = (
    f"{PACK}/Save Text File: the host could not list folder {{path!r}} ({{reason}}), so the next file number cannot "
    "be computed the way the original computed it. A Secure Nodes V2 node lists at most 4096 names at once."
)
