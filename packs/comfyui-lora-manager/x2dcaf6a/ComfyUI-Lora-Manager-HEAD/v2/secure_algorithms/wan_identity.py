"""Pinned native cache/name projection over an actual owner snapshot.

Only the async scanner acquisition and config roots become explicit parameters.
Cache matching, ordered fallback, authored trainedWords and unresolved values
remain native. No snapshot is manufactured and no file operation is performed.
"""
from __future__ import annotations

import os

def lookup_cache_lora(lora_name: str, cache_rows: list) -> tuple:
    if os.path.isabs(lora_name):
        for item in cache_rows:
            file_path = item.get('file_path')
            if file_path and os.path.abspath(file_path) == os.path.abspath(lora_name):
                civitai = item.get('civitai') or {}
                return (file_path, civitai.get('trainedWords', []))
        return (lora_name, [])
    lora_name_normalized = lora_name.replace('\\', '/')
    lora_name_no_ext = lora_name_normalized
    for ext in ('.safetensors', '.ckpt', '.pt', '.bin'):
        if lora_name_no_ext.lower().endswith(ext):
            lora_name_no_ext = lora_name_no_ext[:-len(ext)]
            break
    has_path = '/' in lora_name_no_ext
    basename = os.path.basename(lora_name_no_ext) if has_path else lora_name_no_ext
    best_fallback = None
    for item in cache_rows:
        file_name = item.get('file_name', '')
        folder = item.get('folder', '')
        file_name_no_ext = file_name
        for ext in ('.safetensors', '.ckpt', '.pt', '.bin'):
            if file_name_no_ext.lower().endswith(ext):
                file_name_no_ext = file_name_no_ext[:-len(ext)]
                break
        path_name = f'{folder}/{file_name_no_ext}'.replace('\\', '/') if folder else file_name_no_ext
        if lora_name_no_ext == file_name_no_ext:
            file_path = item.get('file_path')
            if file_path:
                civitai = item.get('civitai', {})
                trigger_words = civitai.get('trainedWords', []) if civitai else []
                return (file_path, trigger_words)
        if lora_name_no_ext == path_name:
            file_path = item.get('file_path')
            if file_path:
                civitai = item.get('civitai', {})
                trigger_words = civitai.get('trainedWords', []) if civitai else []
                return (file_path, trigger_words)
        if has_path and file_name_no_ext == basename:
            if folder and lora_name_no_ext.startswith(folder.replace('\\', '/') + '/'):
                best_fallback = item
            elif best_fallback is None:
                best_fallback = item
    if best_fallback:
        file_path = best_fallback.get('file_path')
        if file_path:
            civitai = best_fallback.get('civitai', {})
            trigger_words = civitai.get('trainedWords', []) if civitai else []
            return (file_path, trigger_words)
    return (lora_name, [])

def relative_name_for_path(abs_path: str, loras_roots: list, extra_loras_roots: list) -> str:
    """Return abs_path relative to the first matching lora root, or basename as fallback."""
    all_roots = list(loras_roots or []) + list(extra_loras_roots or [])
    for root in all_roots:
        try:
            return os.path.relpath(abs_path, root)
        except ValueError:
            continue
    return os.path.basename(abs_path)
