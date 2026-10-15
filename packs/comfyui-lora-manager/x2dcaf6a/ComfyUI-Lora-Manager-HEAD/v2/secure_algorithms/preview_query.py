"""Pinned pure query methods. No scanner, settings singleton, model or routes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Mapping, Iterable, Protocol, cast
import time
import logging
logger = logging.getLogger(__name__)
NSFW_LEVELS = {"PG":1,"PG13":2,"R":4,"X":8,"XXX":16,"Blocked":32}
DEFAULT_CIVITAI_MODEL_TYPE = "LORA"
class SettingsProvider(Protocol):
    def get(self, key, default=None): ...

def _coerce_to_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate if candidate else None

def normalize_sub_type(value: Any) -> Optional[str]:
    """Return a lowercase string suitable for sub_type comparisons."""
    candidate = _coerce_to_str(value)
    return candidate.lower() if candidate else None

def resolve_sub_type(entry: Mapping[str, Any]) -> str:
    """Extract the sub-type from metadata, checking multiple sources.
    
    Priority:
    1. entry['sub_type'] - new canonical field
    2. entry['model_type'] - backward compatibility
    3. civitai.model.type - CivitAI API data
    4. DEFAULT_CIVITAI_MODEL_TYPE - fallback
    """
    if not isinstance(entry, Mapping):
        return DEFAULT_CIVITAI_MODEL_TYPE
    sub_type = _coerce_to_str(entry.get('sub_type'))
    if sub_type:
        return sub_type
    model_type = _coerce_to_str(entry.get('model_type'))
    if model_type:
        return model_type
    civitai = entry.get('civitai')
    if isinstance(civitai, Mapping):
        civitai_model = civitai.get('model')
        if isinstance(civitai_model, Mapping):
            civitai_type = _coerce_to_str(civitai_model.get('type'))
            if civitai_type:
                return civitai_type
    return DEFAULT_CIVITAI_MODEL_TYPE

@dataclass(frozen=True)
class FilterCriteria:
    """Container for model list filtering options."""
    folder: Optional[str] = None
    folder_include: Optional[Sequence[str]] = None
    folder_exclude: Optional[Sequence[str]] = None
    base_models: Optional[Sequence[str]] = None
    tags: Optional[Dict[str, str]] = None
    auto_tags: Optional[Dict[str, str]] = None
    favorites_only: bool = False
    search_options: Optional[Dict[str, Any]] = None
    model_types: Optional[Sequence[str]] = None
    tag_logic: str = 'any'

class ModelFilterSet:
    """Applies common filtering rules to the model collection."""

    def __init__(self, settings: SettingsProvider, nsfw_levels: Optional[Dict[str, int]]=None) -> None:
        self._settings = settings
        self._nsfw_levels = nsfw_levels or NSFW_LEVELS

    def apply(self, data: Iterable[Dict[str, Any]], criteria: FilterCriteria) -> List[Dict[str, Any]]:
        """Return items that satisfy the provided criteria."""
        overall_start = time.perf_counter()
        items = list(data)
        initial_count = len(items)
        if self._settings.get('show_only_sfw', False):
            t0 = time.perf_counter()
            threshold = self._nsfw_levels.get('R', 0)
            items = [item for item in items if not item.get('preview_nsfw_level') or item.get('preview_nsfw_level') < threshold]
            sfw_duration = time.perf_counter() - t0
        else:
            sfw_duration = 0
        favorites_duration = 0
        if criteria.favorites_only:
            t0 = time.perf_counter()
            items = [item for item in items if item.get('favorite', False)]
            favorites_duration = time.perf_counter() - t0
        folder_duration = 0
        folder = criteria.folder
        folder_include = criteria.folder_include or []
        folder_exclude = criteria.folder_exclude or []
        options = criteria.search_options or {}
        recursive = bool(options.get('recursive', True))
        if folder_exclude:
            t0 = time.perf_counter()
            for exclude_folder in folder_exclude:
                if exclude_folder:
                    if not exclude_folder.endswith('/'):
                        exclude_prefix = f'{exclude_folder}/'
                    else:
                        exclude_prefix = exclude_folder
                    items = [item for item in items if item.get('folder') != exclude_folder and (not item.get('folder', '').startswith(exclude_prefix))]
            folder_duration = time.perf_counter() - t0
        if folder is not None:
            t0 = time.perf_counter()
            if recursive:
                if folder:
                    folder_with_sep = f'{folder}/'
                    items = [item for item in items if item.get('folder') == folder or item.get('folder', '').startswith(folder_with_sep)]
            else:
                items = [item for item in items if item.get('folder') == folder]
            folder_duration = time.perf_counter() - t0 + folder_duration
        if folder_include:
            t0 = time.perf_counter()
            matched_items = []
            for include_folder in folder_include:
                if include_folder:
                    if recursive:
                        if not include_folder.endswith('/'):
                            folder_prefix = f'{include_folder}/'
                        else:
                            folder_prefix = include_folder
                        folder_items = [item for item in items if item.get('folder') == include_folder or item.get('folder', '').startswith(folder_prefix)]
                    else:
                        folder_items = [item for item in items if item.get('folder') == include_folder]
                    matched_items.extend(folder_items)
            seen = set()
            items = []
            for item in matched_items:
                item_id = item.get('sha256') or item.get('id')
                if item_id is not None:
                    identifier = item_id
                else:
                    identifier = tuple(sorted(((k, str(v)) for k, v in item.items())))
                if identifier not in seen:
                    seen.add(identifier)
                    items.append(item)
            folder_duration = time.perf_counter() - t0 + folder_duration
        elif folder is not None:
            t0 = time.perf_counter()
            if recursive:
                if folder:
                    if not folder.endswith('/'):
                        folder_prefix = f'{folder}/'
                    else:
                        folder_prefix = folder
                    items = [item for item in items if item.get('folder') == folder or item.get('folder', '').startswith(folder_prefix)]
            else:
                items = [item for item in items if item.get('folder') == folder]
            folder_duration = time.perf_counter() - t0 + folder_duration
        base_models_duration = 0
        base_models = criteria.base_models or []
        if base_models:
            t0 = time.perf_counter()
            base_model_set = set(base_models)
            items = [item for item in items if item.get('base_model') in base_model_set]
            base_models_duration = time.perf_counter() - t0
        tags_duration = 0
        tag_filters = criteria.tags or {}
        if tag_filters:
            t0 = time.perf_counter()
            include_tags = set()
            exclude_tags = set()
            if isinstance(tag_filters, dict):
                for tag, state in tag_filters.items():
                    if not tag:
                        continue
                    normalized = tag.strip().lower()
                    if state == 'exclude':
                        exclude_tags.add(normalized)
                    else:
                        include_tags.add(normalized)
            else:
                include_tags = {tag.strip().lower() for tag in cast(Iterable[Any], tag_filters) if tag}
            if include_tags:
                tag_logic = criteria.tag_logic.lower() if criteria.tag_logic else 'any'

                def matches_include(item_tags):
                    if not item_tags and '__no_tags__' in include_tags:
                        return True
                    if tag_logic == 'all':
                        non_special_tags = include_tags - {'__no_tags__'}
                        if '__no_tags__' in include_tags:
                            if not item_tags:
                                return True
                            if non_special_tags:
                                normalized_item_tags = {t.strip().lower() for t in item_tags or [] if isinstance(t, str)}
                                return all((tag in normalized_item_tags for tag in non_special_tags))
                            return True
                        normalized_item_tags = {t.strip().lower() for t in item_tags or [] if isinstance(t, str)}
                        return all((tag in normalized_item_tags for tag in non_special_tags))
                    else:
                        normalized_item_tags = {t.strip().lower() for t in item_tags or [] if isinstance(t, str)}
                        return bool(normalized_item_tags & include_tags)
                items = [item for item in items if matches_include(item.get('tags'))]
            if exclude_tags:

                def matches_exclude(item_tags):
                    if not item_tags and '__no_tags__' in exclude_tags:
                        return True
                    normalized_item_tags = {t.strip().lower() for t in item_tags or [] if isinstance(t, str)}
                    return bool(normalized_item_tags & exclude_tags)
                items = [item for item in items if not matches_exclude(item.get('tags'))]
            tags_duration = time.perf_counter() - t0
        model_types_duration = 0
        model_types = criteria.model_types or []
        if model_types:
            t0 = time.perf_counter()
            normalized_model_types = {model_type for model_type in (normalize_sub_type(value) for value in model_types) if model_type}
            if normalized_model_types:
                items = [item for item in items if normalize_sub_type(resolve_sub_type(item)) in normalized_model_types]
            model_types_duration = time.perf_counter() - t0
        auto_tags_duration = 0
        auto_tag_filters = criteria.auto_tags or {}
        if auto_tag_filters:
            t0 = time.perf_counter()
            include_at = set()
            exclude_at = set()
            for tag, state in auto_tag_filters.items():
                if not tag:
                    continue
                if state == 'exclude':
                    exclude_at.add(tag)
                else:
                    include_at.add(tag)
            if include_at:
                items = [item for item in items if any((tag in include_at for tag in item.get('auto_tags') or []))]
            if exclude_at:
                items = [item for item in items if not any((tag in exclude_at for tag in item.get('auto_tags') or []))]
            auto_tags_duration = time.perf_counter() - t0
        duration = time.perf_counter() - overall_start
        if duration > 0.1:
            logger.debug('ModelFilterSet.apply took %.3fs (sfw: %.3fs, fav: %.3fs, folder: %.3fs, base: %.3fs, tags: %.3fs, types: %.3fs, auto_tags: %.3fs). Count: %d -> %d', duration, sfw_duration, favorites_duration, folder_duration, base_models_duration, tags_duration, model_types_duration, auto_tags_duration, initial_count, len(items))
        return items

class LiteralPreviewFilters:

    async def _apply_specific_filters(self, data: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """Apply LoRA-specific filters"""
        first_letter = kwargs.get('first_letter')
        if first_letter:
            data = self._filter_by_first_letter(data, first_letter)
        name_pattern_include = kwargs.get('name_pattern_include', [])
        name_pattern_exclude = kwargs.get('name_pattern_exclude', [])
        name_pattern_use_regex = kwargs.get('name_pattern_use_regex', False)
        if name_pattern_include or name_pattern_exclude:
            import re

            def matches_pattern(name, pattern, use_regex):
                """Check if name matches pattern (regex or substring)"""
                if not name:
                    return False
                if use_regex:
                    try:
                        return bool(re.search(pattern, name, re.IGNORECASE))
                    except re.error:
                        return pattern.lower() in name.lower()
                else:
                    return pattern.lower() in name.lower()

            def matches_any_pattern(name, patterns, use_regex):
                """Check if name matches any of the patterns"""
                if not patterns:
                    return True
                return any((matches_pattern(name, p, use_regex) for p in patterns))
            filtered = []
            for lora in data:
                model_name = lora.get('model_name', '')
                file_name = lora.get('file_name', '')
                names_to_check = [n for n in [model_name, file_name] if n]
                excluded = False
                if name_pattern_exclude:
                    for name in names_to_check:
                        if matches_any_pattern(name, name_pattern_exclude, name_pattern_use_regex):
                            excluded = True
                            break
                if excluded:
                    continue
                if name_pattern_include:
                    included = False
                    for name in names_to_check:
                        if matches_any_pattern(name, name_pattern_include, name_pattern_use_regex):
                            included = True
                            break
                    if not included:
                        continue
                filtered.append(lora)
            data = filtered
        return data

    async def _apply_credit_required_filter(self, data: List[Dict[str, Any]], credit_required: bool) -> List[Dict[str, Any]]:
        """Apply credit required filtering based on license_flags.

        Args:
            data: List of model data items
            credit_required:
                - True: Return items where credit is required (allowNoCredit=False)
                - False: Return items where credit is not required (allowNoCredit=True)
        """
        filtered_data = []
        for item in data:
            license_flags = item.get('license_flags', 127)
            allow_no_credit = bool(license_flags & 1 << 0)
            if credit_required:
                if not allow_no_credit:
                    filtered_data.append(item)
            elif allow_no_credit:
                filtered_data.append(item)
        return filtered_data

    async def _apply_allow_selling_filter(self, data: List[Dict[str, Any]], allow_selling: bool) -> List[Dict[str, Any]]:
        """Apply allow selling generated content filtering based on license_flags.

        Args:
            data: List of model data items
            allow_selling:
                - True: Return items where selling generated content is allowed (allowCommercialUse contains Image)
                - False: Return items where selling generated content is not allowed (allowCommercialUse does not contain Image)
        """
        filtered_data = []
        for item in data:
            license_flags = item.get('license_flags', 127)
            has_image_permission = bool(license_flags & 1 << 1)
            if allow_selling:
                if has_image_permission:
                    filtered_data.append(item)
            elif not has_image_permission:
                filtered_data.append(item)
        return filtered_data
