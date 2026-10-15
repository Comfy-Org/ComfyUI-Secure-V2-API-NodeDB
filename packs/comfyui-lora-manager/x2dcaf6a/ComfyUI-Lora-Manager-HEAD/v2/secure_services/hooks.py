"""Native Hook sequencing over admitted assets and imported authored records."""
from __future__ import annotations

import logging

from comfy_api.latest import sdk

from ..secure_algorithms.hook_selection import append_hook_success, finish_hook_summaries
from ..secure_algorithms.lora_requests import apply_lora_syntax_format, get_loras_list
from .managed_library import _logical, _match, _stem, _syntax_format, read_loader_record

logger = logging.getLogger(__name__)


async def create_managed_hooks(text, loras, *, prev_hooks=None) -> tuple:
    del text
    group = (await sdk.Hooks.clone(prev_hooks) if prev_hooks is not None
             else await sdk.Hooks.empty())
    active, words = [], []
    for row in get_loras_list({'loras': loras}):
        if not row.get('active', False):
            continue
        # Native formats each active entry before strength parsing or zero skip.
        name = apply_lora_syntax_format(row['name'], await _syntax_format())
        model_strength = float(row['strength'])
        clip_strength = float(row.get('clipStrength', model_strength))
        if model_strength == 0. and clip_strength == 0.:
            continue
        catalogue = await sdk.ctx().assets.list('loras')
        for candidate in catalogue:
            _logical(candidate)
        try:
            logical = _match(name, catalogue)
        except ValueError:
            logger.warning("LoRA '%s' not found — skipping", name)
            continue
        try:
            record = await read_loader_record(logical)
        except FileNotFoundError:
            logger.warning("LoRA '%s' not found — skipping", name)
            continue
        metadata = record['metadata']
        # Absent imported metadata is an integration gap, not default words.
        if metadata is None:
            raise ValueError('Native LoRA metadata has not been imported')
        civitai = metadata.get('civitai') or {}
        trigger_words = civitai.get('trainedWords', [])
        try:
            created = await sdk.Hooks.create_lora(record['asset'], model_strength, clip_strength)
        except Exception:
            logger.exception("Failed to load LoRA '%s' — skipping", name)
            continue
        # Native combine errors propagate; summaries follow successful combine.
        group = await sdk.Hooks.clone_and_combine(group, created)
        append_hook_success(active, words, (name, model_strength, clip_strength), trigger_words)
    return group, *finish_hook_summaries(active, words)


def _queue_match(name: str, catalogue: list[str]) -> str | None:
    # Native queue lookup prefers the first prefix match, then first basename.
    name = _stem(name.replace('\\', '/'))
    exact = next((item for item in catalogue
                  if name in (_stem(item), _stem(item).rsplit('/', 1)[-1])), None)
    if exact is not None or '/' not in name:
        return exact
    candidates = [item for item in catalogue
                  if _stem(item).rsplit('/', 1)[-1] == name.rsplit('/', 1)[-1]]
    for item in candidates:
        folder = item.rsplit('/', 1)[0] if '/' in item else ''
        if folder and name.startswith(folder + '/'):
            return item
    return candidates[0] if candidates else None


async def validate_hook_entries(loras) -> bool | str:
    if not loras:
        return True
    names = []
    for row in get_loras_list({'loras': loras}):
        if not isinstance(row, dict) or not row.get('active', False):
            continue
        names.append(apply_lora_syntax_format(str(row.get('name') or ''), await _syntax_format()))
    if not names:
        return True
    try:
        catalogue = await sdk.ctx().assets.list('loras')
        missing = []
        for name in names:
            if not name:
                continue
            logical = _queue_match(name, catalogue)
            if logical is None:
                missing.append(name)
                continue
            try:
                await sdk.ctx().assets.resolve('loras', logical)
            except FileNotFoundError:
                missing.append(name)
    except Exception:
        # Original cannot-verify catalogue validation allows queueing. Execution
        # still enforces permissions, imported records and confined asset refs.
        logger.exception('Failed to validate LoRA entries against the local library')
        return True
    return 'Missing LoRA(s) in local library: ' + ', '.join(missing) if missing else True
