"""Source filename/metadata algorithms; all host effects use bounded SDK ops."""
import json
import posixpath
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
    # Output names are managed relative names, never filesystem authority.
    if "\\" in value or "\x00" in value or ":" in value or value.startswith("/"):
        raise ValueError("output names must be relative logical names")
    if ".." in value.split("/"):
        raise ValueError("output name escapes the output namespace")
    return posixpath.normpath(value) if value else ""


async def save_files(images, seed_value, steps, cfg, sampler_name, scheduler,
                     positive, negative, modelname, quality_jpeg_or_webp,
                     lossless_webp, width, height, counter, filename, path,
                     extension, time_format):
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
    if extension == "jpeg":
        options["jpeg_subsampling"] = -1
    if extension == "png":
        metadata = await context.graph.execution_metadata()
        png_text = [("parameters", comment)]
        prompt = metadata["prompt"]
        extra_pnginfo = metadata["extra_pnginfo"]
        if prompt is not None:
            png_text.append(("prompt", json.dumps(prompt)))
        if extra_pnginfo is not None:
            for key in extra_pnginfo:
                png_text.append((key, json.dumps(extra_pnginfo[key])))
        options["png_text"] = png_text
    else:
        options["a1111_parameters"] = comment
    return await context.output.save_images(
        images, filenames=filenames, save_metadata=False,
        image_format=extension, quality=quality_jpeg_or_webp,
        lossless=lossless_webp, optimize=True, overwrite=True, **options)
