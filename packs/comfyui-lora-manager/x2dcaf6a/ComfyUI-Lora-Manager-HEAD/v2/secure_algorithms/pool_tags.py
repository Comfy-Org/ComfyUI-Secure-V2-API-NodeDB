"""Literal pinned tag block; pool criteria only needs tags and default OR.

Other general model query operations are not represented here.
"""
import time
from typing import Any, Iterable, cast
from dataclasses import dataclass

@dataclass(frozen=True)
class FilterCriteria:
    tags: dict
    tag_logic: str = "any"

class PoolTagFilters:

    def apply(self, items, criteria):
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
        return items
