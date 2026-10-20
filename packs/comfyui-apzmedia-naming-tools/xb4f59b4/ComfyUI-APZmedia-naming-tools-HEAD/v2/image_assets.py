"""Public managed-asset transport helpers; source only, no host path access."""
import os

from comfy_api.latest import sdk

from .image_decode import MAX_ENCODED_BYTES, decode_image_bytes


def selected_asset(image):
    # Original annotated_filepath strips a single leading-space + suffix.
    # Keep spelling, spacing and basename behavior; the resolver confines
    # logical names to the selected managed directory.
    for ending, count, folder in [("[output]", 9, "output"),
                                  ("[input]", 8, "input"),
                                  ("[temp]", 7, "temp")]:
        if image.endswith(ending):
            return folder, image[:-count]
    return "input", image


async def read_encoded_image(image):
    assets = sdk.ctx().assets
    folder, name = selected_asset(image)
    ref = await assets.resolve(folder, name)
    size = await assets.size(ref)
    if type(size) is not int or not 0 <= size <= MAX_ENCODED_BYTES:
        raise ValueError("APZ encoded image exceeds 64 MiB")
    chunks = []
    offset = 0
    while offset < size:
        count = min(1024**2, size - offset)
        data = await assets.read_range(ref, offset=offset, length=count)
        if type(data) is not bytes or len(data) != count:
            raise ValueError("APZ image changed or returned an invalid byte range")
        chunks.append(data)
        offset += count
    return b"".join(chunks), name


async def load_selected_image(image):
    """Actual decode/publication body; picker schema remains a named gap."""
    encoded, name = await read_encoded_image(image)
    pixels, mask = decode_image_bytes(encoded)
    filename = os.path.basename(name)
    return (await sdk.ImageRef.from_tensor(pixels),
            await sdk.MaskRef.from_value(mask), filename,
            os.path.splitext(filename)[0])


async def image_fingerprint(image):
    assets = sdk.ctx().assets
    folder, name = selected_asset(image)
    return await assets.digest(await assets.resolve(folder, name), algorithm="sha256")


async def validate_selected_image(image):
    folder, name = selected_asset(image)
    if not await sdk.ctx().assets.exists(folder, name):
        return "Invalid image file: {}".format(image)
    return True
