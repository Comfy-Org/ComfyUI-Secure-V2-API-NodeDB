"""Directories for the converted Inspire directory loaders, through the SDK (Secure Nodes V2).

The original lists any host directory with os.listdir / os.path and opens files with PIL
(pristine inspire/image_util.py:62-248). A guest has no host filesystem. Here a directory is a
folder inside one of ComfyUI's managed folders:
- a leading "input/", "output/" or "temp/" selects that folder, as the original's paths relative
  to the ComfyUI folder do;
- any other relative path is a sub-folder of the input folder;
- absolute paths and ".." are refused by name.
It is listed with ctx.assets.list (files only, in name order) and read with ctx.assets.resolve +
read_bytes. The pack's own lines decode the bytes. No host path is seen or returned.
"""

import re

from comfy_api.latest import sdk

MANAGED = ("input", "output", "temp")
_DRIVE = re.compile(r"^[A-Za-z]:")


class DirectoryRefused(ValueError):
    """A directory this Secure Nodes V2 conversion cannot reach."""


def refusal_absolute(node, directory):
    return (f"{node}: Secure Nodes V2 loads images only from ComfyUI's input, output or temp folder; "
            f"'{directory}' is an absolute path. Put the images in a sub-folder of the input folder and "
            "enter that sub-folder (for example 'my_frames' or 'input/my_frames').")


def refusal_parent(node, directory):
    return (f"{node}: Secure Nodes V2 does not follow '..' out of ComfyUI's input, output or temp folder "
            f"('{directory}'). Enter a sub-folder of the input folder instead.")


def refusal_datetime(node, method):
    return (f"{node}: sort_method '{method}' is not available in Secure Nodes V2 yet: it sorts by file "
            "modification time, which the SDK does not expose. Use 'Alphabetical (ASC)', "
            "'Numerical (ASC)' or 'None' (name order).")


def locate(node, directory):
    """(managed folder, logical prefix) for the directory a workflow names."""
    text = directory.replace("\\", "/")
    if text.startswith("/") or _DRIVE.match(text):
        raise DirectoryRefused(refusal_absolute(node, directory))
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise DirectoryRefused(refusal_parent(node, directory))
    if parts and parts[0] in MANAGED:
        return parts[0], "/".join(parts[1:])
    return "input", "/".join(parts)


def _host_error_is(error, kind):
    """A host-side SDK error is the builtin type in-process. In a real guest it arrives as the transport's error,
    with the host's type name in remote_type (round 3)."""
    return isinstance(error, kind) or getattr(error, "remote_type", None) == kind.__name__


class Directory:
    """One listed directory: `names` are its files, in name order."""

    def __init__(self, folder, prefix, names):
        self.folder, self.prefix, self.names = folder, prefix, names

    async def read(self, name):
        logical = f"{self.prefix}/{name}" if self.prefix else name
        ctx = sdk.ctx()
        return await ctx.assets.read_bytes(await ctx.assets.resolve(self.folder, logical))


async def open_directory(node, directory, not_found_message):
    """List a directory. Raises the original's FileNotFoundError when it does not exist; an empty
    directory looks the same as a missing one, because the SDK lists files, not folders."""
    if directory == "":
        raise FileNotFoundError(not_found_message)
    folder, prefix = locate(node, directory)
    ctx = sdk.ctx()
    try:
        names = await ctx.assets.list(folder, prefix=prefix, recursive=False)
    except Exception as error:
        if not _host_error_is(error, NotADirectoryError):
            raise
        raise FileNotFoundError(not_found_message) from None
    base = f"{prefix}/" if prefix else ""
    files = [name[len(base):] for name in names]
    if not files:
        try:
            below = await ctx.assets.list(folder, prefix=prefix, recursive=True)
        except Exception as error:
            if not _host_error_is(error, ValueError):
                raise
            below = ["(more files than the SDK lists)"]
        if not below:
            raise FileNotFoundError(not_found_message)
    return Directory(folder, prefix, files)
