"""Pinned, hash-verified Florence-2 weight declarations.

Upstream reaches the Hugging Face hub with ``snapshot_download(repo_id=...)``:
an unpinned fetch of an entire repository, whatever it happens to contain
today, including ``pytorch_model.bin`` pickles.  Nothing about that request is
reviewable before it runs.

Every weight this pack can ever fetch is instead named here, at a fixed
repository revision, as a single SafeTensors file with its SHA-256 recorded.
The host refuses any request that is not byte-for-byte one of these
declarations (see ``SDK_REQUIRED_WEIGHTS``), verifies the digest after
download, and serves later requests from its cache.  Adding a model means
editing this table, which is a reviewable diff.

The tokenizer is NOT downloaded.  It ships inside the pack -- see
``model/tokenizer.py`` -- because its byte identity is then covered by the
pack manifest rather than by a live hub lookup.
"""
from __future__ import annotations

from comfy_api.latest import sdk

# Florence-2 is a caption/detection language model, so its SafeTensors weights
# live in the text-encoder catalogue; the adapter lives in the LoRA catalogue.
# Both are existing, registered catalogues -- this pack invents no folder.
_WEIGHT_FOLDER = "text_encoders"
_LORA_FOLDER = "loras"

# Selectable models, in upstream's order.  ``MODEL_LIST`` is what the combo
# shows; ``MODEL_WEIGHTS`` is what may actually be fetched.  They are the same
# set by construction, asserted below.
MODEL_WEIGHTS: dict[str, sdk.HuggingFaceWeight] = {
    "microsoft/Florence-2-base": sdk.HuggingFaceWeight(
        repo_id="microsoft/Florence-2-base",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac",
        sha256="03075d2d2d2bbd3e180b9ba0afae4aa8563226e2d32911656966e05b2f2ee060",
        on_demand=True,
    ),
    "microsoft/Florence-2-base-ft": sdk.HuggingFaceWeight(
        repo_id="microsoft/Florence-2-base-ft",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="f6c1a25888ffc1d945ee8a1a77ac833c7303d46e",
        sha256="58757d657ff44051314c8030b68e04cb1bb618ca9a4885418f111f6fb708185a",
        on_demand=True,
    ),
    "microsoft/Florence-2-large": sdk.HuggingFaceWeight(
        repo_id="microsoft/Florence-2-large",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="21a599d414c4d928c9032694c424fb94458e3594",
        sha256="4f38ce741c6b71188fe2b3419a55e11917a8a7b321ae2e63c61da0191b0ebad7",
        on_demand=True,
    ),
    "microsoft/Florence-2-large-ft": sdk.HuggingFaceWeight(
        repo_id="microsoft/Florence-2-large-ft",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="4a12a2b54b7016a48a22037fbd62da90cd566f2a",
        sha256="8b4e610c952eef90a836c56cda0f398a672a3a6ca7b4d96b0e09a86dee42e2c3",
        on_demand=True,
    ),
    "HuggingFaceM4/Florence-2-DocVQA": sdk.HuggingFaceWeight(
        repo_id="HuggingFaceM4/Florence-2-DocVQA",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="2f8e312df1b0689740beba3c2f3dbfc61067ad7e",
        sha256="1d9a3bc6abcace5e9820630945fe26cfa961fe2577f8adeb48256acba876123e",
        on_demand=True,
    ),
    "thwri/CogFlorence-2.1-Large": sdk.HuggingFaceWeight(
        repo_id="thwri/CogFlorence-2.1-Large",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="cd834343b8e903f05aca17cd0e313b74014ccc11",
        sha256="ea92a49e6806c96c1af4f55906e439065a573030dc0090f9c25580f0ed698d40",
        on_demand=True,
    ),
    "thwri/CogFlorence-2.2-Large": sdk.HuggingFaceWeight(
        repo_id="thwri/CogFlorence-2.2-Large",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="19f2c614fdfd18ba49c81d567d70d3a68313e0bb",
        sha256="77384f40b2c67f798ca2f6ac4a8a46e969313115aff7a12842275e0017a08805",
        on_demand=True,
    ),
    "gokaygokay/Florence-2-SD3-Captioner": sdk.HuggingFaceWeight(
        repo_id="gokaygokay/Florence-2-SD3-Captioner",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="519d1e567b00ff9117a1aab0d432c3dd9fa865d2",
        sha256="f8cfbc57ba468159501fe12c67ddfd94f1ad6983f6ce1e82cb5995c8149b79d1",
        on_demand=True,
    ),
    "gokaygokay/Florence-2-Flux-Large": sdk.HuggingFaceWeight(
        repo_id="gokaygokay/Florence-2-Flux-Large",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="a828167bee1befbf73c9d384f7da04743d830232",
        sha256="82d0f8da156f27d64c31abef8281b1c4cb646ec4edfab2debe5f64a78d208946",
        on_demand=True,
    ),
    "MiaoshouAI/Florence-2-base-PromptGen-v1.5": sdk.HuggingFaceWeight(
        repo_id="MiaoshouAI/Florence-2-base-PromptGen-v1.5",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="caf550c43498b7e98c9b5919bf204309a56cfc47",
        sha256="7727411b7449737a010e7f5fcb7c28a5d2d4d93fa89370b92dfb05ee225259ff",
        on_demand=True,
    ),
    "MiaoshouAI/Florence-2-large-PromptGen-v1.5": sdk.HuggingFaceWeight(
        repo_id="MiaoshouAI/Florence-2-large-PromptGen-v1.5",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="e4fb0497102b985f4af0d27d68b4106ff6e73a59",
        sha256="2e247747e5182cedea2b8ba87fde47a4b4b548febd57cf9ac9ff9dba6da8a9c5",
        on_demand=True,
    ),
    "MiaoshouAI/Florence-2-base-PromptGen-v2.0": sdk.HuggingFaceWeight(
        repo_id="MiaoshouAI/Florence-2-base-PromptGen-v2.0",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="59b6e4bf75d0f3e8a6b1a14211f6a50fcdd48d63",
        sha256="3858ba6adc5b02458015dc61d0f7a30a4fb351d2f23e4414a24d3a86c42b1100",
        on_demand=True,
    ),
    "MiaoshouAI/Florence-2-large-PromptGen-v2.0": sdk.HuggingFaceWeight(
        repo_id="MiaoshouAI/Florence-2-large-PromptGen-v2.0",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="4aa33eaf50aab040fe8523312ff52eb53322c220",
        sha256="95b6441fb8e3a96b1f6ec0ac894a7632ea49fc77c0dd623a7a53d1d879390321",
        on_demand=True,
    ),
    "PJMixers-Images/Florence-2-base-Castollux-v0.5": sdk.HuggingFaceWeight(
        repo_id="PJMixers-Images/Florence-2-base-Castollux-v0.5",
        filename="model.safetensors",
        folder=_WEIGHT_FOLDER,
        revision="e3a0168ed8e406f9605e9792119c11b3fd005df3",
        sha256="fbba334010f87ff1ee68aa54970414bac7e002acf359c49e3d57469446dfe23e",
        on_demand=True,
    ),
}

MODEL_LIST = list(MODEL_WEIGHTS)

# Castollux ships one added token beyond the standard Florence-2 set.  Naming
# it here keeps the shared vendored vocabulary byte-exact for every model while
# still reproducing that repository's tokenizer id-for-id.
EXTRA_SPECIAL_TOKENS: dict[str, tuple[str, ...]] = {
    "PJMixers-Images/Florence-2-base-Castollux-v0.5": ("<image>",),
}

LORA_WEIGHTS: dict[str, sdk.HuggingFaceWeight] = {
    "NikshepShetty/Florence-2-pixelprose": sdk.HuggingFaceWeight(
        repo_id="NikshepShetty/Florence-2-pixelprose",
        filename="adapter_model.safetensors",
        folder=_LORA_FOLDER,
        revision="0515d29406e399e3234f7b9b5229f701800a7676",
        sha256="355fc192daffa7f7069a7891ba883683f5ffd101eaf68d0b310977b6754c2037",
        on_demand=True,
    ),
}

LORA_LIST = list(LORA_WEIGHTS)

# ``adapter_config.json`` cannot be fetched -- the host allows tensor archives
# only -- so the two values upstream reads out of it are pinned here, taken
# from the same pinned revision as the adapter itself.  ``lora_alpha`` is the
# scale numerator; the rank comes from the adapter's own tensor shapes, which
# is what upstream's comfy lora path does too.  (The adapter also sets
# ``use_rslora``; upstream ignores it, so this conversion ignores it as well --
# reproducing upstream, not peft.)
LORA_ALPHA: dict[str, int] = {
    "NikshepShetty/Florence-2-pixelprose": 32,
}

ALL_WEIGHTS: tuple[sdk.HuggingFaceWeight, ...] = (
    *MODEL_WEIGHTS.values(),
    *LORA_WEIGHTS.values(),
)

assert all(weight.on_demand for weight in ALL_WEIGHTS)
assert all(weight.sha256 for weight in ALL_WEIGHTS)


def model_weight(model: str) -> sdk.HuggingFaceWeight:
    """The declaration for ``model``, or a refusal naming the closed set."""
    try:
        return MODEL_WEIGHTS[model]
    except KeyError:
        raise ValueError(
            f"Model {model} is not in the supported model list.") from None


def lora_weight(model: str) -> sdk.HuggingFaceWeight:
    try:
        return LORA_WEIGHTS[model]
    except KeyError:
        raise ValueError(
            f"Lora Model {model} is not in the supported lora model list."
        ) from None


__all__ = [
    "ALL_WEIGHTS", "EXTRA_SPECIAL_TOKENS", "LORA_ALPHA", "LORA_LIST",
    "LORA_WEIGHTS", "MODEL_LIST", "MODEL_WEIGHTS", "lora_weight",
    "model_weight",
]
