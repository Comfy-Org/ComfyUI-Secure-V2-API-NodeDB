"""Pinned Efficiency-Nodes prompt weighting used by quadmoonCLIPTextEncode2."""
from __future__ import annotations

from typing import Any

import numpy as np
import torch

from comfy_api.latest import sdk


def _component_data(tokenized: list) -> tuple[list, list, list]:
    tokens, weights, word_ids = [], [], []
    if not isinstance(tokenized, list) or not tokenized:
        raise ValueError("advanced prompt encoding needs token chunks")
    for chunk_index, chunk in enumerate(tokenized):
        if not isinstance(chunk, list) or not chunk:
            raise ValueError(f"advanced token chunk {chunk_index} is malformed")
        token_row, weight_row, word_row = [], [], []
        for entry_index, entry in enumerate(chunk):
            if not isinstance(entry, (tuple, list)) or len(entry) < 3:
                raise ValueError(
                    f"advanced token entry {chunk_index}:{entry_index} "
                    "does not include a word id"
                )
            token_row.append(entry[0])
            weight_row.append(float(entry[1]))
            word_row.append(entry[2])
        tokens.append(token_row)
        weights.append(weight_row)
        word_ids.append(word_row)
    return tokens, weights, word_ids


def _weighted_pairs(tokens: list, weights: list) -> list:
    return [
        [(token, float(weight))
         for token, weight in zip(row, weight_row, strict=True)]
        for row, weight_row in zip(tokens, weights, strict=True)
    ]


async def _encode_component(clip, component: str, pairs: list):
    embedding_ref, pooled_ref = await clip.encode_token_weights_component(
        component, pairs,
    )
    embedding = await embedding_ref.raw()
    pooled = None if pooled_ref is None else await pooled_ref.raw()
    return embedding, pooled


async def _batched_encode(
    clip, component: str, pairs: list, *, chunk_length: int,
    chunks_per_prompt: int,
) -> torch.Tensor:
    encoded = []
    for start in range(0, len(pairs), 32):
        batch = pairs[start:start + 32]
        embedding, _ = await _encode_component(clip, component, batch)
        encoded.append(embedding.reshape(len(batch), chunk_length, -1))
    combined = torch.cat(encoded)
    if len(pairs) % chunks_per_prompt:
        raise ValueError("masked prompt batch lost its token-chunk alignment")
    return combined.reshape(
        len(pairs) // chunks_per_prompt,
        chunk_length * chunks_per_prompt,
        -1,
    )


def _mask_word_id(
    tokens: list, word_ids: list, target: Any, mask_token: tuple[Any, float],
) -> tuple[list, np.ndarray]:
    masked = [
        [mask_token if word_id == target else token
         for token, word_id in zip(row, word_row, strict=True)]
        for row, word_row in zip(tokens, word_ids, strict=True)
    ]
    return masked, np.asarray(word_ids, dtype=object) == target


def _mask_flat_indices(
    tokens: list, indices: np.ndarray, mask_token: tuple[Any, float],
) -> list:
    chunk_length = len(tokens[0])
    selected = {int(index) for index in indices.tolist()}
    return [
        [mask_token if row_index * chunk_length + column in selected else token
         for column, token in enumerate(row)]
        for row_index, row in enumerate(tokens)
    ]


async def _down_weight(
    clip, component: str, tokens: list, weights: list, word_ids: list,
    base: torch.Tensor, chunk_length: int, *, mask_token_id: int = 266,
) -> tuple[torch.Tensor, list, torch.Tensor]:
    unique, inverse = np.unique(np.asarray(weights), return_inverse=True)
    if np.sum(unique < 1) == 0:
        return base, tokens, base[0, chunk_length - 1:chunk_length, :]
    mask_token = (mask_token_id, 1.0)
    current = tokens
    prompts = []
    for index, weight in enumerate(unique):
        if weight >= 1:
            continue
        current = _mask_flat_indices(
            current, np.where(inverse == index)[0], mask_token,
        )
        prompts.extend(current)
    embeddings = await _batched_encode(
        clip, component, prompts,
        chunk_length=chunk_length,
        chunks_per_prompt=len(tokens),
    )
    embeddings = torch.cat((base, embeddings))
    bounded = unique[unique <= 1.0]
    mixing = torch.as_tensor(
        np.diff([0.0] + bounded.tolist()),
        dtype=embeddings.dtype,
        device=embeddings.device,
    ).reshape((-1, 1, 1))
    if mixing.shape[0] != embeddings.shape[0]:
        raise ValueError("down-weight prompt did not contain a unit-weight token")
    weighted = (mixing * embeddings).sum(dim=0, keepdim=True)
    return weighted, current, weighted[0, chunk_length - 1:chunk_length, :]


async def _masked_word_embeddings(
    clip, component: str, tokens: list, weights: list, word_ids: list,
    base: torch.Tensor, chunk_length: int, *, mask_token_id: int = 266,
) -> tuple[torch.Tensor, torch.Tensor]:
    pooled_base = base[0, chunk_length - 1:chunk_length, :]
    flat_word_ids = np.asarray(word_ids, dtype=object).reshape(-1)
    flat_weights = np.asarray(weights, dtype=float).reshape(-1)
    unique_ids, first_indices = np.unique(flat_word_ids, return_index=True)
    weighted_words = [
        (word_id, float(flat_weights[index]))
        for word_id, index in zip(unique_ids, first_indices, strict=True)
        if float(flat_weights[index]) != 1.0
    ]
    if not weighted_words:
        return torch.zeros_like(base), pooled_base

    all_weights = torch.as_tensor(
        weights, dtype=base.dtype, device=base.device,
    ).reshape(1, -1, 1).expand_as(base)
    mask_token = (mask_token_id, 1.0)
    prompts, masks, selected_weights = [], [], []
    for word_id, weight in weighted_words:
        masked, selected = _mask_word_id(
            tokens, word_ids, word_id, mask_token,
        )
        prompts.extend(masked)
        masks.append(torch.as_tensor(
            selected, dtype=base.dtype, device=base.device,
        ).reshape(1, -1, 1).expand_as(base))
        selected_weights.append(weight)

    embeddings = await _batched_encode(
        clip, component, prompts,
        chunk_length=chunk_length,
        chunks_per_prompt=len(tokens),
    )
    mask_tensor = torch.cat(masks)
    differences = base.expand_as(embeddings) - embeddings
    pooled = differences[0, chunk_length - 1:chunk_length, :]
    differences = (differences * mask_tensor).sum(dim=0, keepdim=True)
    pooled_start = pooled_base.expand(len(selected_weights), -1)
    selected = torch.tensor(
        selected_weights, device=pooled_start.device,
    ).reshape(-1, 1).expand_as(pooled_start)
    pooled = ((pooled - pooled_start) * (selected - 1.0)).mean(
        dim=0, keepdim=True,
    )
    return (all_weights - 1.0) * differences, pooled_base + pooled


async def _advanced_component(
    clip, component: str, tokenized: list, interpretation: str,
    *, return_pooled: bool,
) -> tuple[torch.Tensor, torch.Tensor | None]:
    tokens, weights, word_ids = _component_data(tokenized)
    chunk_length = len(tokens[0])
    if any(len(row) != chunk_length for row in tokens):
        raise ValueError("advanced prompt token chunks have inconsistent lengths")
    unweighted = _weighted_pairs(
        tokens, [[1.0] * len(row) for row in tokens],
    )
    base, pooled_base = await _encode_component(clip, component, unweighted)

    if interpretation == "A1111":
        weight_tensor = torch.as_tensor(
            weights, dtype=base.dtype, device=base.device,
        ).reshape(1, -1, 1).expand_as(base)
        weighted = base * weight_tensor
        weighted = (base.mean() / weighted.mean()) * weighted
        pooled = pooled_base
    elif interpretation == "compel":
        positive_weights = [
            [weight if weight >= 1.0 else 1.0 for weight in row]
            for row in weights
        ]
        positive_tokens = _weighted_pairs(tokens, positive_weights)
        positive_embedding, _ = await _encode_component(
            clip, component, positive_tokens,
        )
        weighted, _, pooled = await _down_weight(
            clip, component, positive_tokens, weights, word_ids,
            positive_embedding, chunk_length,
        )
    elif interpretation == "comfy++":
        weighted, _, _ = await _down_weight(
            clip, component, unweighted, weights, word_ids,
            base, chunk_length,
        )
        up_weights = [
            [weight if weight > 1.0 else 1.0 for weight in row]
            for row in weights
        ]
        additions, pooled = await _masked_word_embeddings(
            clip, component, unweighted, up_weights, word_ids,
            base, chunk_length,
        )
        weighted = weighted + additions
    elif interpretation == "down_weight":
        top = max(weight for row in weights for weight in row)
        limit = min(top, 1.0)
        if top == 0:
            raise ValueError("down-weight prompt cannot normalize zero weights")
        scaled = [
            [limit if word_id == 0 else (weight / top) * limit
             for weight, word_id in zip(row, word_row, strict=True)]
            for row, word_row in zip(weights, word_ids, strict=True)
        ]
        weighted, _, pooled = await _down_weight(
            clip, component, unweighted, scaled, word_ids,
            base, chunk_length,
        )
    else:
        raise ValueError(f"unknown prompt weight interpretation {interpretation!r}")
    return weighted, pooled if return_pooled else None


async def encode_prompt(clip, text: str, interpretation: str):
    """Reproduce the pinned Efficiency encode path with normalization=none."""
    tokens = await clip.tokenize(str(text), return_word_ids=True)
    interpretation = str(interpretation)
    if interpretation == "comfy":
        return await clip.encode_from_tokens_scheduled(tokens)
    if interpretation not in {"A1111", "compel", "comfy++", "down_weight"}:
        raise ValueError(f"unknown prompt weight interpretation {interpretation!r}")
    components = [key for key in ("l", "g") if key in tokens]
    if not components:
        raise ValueError("advanced prompt weighting supports CLIP-L/CLIP-G encoders")
    encoded = {}
    for component in components:
        # The pinned Efficiency helper asks only CLIP-G for a pooled value.
        # Plain SD1/CLIP-L conditioning therefore retains pooled_output=None.
        encoded[component] = await _advanced_component(
            clip, component, tokens[component], interpretation,
            return_pooled=component == "g",
        )
    if components == ["l", "g"]:
        embedding = torch.cat((encoded["l"][0], encoded["g"][0]), dim=-1)
        pooled = encoded["g"][1]
    else:
        embedding, pooled = encoded[components[0]]
    return await sdk.CondRef.from_value(
        [[embedding, {"pooled_output": pooled}]],
    )


__all__ = ["encode_prompt"]
