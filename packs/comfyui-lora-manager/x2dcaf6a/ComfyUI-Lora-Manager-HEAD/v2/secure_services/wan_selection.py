"""Owned WAN selector execution, pending actual cache-owner node binding.

The snapshot and business-path/catalogue binding must come from their real owner.
This service does not acquire them, invent a public API, default metadata, or
register original nodes. JACK owns the separate WAN model consumer.
"""
from __future__ import annotations

from ..secure_algorithms.wan_identity import lookup_cache_lora, relative_name_for_path
from ..secure_algorithms.wan_selection import (
    append_resolved_entry, begin_text_selection, begin_widget_selection,
    finish_selection, iter_text_requests, iter_widget_requests,
)
from .wan_selection_assets import resolve_selected_lora_asset


async def _append_request(
    state: dict, request: tuple, *, cache_rows: list,
    catalogue_bindings: dict, loras_roots: list, extra_loras_roots: list,
) -> None:
    native_path, words = lookup_cache_lora(request[0], cache_rows)
    # Preserve native name projection before row mutation. A relative path is
    # not a containment check; extra-root names may legitimately contain ../.
    relative_name = relative_name_for_path(native_path, loras_roots, extra_loras_roots)
    if native_path not in catalogue_bindings:
        # Native unresolved names are rows, not skipped requests. That branch
        # needs an explicit wire/consumer policy before a public node can bind.
        raise NotImplementedError(
            'Native selector cache path has no owner-established catalogue identity; '
            'unresolved requests are not silently skipped')
    selected, _asset = await resolve_selected_lora_asset(catalogue_bindings[native_path])
    append_resolved_entry(state, request, selected, relative_name, words)


async def select_widget_loras(
    text: str, loras: object, low_mem_load: bool = False, merge_loras: bool = True,
    *, cache_rows: list, catalogue_bindings: dict,
    loras_roots: list, extra_loras_roots: list, **kwargs,
) -> tuple:
    # Native ignores the autocomplete text during execution. Widget validation
    # is a separate queue stage and is not emulated here.
    state = begin_widget_selection(low_mem_load, merge_loras, **kwargs)
    for request in iter_widget_requests(loras):
        await _append_request(state, request, cache_rows=cache_rows,
            catalogue_bindings=catalogue_bindings, loras_roots=loras_roots,
            extra_loras_roots=extra_loras_roots)
    return finish_selection(state)


async def select_text_loras(
    lora_syntax: str, low_mem_load: bool = False, merge_lora: bool = True,
    *, cache_rows: list, catalogue_bindings: dict,
    loras_roots: list, extra_loras_roots: list, **kwargs,
) -> tuple:
    # Native text parsing and initialization differ from the widget producer.
    state = begin_text_selection(low_mem_load, merge_lora, **kwargs)
    for request in iter_text_requests(lora_syntax):
        await _append_request(state, request, cache_rows=cache_rows,
            catalogue_bindings=catalogue_bindings, loras_roots=loras_roots,
            extra_loras_roots=extra_loras_roots)
    return finish_selection(state)
