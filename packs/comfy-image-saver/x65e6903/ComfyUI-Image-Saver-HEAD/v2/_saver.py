"""Source filename/metadata algorithms; all host effects use bounded SDK ops."""
import json
import posixpath
import re
from datetime import datetime
from comfy_api.latest import sdk


def parse_name(ckpt_name):
    path = ckpt_name
    filename = path.split("/")[-1]
    filename = filename.split(".")[:-1]
    filename = ".".join(filename)
    return filename


def handle_whitespace(string: str):
    return string.strip().replace("\n", " ").replace("\r", " ").replace("\t", " ")


def get_timestamp(time_format):
    now = datetime.now()
    try:
        timestamp = now.strftime(time_format)
    except:
        timestamp = now.strftime("%Y-%m-%d-%H%M%S")

    return timestamp


def make_pathname(filename, seed, modelname, counter, time_format):
    filename = filename.replace("%date", get_timestamp("%Y-%m-%d"))
    filename = filename.replace("%time", get_timestamp(time_format))
    filename = filename.replace("%model", modelname)
    filename = filename.replace("%seed", str(seed))
    filename = filename.replace("%counter", str(counter))
    return filename


def make_filename(filename, seed, modelname, counter, time_format):
    filename = make_pathname(filename, seed, modelname, counter, time_format)

    return get_timestamp(time_format) if filename == "" else filename



def logical_name(value):
    # Output names are managed relative names, never filesystem authority. Same rules as the SDK
    # writer (_logical_output_target): NUL, absolute paths, drive prefixes and ".." leave the output
    # folder. A mid-name ":" is fine, as in the original. "\\" is refused because the writer treats it
    # as a path separator where the original writes it literally.
    if "\x00" in value or value.startswith("/") or re.match(r"^[A-Za-z]:($|/)", value):
        raise ValueError(f"{_NODE}: output names must stay inside the output folder: {value!r}")
    if "\\" in value:
        raise ValueError(f"{_NODE}: a backslash in an output name is not supported (the V2 image "
                         f"writer treats it as a path separator): {value!r}")
    if ".." in value.split("/"):
        raise ValueError(f"{_NODE}: output name escapes the output folder: {value!r}")
    return posixpath.normpath(value) if value else ""


_NODE = "comfy-image-saver/Save Image w/Metadata"
JPEG_REFUSAL = (
    _NODE + ": JPEG output is not available in Secure Nodes V2. The original saves JPEG with "
    "Pillow's default chroma subsampling; the V2 image writer always uses 4:4:4 and declares "
    "no subsampling option, so the file would differ. Use png or webp.")
DUPLICATE_TEXT_REFUSAL = (
    _NODE + ": PNG text key {key!r} occurs more than once (parameters, prompt and extra_pnginfo "
    "keys); the original writes duplicate text chunks, which the V2 image writer cannot store.")


async def save_files(images, seed_value, steps, cfg, sampler_name, scheduler,
                     positive, negative, modelname, quality_jpeg_or_webp,
                     lossless_webp, width, height, counter, filename, path,
                     extension, time_format):
    if extension == "jpeg":
        raise ValueError(JPEG_REFUSAL)
    filename = make_filename(filename, seed_value, modelname, counter, time_format)
    path = make_pathname(path, seed_value, modelname, counter, time_format)
    context = sdk.ctx()
    asset = await context.assets.resolve("checkpoints", modelname)
    basemodelname = parse_name(modelname)
    modelhash = (await context.assets.digest(asset, algorithm="sha256"))[:10]
    comment = f"{handle_whitespace(positive)}\nNegative prompt: {handle_whitespace(negative)}\nSteps: {steps}, Sampler: {sampler_name}{f'_{scheduler}' if scheduler != 'normal' else ''}, CFG Scale: {cfg}, Seed: {seed_value}, Size: {width}x{height}, Model hash: {modelhash}, Model: {basemodelname}, Version: ComfyUI"
    batch_size = int(await images.batch_size())
    filenames = []
    for img_count in range(1, batch_size + 1):
        # Preserve the upstream cumulative mutation, including _01_02_03.
        if batch_size > 1:
            filename += "_{:02d}".format(img_count)
        filenames.append(logical_name(posixpath.join(path, f"{filename}.{extension}")))
    options = {}
    if extension == "png":
        # Same chunks, same order as the original's PngInfo.add_text calls
        # (nodes.py:242-249). The declared png_text is an ordered dict, so a
        # repeated key is refused rather than silently merged.
        metadata = await context.graph.execution_metadata()
        pairs = [("parameters", comment)]
        prompt = metadata["prompt"]
        extra_pnginfo = metadata["extra_pnginfo"]
        if prompt is not None:
            pairs.append(("prompt", json.dumps(prompt)))
        if extra_pnginfo is not None:
            for key in extra_pnginfo:
                pairs.append((key, json.dumps(extra_pnginfo[key])))
        png_text = {}
        for key, value in pairs:
            if key in png_text:
                raise ValueError(DUPLICATE_TEXT_REFUSAL.format(key=key))
            png_text[key] = value
        options["png_text"] = png_text
    else:
        options["a1111_parameters"] = comment
    try:
        return await context.output.save_images(
            images, filenames=filenames, save_metadata=False,
            image_format=extension, quality=quality_jpeg_or_webp,
            lossless=lossless_webp, optimize=True, **options)
    except Exception as error:
        # The writer never overwrites ("an exact output image already exists"); the original does.
        # In a guest the host error arrives as a transport error, so match its text, not its type.
        if "an exact output image already exists" in str(error):
            raise FileExistsError(
                f"{_NODE}: {', '.join(filenames)} already exists. The original overwrites it, but the "
                "V2 image writer never overwrites files; use %time or %counter in the filename.") from error
        raise
