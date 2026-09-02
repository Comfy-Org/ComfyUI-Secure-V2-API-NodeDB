"""The narrow slice of CLIP that smZNodes' A1111 engines actually need.

Upstream reaches its goal by REPLACING two bound methods on the live CLIP
object for the duration of one encode:

    clip.tokenizer.<component>.tokenize_with_weights   -> engine.tokenize_with_weights
    clip.cond_stage_model.<component>.encode_token_weights -> engine.encode_token_weights

and, inside `ClassicTextProcessingEngine.__init__`, additionally wraps
`text_encoder.transformer.text_model.embeddings.token_embedding` so textual
inversion vectors can be spliced into the input embedding layer mid-forward.

None of that is recreatable from a guest, and none of it is the point. What
the engine needs from the host is exactly two questions:

    1. "what token ids does this text fragment produce?"   -> clip.tokenize
    2. "what embeddings do these token ids produce?"       -> clip.encode_token_weights_component

Both are closed, data-only SDK ops. Everything else the engine does --
attention parsing, emphasis multipliers, mean renormalisation, BREAK chunking,
comma backtracking, prompt-editing schedules -- is pack math and stays here,
byte-for-byte as upstream wrote it.

This module holds no state across dispatches and caches nothing globally.
"""
from __future__ import annotations

import torch


#: `encode_token_weights_component` is defined for the conventional SD1/SDXL
#: text encoders only. A T5 or Gemma component has no component encoder on the
#: closed op, so the A1111 pipeline cannot be offered for it.
SUPPORTED_COMPONENTS = ("l", "g")

EMBEDDING_IDENTIFIER = "embedding:"


class UnsupportedByBridge(RuntimeError):
    """A prompt or model asks for something the closed CLIP ops cannot express."""


def escape_for_tokenizer(text: str) -> str:
    """Quote a literal fragment so the host tokenizer does not re-read it.

    The pack's attention parser has already consumed emphasis syntax and hands
    us the *literal* text of a fragment. `comfy.sd1_clip.token_weights` would
    parse `(...)` all over again -- and a prompt written `\\(cat\\)` really does
    contain a literal parenthesis by the time it reaches us. `escape_important`
    recognises exactly `\\(` and `\\)`, so re-escaping those two characters is
    both necessary and sufficient.
    """
    return text.replace("(", "\\(").replace(")", "\\)")


class ComponentBridge:
    """One CLIP component (`l` or `g`) as the text-processing engine sees it."""

    def __init__(self, clip, component, *, id_start, id_end, id_pad,
                 chunk_length, comma_token):
        self._clip = clip
        self.component = component
        self.id_start = id_start
        self.id_end = id_end
        self.id_pad = id_pad
        #: full padded row width the host tokenizer emits (77 for SD/SDXL)
        self.row_length = chunk_length
        #: usable content width, which is what A1111 calls `chunk_length`
        self.chunk_length = chunk_length - 2
        self.comma_token = comma_token

    # -- question 1: text -> token ids -----------------------------------

    def _strip(self, rows):
        """Recover the raw fragment ids from padded `[start] ... [end] pad*` rows.

        Splitting on the FIRST end token rather than trimming trailing pads is
        deliberate. SDXL's CLIP-G pads with token id 0, and 0 is a perfectly
        ordinary content token ('!'), so a trailing-pad trim would silently eat
        a real character. The end token is special and never produced by the
        BPE for ordinary text, which makes the first occurrence unambiguous.
        """
        ids = []
        for row in rows:
            tokens = [entry[0] for entry in row]
            for token in tokens:
                if not isinstance(token, int):
                    raise UnsupportedByBridge(
                        "this prompt resolves to a pre-computed embedding "
                        "tensor, which the closed CLIP ops cannot return to a "
                        "node; use the 'comfy' parser for embeddings"
                    )
            if tokens and tokens[0] == self.id_start:
                tokens = tokens[1:]
            try:
                end = tokens.index(self.id_end)
            except ValueError:
                end = len(tokens)
            ids.extend(tokens[:end])
        return ids

    async def tokenize(self, texts):
        """Mirror `tokenizer(texts, truncation=False, add_special_tokens=False)`."""
        out = []
        for text in texts:
            if EMBEDDING_IDENTIFIER in text:
                raise UnsupportedByBridge(
                    "textual inversion embeddings are only available through "
                    "the 'comfy' parser; the weighted parsers would need the "
                    "embedding vectors themselves inside the node"
                )
            tokenized = await self._clip.tokenize(escape_for_tokenizer(text))
            out.append(self._strip(tokenized[self.component]))
        return out

    # -- question 2: token ids -> embeddings ------------------------------

    async def encode_rows(self, rows):
        """Encode a batch of equal-length token rows unweighted.

        Weights are deliberately all 1.0: core's own `encode_token_weights`
        applies ComfyUI's interpolate-from-empty weighting, which is NOT the
        A1111 scheme. Sending 1.0 makes that step the identity and leaves the
        emphasis math to `emphasis.py`, exactly where upstream keeps it.

        One call per row, because core returns a single `first_pooled` for a
        whole call and A1111 needs one pooled vector per prompt in the batch.
        """
        embeddings = []
        pooled = []
        for row in rows:
            pairs = [[(int(token), 1.0) for token in row]]
            embedding_ref, pooled_ref = (
                await self._clip.encode_token_weights_component(
                    self.component, pairs
                )
            )
            embedding = await embedding_ref.raw()
            embeddings.append(embedding.reshape(1, len(row), -1))
            pooled.append(
                None if pooled_ref is None else await pooled_ref.raw()
            )
        stacked = torch.cat(embeddings, dim=0)
        if any(entry is None for entry in pooled):
            return stacked, None
        return stacked, torch.cat(
            [entry.reshape(1, -1) for entry in pooled], dim=0
        )


async def build_bridges(clip):
    """Discover this CLIP's usable components and their special token ids.

    There is no op that reports a text encoder's class or component list, so
    discovery goes through the tokenizer's own output: the keys of
    `clip.tokenize("")` are the component names, and the empty prompt's single
    row is `[start] [end] pad*`, which names all three special ids at once.
    """
    empty = await clip.tokenize("")
    if not isinstance(empty, dict) or not empty:
        raise UnsupportedByBridge("this CLIP did not report any components")

    unsupported = [key for key in empty if key not in SUPPORTED_COMPONENTS]
    usable = [key for key in SUPPORTED_COMPONENTS if key in empty]
    if not usable:
        raise UnsupportedByBridge(
            "the weighted parsers support the CLIP-L/CLIP-G encoders; this "
            f"model reports {sorted(empty)}"
        )
    if unsupported:
        raise UnsupportedByBridge(
            "the weighted parsers cannot encode the "
            f"{sorted(unsupported)} component(s) of this model; core exposes "
            "component encoding for CLIP-L/CLIP-G only. Use the 'comfy' parser"
        )

    comma = await clip.tokenize(",")
    bridges = {}
    for component in usable:
        row = empty[component][0]
        if len(row) < 3:
            raise UnsupportedByBridge(
                f"component {component!r} reported an unusable empty prompt"
            )
        id_start = row[0][0]
        id_end = row[1][0]
        id_pad = row[-1][0]
        comma_row = [entry[0] for entry in comma[component][0]]
        comma_token = comma_row[1] if len(comma_row) > 1 else None
        if comma_token == id_end:
            comma_token = None
        bridges[component] = ComponentBridge(
            clip, component,
            id_start=id_start, id_end=id_end, id_pad=id_pad,
            chunk_length=len(row), comma_token=comma_token,
        )
    return bridges
