"""Native filter/rank composition over caller-owned catalogue rows.
Relative names must already have a genuine selected scanner/root provenance.
This module acquires no model roots, catalogue, authenticated state or storage.
"""
from __future__ import annotations
import os, re
from typing import Any, Dict, List
from .preview_query import FilterCriteria, ModelFilterSet
from .auto_tag_service import extract_auto_tags

class BaseModelService:
    @staticmethod
    def _remove_model_extension(path: str) -> str:
        """Remove model file extension (.safetensors, .ckpt, .pt, .bin) for cleaner matching."""
        return re.sub(r"\.(safetensors|ckpt|pt|bin)$", "", path, flags=re.IGNORECASE)

    @staticmethod
    def _parse_search_tokens(search_term: str) -> tuple[List[str], List[str]]:
        """Split a search string into include and exclude tokens."""
        include_terms: List[str] = []
        exclude_terms: List[str] = []

        for raw_term in search_term.split():
            term = raw_term.strip()
            if not term:
                continue

            if term.startswith("-") and len(term) > 1:
                exclude_terms.append(term[1:].lower())
            else:
                include_terms.append(term.lower())

        return include_terms, exclude_terms

    @staticmethod
    def _relative_path_matches_tokens(
        path_lower: str, include_terms: List[str], exclude_terms: List[str]
    ) -> bool:
        """Determine whether a relative path string satisfies include/exclude tokens.

        Matches against the path without extension to avoid matching .safetensors
        when searching for 's'.
        """
        # Use path without extension for matching
        path_for_matching = BaseModelService._remove_model_extension(path_lower)

        if any(term and term in path_for_matching for term in exclude_terms):
            return False

        for term in include_terms:
            if term and term not in path_for_matching:
                return False

        return True

    @staticmethod
    def _relative_path_sort_key(relative_path: str, include_terms: List[str]) -> tuple[int, int, int, str]:
        """Sort paths by how well they satisfy the include tokens.

        Sorts based on path without extension for consistent ordering.
        """
        # Use path without extension for sorting
        path_for_sorting = BaseModelService._remove_model_extension(
            relative_path.lower()
        )
        prefix_hits = sum(
            1 for term in include_terms if term and path_for_sorting.startswith(term)
        )
        match_positions = [
            path_for_sorting.find(term)
            for term in include_terms
            if term and term in path_for_sorting
        ]
        first_match_index = min(match_positions) if match_positions else 0

        return (
            -prefix_hits,
            first_match_index,
            len(path_for_sorting),
            path_for_sorting,
        )

    @staticmethod
    def _relative_path_folder_group_sort_key(
        relative_path: str, include_terms: List[str]
    ) -> tuple:
        """Group paths by folder, then sort by relevance within each group.

        Folders are ordered alphabetically (case-insensitive) by their full
        folder path, with root-level files (empty folder) first. Within a
        folder, paths keep the relevance ordering of
        ``_relative_path_sort_key``. This keeps same-folder entries together
        in the autocomplete dropdown instead of interleaving them by filename.
        """
        path_for_sorting = BaseModelService._remove_model_extension(
            relative_path.lower()
        )
        folder = path_for_sorting.rpartition(os.sep)[0]

        return (folder,) + BaseModelService._relative_path_sort_key(
            relative_path, include_terms
        )

    async def _apply_credit_required_filter(
        self, data: List[Dict[str, Any]], credit_required: bool
    ) -> List[Dict[str, Any]]:
        """Apply credit required filtering based on license_flags.

        Args:
            data: List of model data items
            credit_required:
                - True: Return items where credit is required (allowNoCredit=False)
                - False: Return items where credit is not required (allowNoCredit=True)
        """
        filtered_data = []
        for item in data:
            license_flags = item.get(
                "license_flags", 127
            )  # Default to all permissions enabled

            # Bit 0 represents allowNoCredit (1 = no credit required, 0 = credit required)
            allow_no_credit = bool(license_flags & (1 << 0))

            # If credit_required is True, we want items where allowNoCredit is False (credit required)
            # If credit_required is False, we want items where allowNoCredit is True (no credit required)
            if credit_required:
                if not allow_no_credit:  # Credit is required
                    filtered_data.append(item)
            else:
                if allow_no_credit:  # Credit is not required
                    filtered_data.append(item)

        return filtered_data

    async def _apply_allow_selling_filter(
        self, data: List[Dict[str, Any]], allow_selling: bool
    ) -> List[Dict[str, Any]]:
        """Apply allow selling generated content filtering based on license_flags.

        Args:
            data: List of model data items
            allow_selling:
                - True: Return items where selling generated content is allowed (allowCommercialUse contains Image)
                - False: Return items where selling generated content is not allowed (allowCommercialUse does not contain Image)
        """
        filtered_data = []
        for item in data:
            license_flags = item.get(
                "license_flags", 127
            )  # Default to all permissions enabled

            # Bits 1-4 represent commercial use permissions
            # Bit 1 specifically represents Image permission (allowCommercialUse contains Image)
            has_image_permission = bool(license_flags & (1 << 1))

            # If allow_selling is True, we want items where Image permission is granted
            # If allow_selling is False, we want items where Image permission is not granted
            if allow_selling:
                if has_image_permission:  # Selling generated content is allowed
                    filtered_data.append(item)
            else:
                if not has_image_permission:  # Selling generated content is not allowed
                    filtered_data.append(item)

        return filtered_data

async def search_selected_catalogue(rows, selected_relative_paths, preferences, plan):
    # Explicit correspondence; never infer a native root from a logical name.
    if len(rows) != len(selected_relative_paths):
        raise ValueError('Selected row/path correspondence required')
    if len(rows) > 2048:
        raise ValueError('Catalogue exceeds admitted 2048-row profile')
    import json
    if len(json.dumps([rows, selected_relative_paths, preferences, plan], ensure_ascii=False).encode('utf-8')) > 1_048_576:
        raise ValueError('Catalogue/query exceeds admitted 1MiB local projection')
    for row, path in zip(rows, selected_relative_paths):
        if type(row) is not dict or type(path) is not str:
            raise TypeError('Selected row and native relative string required')
    service = BaseModelService()
    include_terms, exclude_terms = service._parse_search_tokens(plan['search'])
    # Reuse the prior catalogue's 16M comparison-work profile. This precedes
    # auto-tag mutation, native filtering, sorting and output allocation.
    terms = include_terms + exclude_terms
    criteria = (plan['base_models'], plan['model_types'], plan['tags'], plan['auto_tags'])
    fanout = 1 + len(terms) + sum(len(value) for value in criteria)
    logical_chars = sum(len(path) for path in selected_relative_paths)
    logical_chars += sum(len(json.dumps(row, ensure_ascii=False)) for row in rows)
    if logical_chars * fanout > 16_000_000:
        raise ValueError('Catalogue/filter comparison-work projection exceeds 16M')
    data = rows
    has_filters = any([plan['apply_filters'], plan['folder'] is not None,
        plan['base_models'], plan['model_types'], plan['tags'], plan['auto_tags'],
        plan['credit_required'] is not None, plan['allow_selling_generated_content'] is not None])
    if has_filters:
        if plan['auto_tags']:
            for item in data:
                if not item.get('auto_tags'):
                    item['auto_tags'] = extract_auto_tags(item)
        data = ModelFilterSet(preferences).apply(data, FilterCriteria(folder=plan['folder'],
            base_models=plan['base_models'], model_types=plan['model_types'], tags=plan['tags'],
            auto_tags=plan['auto_tags'], search_options={'recursive':plan['recursive']}, tag_logic=plan['tag_logic']))
        if plan['credit_required'] is not None:
            data = await service._apply_credit_required_filter(data, plan['credit_required'])
        if plan['allow_selling_generated_content'] is not None:
            data = await service._apply_allow_selling_filter(data, plan['allow_selling_generated_content'])
    # Identity correspondence preserves duplicate rows/names and scanner ordering.
    surviving = {id(row) for row in data}
    matching = [path for row, path in zip(rows, selected_relative_paths)
        if id(row) in surviving and row.get('file_path', '') and path
        and service._relative_path_matches_tokens(path.lower(), include_terms, exclude_terms)]
    matching.sort(key=lambda relative: service._relative_path_folder_group_sort_key(relative, include_terms))
    start = min(plan['offset'], len(matching))
    end = min(start + plan['limit'], len(matching))
    return matching[start:end]
