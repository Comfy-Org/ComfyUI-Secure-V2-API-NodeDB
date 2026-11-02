import posixpath

from comfy_api.latest import sdk

from .hash import AssetTarget
from .._v2_capture import run_async
from .._v2_refusals import EMBEDDINGS_CATALOGUE, SecureConversionRefusal


def _catalogue_subdirectories(embedding_name):
    """comfy.sd1_clip.expand_directory_list for the embeddings folder, below its root: every
    subdirectory holding catalogued files, as logical paths, by depth and then name."""
    try:
        names = run_async(sdk.ctx().assets.list("embeddings", recursive=True))
    except ValueError as error:  # the catalogue lists at most 4096 names at once
        raise SecureConversionRefusal(EMBEDDINGS_CATALOGUE.format(name=embedding_name)) from error
    directories = set()
    for name in names:
        parent = posixpath.dirname(name)
        while parent:
            directories.add(parent)
            parent = posixpath.dirname(parent)
    return sorted(directories, key=lambda d: (d.count("/"), d))


def _search(embed_dir, embedding_name, extensions):
    # Construct the logical path for the embedding name
    embed_path = posixpath.normpath(posixpath.join(embed_dir, embedding_name))

    # Ensure embed_path is within embed_dir (security check)
    if posixpath.isabs(embed_path) or embed_path == ".." or embed_path.startswith("../"):
        return None
    if embed_dir and not embed_path.startswith(embed_dir + "/"):
        return None
    if embed_path == ".":
        # the folder itself; the original then probed '<folder>.safetensors' etc. beside it,
        # which is outside the catalogue
        return None

    # Check if the file exists with or without extensions
    if run_async(sdk.ctx().assets.exists("embeddings", embed_path)):
        return AssetTarget("embeddings", embed_path)
    for ext in extensions:
        candidate_path = embed_path + ext
        if run_async(sdk.ctx().assets.exists("embeddings", candidate_path)):
            return AssetTarget("embeddings", candidate_path)
    return None


def get_embedding_file_path(embedding_name, clip):
    """
    Resolves the file path for an embedding by searching directories and checking file extensions.

    Args:
        embedding_name (str): The name of the embedding file (without an extension).
        clip (object): An object containing the attribute `embedding_directory`,
                       which specifies directories to search.

    Returns:
        AssetTarget or None: The embeddings catalogue entry if found, otherwise None.
        (Secure Nodes V2: the original returned a host path.)
    """
    # Validate embedding_directory
    embedding_directory = getattr(clip, "embedding_directory", None)
    if not embedding_directory:
        raise ValueError("The 'embedding_directory' attribute in the clip object is None or empty.")

    extensions = [".safetensors", ".pt", ".bin"]

    # Secure Nodes V2: the directories searched are the embeddings catalogue's (the loaders pass
    # the embeddings folders as embedding_directory): its root first, then each subfolder.
    valid_file = _search("", embedding_name, extensions)
    if valid_file is None:
        for embed_dir in _catalogue_subdirectories(embedding_name):
            valid_file = _search(embed_dir, embedding_name, extensions)
            # Stop searching if a valid file is found
            if valid_file:
                break

    return valid_file
