"""PPM-owned attention-coupling and NegPiP tensor programs.

The retained bridge is expected to supply host-owned encoder/attention tensors
under strict budgets.  Grouping, mask blending, and negative-weight policy are
kept here because they are PPM behavior, not general Secure Nodes API code.
"""
from __future__ import annotations

import itertools
import math


COND = 0
UNCOND = 1


def _least_common_multiple(values):
    result = int(values[0])
    for value in values[1:]:
        result = math.lcm(result, int(value))
    return result


def normalize_masks(masks):
    import torch

    value = torch.stack(list(masks), dim=0)
    total = value.sum(dim=0, keepdim=True)
    if total.min() <= 0:
        raise ValueError("Masks contain non-filled areas")
    return value / total


def reshape_masks(masks, size, batch_size, token_count):
    import torch.nn.functional as functional

    condition_count = masks.shape[0]
    downsampled = functional.interpolate(masks, size=size, mode="nearest")
    return downsampled.view(condition_count, token_count, 1).repeat_interleave(
        int(batch_size), dim=0
    )


def split_negpip_conditioning(conditioning, enabled):
    if not enabled:
        return conditioning, conditioning
    key, value = conditioning[:, 0::2], conditioning[:, 1::2]
    return (key, value) if key.shape == value.shape else (
        conditioning,
        conditioning,
    )


def attention_couple_pre(
    query,
    key,
    value,
    cond_or_uncond,
    conditionings,
    strengths,
    base_strength=1.0,
    has_negpip=False,
):
    """Expand conditional attention groups and return retained merge state."""
    import torch

    if not conditionings:
        return query, key, value, list(cond_or_uncond)
    if len(conditionings) != len(strengths):
        raise ValueError("conditioning strengths do not match conditionings")

    conditioning_kv = [
        split_negpip_conditioning(item, has_negpip)
        for item in conditionings
    ]
    key_lengths = [item[0].shape[1] for item in conditioning_kv]
    value_lengths = [item[1].shape[1] for item in conditioning_kv]
    chunks = len(cond_or_uncond)
    if chunks < 1 or query.shape[0] % chunks:
        raise ValueError("attention batch does not match cond/uncond groups")
    batch_size = query.shape[0] // chunks
    query_chunks = query.chunk(chunks, dim=0)
    key_chunks = key.chunk(chunks, dim=0)
    value_chunks = value.chunk(chunks, dim=0)
    common_key_length = _least_common_multiple([*key_lengths, key.shape[1]])
    common_value_length = _least_common_multiple(
        [*value_lengths, value.shape[1]]
    )
    extra_keys = torch.cat([
        item[0].repeat(batch_size, common_key_length // key_lengths[index], 1)
        * float(strengths[index])
        for index, item in enumerate(conditioning_kv)
    ], dim=0)
    extra_values = torch.cat([
        item[1].repeat(
            batch_size, common_value_length // value_lengths[index], 1
        ) * float(strengths[index])
        for index, item in enumerate(conditioning_kv)
    ], dim=0)

    queries, keys, values, merge_groups = [], [], [], []
    condition_count = len(conditionings) + 1
    for index, group_type in enumerate(cond_or_uncond):
        target_query = query_chunks[index]
        target_key = key_chunks[index].repeat(
            1, common_key_length // key.shape[1], 1
        )
        target_value = value_chunks[index].repeat(
            1, common_value_length // value.shape[1], 1
        )
        if group_type == UNCOND:
            queries.append(target_query)
            keys.append(target_key)
            values.append(target_value)
            merge_groups.append(UNCOND)
        else:
            queries.append(target_query.repeat(condition_count, 1, 1))
            keys.append(torch.cat([
                target_key * float(base_strength), extra_keys,
            ], dim=0))
            values.append(torch.cat([
                target_value * float(base_strength), extra_values,
            ], dim=0))
            merge_groups.extend(itertools.repeat(COND, condition_count))
    return (
        torch.cat(queries, dim=0),
        torch.cat(keys, dim=0),
        torch.cat(values, dim=0),
        merge_groups,
    )


def attention_couple_post(output, merge_groups, activation_shape, masks):
    import torch

    if not merge_groups or output.shape[0] % len(merge_groups):
        raise ValueError("attention output does not match retained merge groups")
    size = tuple(activation_shape[-2:])
    batch_size = output.shape[0] // len(merge_groups)
    token_count = output.shape[1]
    downsampled_masks = reshape_masks(
        masks, size, batch_size, token_count
    )
    outputs, conditional_outputs = [], []
    conditional_index = 0
    for index, group_type in enumerate(merge_groups):
        start, end = index * batch_size, (index + 1) * batch_size
        if group_type == UNCOND:
            outputs.append(output[start:end])
            continue
        mask_start = conditional_index * batch_size
        mask_end = (conditional_index + 1) * batch_size
        conditional_outputs.append(
            output[start:end] * downsampled_masks[mask_start:mask_end]
        )
        conditional_index += 1
    if conditional_outputs:
        outputs.append(torch.stack(conditional_outputs).sum(0))
    return torch.cat(outputs, dim=0)


def cosmos_attention_couple_pre(query, context, cond_or_uncond, conditionings):
    """Expand PPM's Anima/Cosmos cross-attention inputs.

    Unlike the canonical UNet path, Comfy's sampler-time conditioning
    preparation has already applied strengths.  The transformer receives one
    context tensor rather than separate key/value tensors.
    """
    import torch

    if not conditionings:
        return query, context, list(cond_or_uncond)
    chunks = len(cond_or_uncond)
    if chunks < 1 or query.shape[0] % chunks:
        raise ValueError("attention batch does not match cond/uncond groups")
    batch_size = query.shape[0] // chunks
    query_chunks = query.chunk(chunks, dim=0)
    context_chunks = context.chunk(chunks, dim=0)
    token_lengths = [item.shape[1] for item in conditionings]
    common_length = _least_common_multiple([
        *token_lengths, context.shape[1],
    ])
    extra_context = torch.cat([
        item.repeat(batch_size, common_length // token_lengths[index], 1)
        for index, item in enumerate(conditionings)
    ], dim=0)

    queries, contexts, merge_groups = [], [], []
    region_count = len(conditionings) + 1
    for index, group_type in enumerate(cond_or_uncond):
        target_query = query_chunks[index]
        target_context = context_chunks[index].repeat(
            1, common_length // context.shape[1], 1)
        if group_type == UNCOND:
            queries.append(target_query)
            contexts.append(target_context)
            merge_groups.append(UNCOND)
        else:
            queries.append(target_query.repeat(region_count, 1, 1))
            contexts.append(torch.cat([target_context, extra_context], dim=0))
            merge_groups.extend(itertools.repeat(COND, region_count))
    return torch.cat(queries, dim=0), torch.cat(contexts, dim=0), merge_groups


def cosmos_attention_couple_pre_negpip(
    query,
    context,
    cond_or_uncond,
    conditionings,
    negpip_mask,
    negpip_masks,
):
    """Expand Anima regional context and its matching NegPiP sign mask.

    Upstream treats the sign mask as a token-axis sidecar.  It follows the
    same conditional-region expansion as context, but keeps its own token
    least-common-multiple because a padded Anima mask may be longer than the
    encoded context row.
    """
    import torch

    expanded_query, expanded_context, merge_groups = (
        cosmos_attention_couple_pre(
            query, context, cond_or_uncond, conditionings)
    )
    chunks = len(cond_or_uncond)
    batch_size = query.shape[0] // chunks
    mask_chunks = negpip_mask.chunk(chunks, dim=0)
    mask_lengths = [item.shape[1] for item in negpip_masks]
    common_length = _least_common_multiple([
        *mask_lengths, negpip_mask.shape[1],
    ])
    extra_masks = [
        item.repeat(batch_size, common_length // mask_lengths[index], 1)
        for index, item in enumerate(negpip_masks)
    ]
    extra_mask = torch.cat(extra_masks, dim=0) if extra_masks else None
    masks = []
    for index, group_type in enumerate(cond_or_uncond):
        target = mask_chunks[index].repeat(
            1, common_length // negpip_mask.shape[1], 1)
        if group_type == UNCOND or extra_mask is None:
            masks.append(target)
        else:
            masks.append(torch.cat([target, extra_mask], dim=0))
    return (
        expanded_query,
        expanded_context,
        torch.cat(masks, dim=0),
        merge_groups,
    )


def make_regional_attention_program():
    """Return the retained three-phase Attention Couple closure.

    Host-owned conditioning and mask refs are declared at registration.  The
    host projects their tensor rows once through ``prepare``; the normalized
    masks and conditioning copies below are then ordinary pack-plane state.
    Later ``pre``/``post`` calls receive only the tensors and small metadata
    belonging to the current canonical-UNet attention site.
    """
    conditionings = None
    strengths = None
    base_strength = None
    masks = None

    def regional_attention(phase, *args):
        nonlocal conditionings, strengths, base_strength, masks
        if phase == "prepare":
            if len(args) != 4:
                raise ValueError("regional attention prepare needs four arguments")
            prepared_conditionings, prepared_strengths, prepared_base, raw_masks = args
            if len(prepared_conditionings) != len(prepared_strengths):
                raise ValueError(
                    "regional attention conditioning strengths do not match")
            conditionings = list(prepared_conditionings)
            strengths = [float(value) for value in prepared_strengths]
            base_strength = float(prepared_base)
            masks = normalize_masks(list(raw_masks))
            if masks.shape[0] != len(conditionings) + 1:
                raise ValueError(
                    "regional attention needs one mask per conditioning")
            return None
        if phase == "prepare_cosmos":
            if len(args) != 2:
                raise ValueError(
                    "regional attention Cosmos prepare needs two arguments")
            prepared_conditionings, raw_masks = args
            conditionings = list(prepared_conditionings)
            strengths = [1.0] * len(conditionings)
            base_strength = 1.0
            masks = normalize_masks(list(raw_masks))
            if masks.shape[0] != len(conditionings) + 1:
                raise ValueError(
                    "regional attention needs one mask per conditioning")
            return None
        if conditionings is None or masks is None:
            raise RuntimeError("regional attention was invoked before prepare")
        if phase == "pre":
            if len(args) != 5:
                raise ValueError("regional attention pre needs five arguments")
            query, key, value, cond_or_uncond, has_negpip = args
            return attention_couple_pre(
                query,
                key,
                value,
                list(cond_or_uncond),
                conditionings,
                strengths,
                base_strength,
                bool(has_negpip),
            )[:3]
        if phase == "post":
            if len(args) != 3:
                raise ValueError("regional attention post needs three arguments")
            output, merge_groups, activation_shape = args
            return attention_couple_post(
                output, list(merge_groups), list(activation_shape), masks)
        if phase == "pre_cosmos":
            if len(args) != 3:
                raise ValueError(
                    "regional attention Cosmos pre needs three arguments")
            query, context, cond_or_uncond = args
            return cosmos_attention_couple_pre(
                query, context, list(cond_or_uncond), conditionings)[:2]
        if phase == "pre_cosmos_negpip":
            if len(args) != 5:
                raise ValueError(
                    "regional attention Cosmos/NegPiP pre needs five arguments")
            query, context, cond_or_uncond, negpip_mask, negpip_masks = args
            return cosmos_attention_couple_pre_negpip(
                query,
                context,
                list(cond_or_uncond),
                conditionings,
                negpip_mask,
                list(negpip_masks),
            )[:3]
        raise ValueError(f"unknown regional attention phase {phase!r}")

    return regional_attention


def sdxl_negpip_attention(query, key, value):
    return query, key[:, 0::2], value[:, 1::2]


def negpip_interleave_embeddings(
    encoded, weight_rows, empty_index=None,
):
    """Apply PPM's K/V sign policy to host-produced unweighted embeddings.

    ``encoded`` contains one row per token section and an optional host-created
    empty-token row. The empty row exists only when a weight differs from 1.0
    or there are zero sections, exactly matching the pinned source. Supplying
    those base rows is the host adapter's responsibility; weight arithmetic
    remains in this pack.
    """
    import torch

    sections = len(weight_rows)
    if not isinstance(encoded, torch.Tensor) or encoded.ndim != 3:
        raise TypeError("NegPiP encoded rows must be a rank-3 tensor")
    if encoded.shape[0] < sections:
        raise ValueError("NegPiP encoding has fewer rows than token sections")
    if empty_index is not None and (
        isinstance(empty_index, bool)
        or not isinstance(empty_index, int)
        or not 0 <= empty_index < encoded.shape[0]
    ):
        raise ValueError("NegPiP empty row index is invalid")
    if sections == 0:
        if empty_index is None:
            raise ValueError("zero-section NegPiP encoding needs an empty row")
        return encoded[empty_index:empty_index + 1]
    has_weights = any(
        float(weight) != 1.0
        for section in weight_rows
        for weight in section
    )
    if has_weights and empty_index is None:
        raise ValueError("weighted NegPiP encoding needs an empty-token row")
    empty = None if empty_index is None else encoded[empty_index]
    output = []
    for section_index, weights in enumerate(weight_rows):
        key = encoded[section_index:section_index + 1].clone()
        value = encoded[section_index:section_index + 1].clone()
        if len(weights) > key.shape[1]:
            raise ValueError("NegPiP token weights exceed encoded tokens")
        for token_index, raw_weight in enumerate(weights):
            weight = float(raw_weight)
            if weight == 1.0:
                continue
            if empty is None:
                raise ValueError("weighted NegPiP encoding has no empty row")
            key[:, token_index] = (
                key[:, token_index] - empty[token_index]
            ) * abs(weight) + empty[token_index]
            value[:, token_index] = (
                value[:, token_index] - empty[token_index]
            ) * abs(weight) + empty[token_index]
            if weight < 0.0:
                value[:, token_index] = -value[:, token_index]
        interleaved = torch.zeros_like(key).repeat(1, 2, 1)
        for token_index in range(key.shape[1]):
            interleaved[:, token_index * 2] = key[:, token_index]
            interleaved[:, token_index * 2 + 1] = value[:, token_index]
        output.append(interleaved)
    return torch.cat(output, dim=-2)


def make_negpip_program():
    """Return the retained future-encode/Anima weight program."""

    def negpip_program(phase, *args):
        if phase == "encode":
            if len(args) != 3:
                raise ValueError("NegPiP encode needs three arguments")
            encoded, weight_rows, empty_index = args
            return negpip_interleave_embeddings(
                encoded, weight_rows, empty_index)
        if phase == "anima_weights":
            if len(args) != 3:
                raise ValueError("Anima NegPiP weights need three arguments")
            signed_weights, minimum_length, empty_marker = args
            if empty_marker is not None:
                raise ValueError("Anima NegPiP does not accept an empty marker")
            return anima_negpip_mask(signed_weights, minimum_length)
        raise ValueError(f"unknown NegPiP phase {phase!r}")

    return negpip_program


def anima_negpip_mask(token_weights, minimum_length=512):
    import torch
    import torch.nn.functional as functional

    absolute = torch.abs(token_weights)
    mask = (token_weights == absolute).int()
    mask[mask == 0] = -1
    mask = mask.unsqueeze(0).unsqueeze(-1)
    if mask.shape[1] < int(minimum_length):
        mask = functional.pad(
            mask, (0, 0, 0, int(minimum_length) - mask.shape[1]), value=1.0
        )
    return absolute, mask


def anima_negpip_attention(query, key, value, negpip_mask=None, pe=None):
    output_value = value if negpip_mask is None else value * negpip_mask
    return {"q": query, "k": key, "v": output_value, "pe": pe}


__all__ = [
    "COND",
    "UNCOND",
    "anima_negpip_attention",
    "anima_negpip_mask",
    "attention_couple_post",
    "attention_couple_pre",
    "cosmos_attention_couple_pre",
    "make_regional_attention_program",
    "make_negpip_program",
    "negpip_interleave_embeddings",
    "normalize_masks",
    "sdxl_negpip_attention",
    "split_negpip_conditioning",
]
