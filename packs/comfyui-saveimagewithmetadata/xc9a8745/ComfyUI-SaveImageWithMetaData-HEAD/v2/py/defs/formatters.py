import os

# Secure Nodes V2: catalogue entries instead of host paths (was `import folder_paths`).
from ..utils.hash import asset_target, calc_hash
from ..utils.embedding import get_embedding_file_path

# Secure Nodes V2: comfy.sd1_clip's prompt parsing, vendored (the guest cannot import
# comfy); the tokenizer classes are not imported because a guest sees a CLIP input only as
# an opaque reference (see _v2_clip.py).
from .._v2_clip import escape_important, token_weights, unescape_important, embedding_clip

cache_model_hash = {}


def calc_model_hash(model_name, input_data):
    filename = asset_target("checkpoints", model_name)
    return calc_hash(filename)


def calc_vae_hash(model_name, input_data):
    filename = asset_target("vae", model_name)
    return calc_hash(filename)


def calc_lora_hash(model_name, input_data):
    filename = asset_target("loras", model_name)
    return calc_hash(filename)


def calc_unet_hash(model_name, input_data):
    filename = asset_target("unet", model_name)
    return calc_hash(filename)


def convert_skip_clip(stop_at_clip_layer, input_data):
    return stop_at_clip_layer * -1


def get_scaled_width(scaled_by, input_data):
    samples = input_data[0]["samples"][0]["samples"]
    return round(samples.shape[3] * scaled_by * 8)


def get_scaled_height(scaled_by, input_data):
    samples = input_data[0]["samples"][0]["samples"]
    return round(samples.shape[2] * scaled_by * 8)


def extract_embedding_names(text, input_data):
    embedding_names, _ = _extract_embedding_names(text, input_data)

    return [os.path.basename(embedding_name) for embedding_name in embedding_names]


def extract_embedding_hashes(text, input_data):
    embedding_names, clip = _extract_embedding_names(text, input_data)
    embedding_hashes = []
    for embedding_name in embedding_names:
        embedding_file_path = get_embedding_file_path(embedding_name, clip)
        embedding_hashes.append(calc_hash(embedding_file_path))

    return embedding_hashes


def _extract_embedding_names(text, input_data):
    embedding_identifier = "embedding:"
    clip_ = input_data[0]["clip"][0]
    clip = None
    if clip_ is not None:
        # Secure Nodes V2: was an isinstance() check of clip_.tokenizer against the SD1, SD2,
        # SDXL, SD3 and Flux tokenizers, taking their clip_l / clip_h (see _v2_clip.py).
        clip = embedding_clip(clip_)
        if clip is not None and hasattr(clip, "embedding_identifier"):
            embedding_identifier = clip.embedding_identifier
    if not isinstance(text, str):
        text = "".join(str(item) if item is not None else "" for item in text)
    text = escape_important(text)
    parsed_weights = token_weights(text, 1.0)

    # tokenize words
    embedding_names = []
    for weighted_segment, weight in parsed_weights:
        to_tokenize = unescape_important(weighted_segment).replace("\n", " ").split(" ")
        to_tokenize = [x for x in to_tokenize if x != ""]
        for word in to_tokenize:
            # find an embedding, deal with the embedding
            if (
                word.startswith(embedding_identifier)
                and clip.embedding_directory is not None
            ):
                embedding_name = word[len(embedding_identifier) :].strip("\n")
                embedding_names.append(embedding_name)

    return embedding_names, clip
