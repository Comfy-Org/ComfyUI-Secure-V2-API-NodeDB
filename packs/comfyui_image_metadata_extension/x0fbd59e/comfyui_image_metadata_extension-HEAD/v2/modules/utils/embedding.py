from comfy_api.latest import sdk

from .._v2_capture import run_async
from ..utils.log import print_warning
from .hash import asset_target

# Secure Nodes V2: the original listed folder_paths.get_folder_paths("embeddings")
# at import and joined host paths. The catalogue is asked instead, in the same
# extension order.


def get_embedding_file_path(name):
    """
    Resolve the file path for the given embedding name.

    Args:
        name (str): The name of the embedding (without extension).

    Returns:
        AssetTarget | None: The resolved catalogue entry, or None if not found.
    """
    try:
        extensions = ["", ".safetensors", ".pt", ".bin"]

        for ext in extensions:
            if run_async(sdk.ctx().assets.exists("embeddings", name + ext)):
                return asset_target("embeddings", name + ext)

        raise FileNotFoundError(f"no embeddings asset named {name!r}")

    except Exception as e:
        print_warning(f"embedding not found '{name}': {e}")

    return None
