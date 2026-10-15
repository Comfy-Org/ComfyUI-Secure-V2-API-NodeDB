"""Pinned source methods; managed scanner/guard supplied by owned service.

No filesystem, provider, cache mutation, model or persistent state authority.
"""
import json
import os
from typing import Any, Dict, List, Optional

class LiteralPoolService:

    @staticmethod
    def get_recommended_strength_from_lora_data(lora_data: Dict[str, Any]) -> Optional[float]:
        """Parse usage_tips JSON and extract recommended model strength."""
        try:
            usage_tips = lora_data.get('usage_tips', '')
            if not usage_tips:
                return None
            tips_data = json.loads(usage_tips)
            return tips_data.get('strength')
        except (json.JSONDecodeError, TypeError, AttributeError):
            return None

    @staticmethod
    def get_recommended_clip_strength_from_lora_data(lora_data: Dict[str, Any]) -> Optional[float]:
        """Parse usage_tips JSON and extract recommended clip strength."""
        try:
            usage_tips = lora_data.get('usage_tips', '')
            if not usage_tips:
                return None
            tips_data = json.loads(usage_tips)
            return tips_data.get('clipStrength')
        except (json.JSONDecodeError, TypeError, AttributeError):
            return None

    async def get_random_loras(self, count: int, model_strength_min: float=0.0, model_strength_max: float=1.0, use_same_clip_strength: bool=True, clip_strength_min: float=0.0, clip_strength_max: float=1.0, locked_loras: Optional[List[Dict[str, Any]]]=None, pool_config: Optional[Dict[str, Any]]=None, count_mode: str='fixed', count_min: int=3, count_max: int=7, use_recommended_strength: bool=False, recommended_strength_scale_min: float=0.5, recommended_strength_scale_max: float=1.0, seed: Optional[int]=None) -> List[Dict[str, Any]]:
        """
        Get random LoRAs with specified strength ranges.

        Args:
            count: Number of LoRAs to select (if count_mode='fixed')
            model_strength_min: Minimum model strength
            model_strength_max: Maximum model strength
            use_same_clip_strength: Whether to use same strength for clip
            clip_strength_min: Minimum clip strength
            clip_strength_max: Maximum clip strength
            locked_loras: List of locked LoRA dicts to preserve
            pool_config: Optional pool config for filtering
            count_mode: How to determine count ('fixed' or 'range')
            count_min: Minimum count for range mode
            count_max: Maximum count for range mode
            use_recommended_strength: Whether to use recommended strength from usage_tips
            recommended_strength_scale_min: Minimum scale factor for recommended strength
            recommended_strength_scale_max: Maximum scale factor for recommended strength
            seed: Optional random seed for reproducible/unique randomization per execution

        Returns:
            List of LoRA dicts with randomized strengths
        """
        import random
        rng = random.Random(seed)
        if locked_loras is None:
            locked_loras = []
        if count_mode == 'fixed':
            target_count = count
        else:
            target_count = rng.randint(count_min, count_max)
        cache = await self.scanner.get_cached_data(force_refresh=False)
        available_loras = cache.raw_data if cache else []
        if pool_config:
            available_loras = await self._apply_pool_filters(available_loras, pool_config)
        locked_count = len(locked_loras)
        slots_needed = target_count - locked_count
        if slots_needed < 0:
            slots_needed = 0
            locked_loras = locked_loras[:target_count]
        locked_names = {os.path.basename(lora['name']) if '/' in str(lora.get('name', '')) else lora['name'] for lora in locked_loras}
        available_pool = [l for l in available_loras if l['file_name'] not in locked_names]
        if slots_needed > len(available_pool):
            slots_needed = len(available_pool)
        selected = []
        if slots_needed > 0:
            selected = rng.sample(available_pool, slots_needed)
        result_loras = []
        for lora in selected:
            if use_recommended_strength:
                recommended_strength = self.get_recommended_strength_from_lora_data(lora)
                if recommended_strength is not None:
                    scale = rng.uniform(recommended_strength_scale_min, recommended_strength_scale_max)
                    model_str = round(recommended_strength * scale, 2)
                else:
                    model_str = round(rng.uniform(model_strength_min, model_strength_max), 2)
            else:
                model_str = round(rng.uniform(model_strength_min, model_strength_max), 2)
            if use_same_clip_strength:
                clip_str = model_str
            elif use_recommended_strength:
                recommended_clip_strength = self.get_recommended_clip_strength_from_lora_data(lora)
                if recommended_clip_strength is not None:
                    scale = rng.uniform(recommended_strength_scale_min, recommended_strength_scale_max)
                    clip_str = round(recommended_clip_strength * scale, 2)
                else:
                    clip_str = round(rng.uniform(clip_strength_min, clip_strength_max), 2)
            else:
                clip_str = round(rng.uniform(clip_strength_min, clip_strength_max), 2)
            result_loras.append({'name': f"{lora['folder']}/{lora['file_name']}" if lora.get('folder') else lora['file_name'], 'strength': model_str, 'clipStrength': clip_str, 'active': True, 'expanded': abs(model_str - clip_str) > 0.001, 'locked': False})
        result_loras.extend(locked_loras)
        return result_loras

    async def _apply_pool_filters(self, available_loras: List[Dict[str, Any]], pool_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Apply pool_config filters to available LoRAs.

        Args:
            available_loras: List of all LoRA dicts
            pool_config: Dict with filter settings from LoRA Pool node

        Returns:
            Filtered list of LoRA dicts
        """
        from .pool_tags import FilterCriteria
        filter_section = pool_config
        selected_base_models = filter_section.get('baseModels', [])
        tags_dict = filter_section.get('tags', {})
        include_tags = tags_dict.get('include', [])
        exclude_tags = tags_dict.get('exclude', [])
        folders_dict = filter_section.get('folders', {})
        include_folders = folders_dict.get('include', [])
        exclude_folders = folders_dict.get('exclude', [])
        license_dict = filter_section.get('license', {})
        no_credit_required = license_dict.get('noCreditRequired', False)
        allow_selling = license_dict.get('allowSelling', False)
        tag_filters = {}
        for tag in include_tags:
            tag_filters[tag] = 'include'
        for tag in exclude_tags:
            tag_filters[tag] = 'exclude'
        if include_folders or exclude_folders:
            filtered = []
            for lora in available_loras:
                folder = lora.get('folder', '')
                excluded = False
                for exclude_folder in exclude_folders:
                    if folder.startswith(exclude_folder):
                        excluded = True
                        break
                if excluded:
                    continue
                if include_folders:
                    included = False
                    for include_folder in include_folders:
                        if folder.startswith(include_folder):
                            included = True
                            break
                    if not included:
                        continue
                filtered.append(lora)
            available_loras = filtered
        if selected_base_models:
            available_loras = [lora for lora in available_loras if lora.get('base_model') in selected_base_models]
        if tag_filters:
            criteria = FilterCriteria(tags=tag_filters)
            available_loras = self.filter_set.apply(available_loras, criteria)
        if no_credit_required:
            available_loras = [lora for lora in available_loras if bool(lora.get('license_flags', 127) & 1 << 0)]
        if allow_selling:
            available_loras = [lora for lora in available_loras if bool(lora.get('license_flags', 127) & 1 << 1)]
        name_patterns = filter_section.get('namePatterns', {})
        include_patterns = name_patterns.get('include', [])
        exclude_patterns = name_patterns.get('exclude', [])
        use_regex = name_patterns.get('useRegex', False)
        if include_patterns or exclude_patterns:
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
            for lora in available_loras:
                model_name = lora.get('model_name', '')
                file_name = lora.get('file_name', '')
                names_to_check = [n for n in [model_name, file_name] if n]
                excluded = False
                if exclude_patterns:
                    for name in names_to_check:
                        if matches_any_pattern(name, exclude_patterns, use_regex):
                            excluded = True
                            break
                if excluded:
                    continue
                if include_patterns:
                    included = False
                    for name in names_to_check:
                        if matches_any_pattern(name, include_patterns, use_regex):
                            included = True
                            break
                    if not included:
                        continue
                filtered.append(lora)
            available_loras = filtered
        return available_loras

    async def get_cycler_list(self, pool_config: Optional[Dict[str, Any]]=None, sort_by: str='filename') -> List[Dict[str, Any]]:
        """
        Get filtered and sorted LoRA list for cycling.

        Args:
            pool_config: Optional pool config for filtering (filters dict)
            sort_by: Sort field - 'filename' or 'model_name'

        Returns:
            List of LoRA dicts with file_name and model_name
        """
        cache = await self.scanner.get_cached_data(force_refresh=False)
        available_loras = cache.raw_data if cache else []
        if pool_config:
            available_loras = await self._apply_pool_filters(available_loras, pool_config)
        if sort_by == 'model_name':
            available_loras = sorted(available_loras, key=lambda x: ((x.get('model_name') or x.get('file_name', '')).lower(), x.get('file_path', '').lower()))
        else:
            available_loras = sorted(available_loras, key=lambda x: (x.get('file_name', '').lower(), x.get('file_path', '').lower()))
        result = []
        for lora in available_loras:
            entry = {'file_name': f"{lora['folder']}/{lora['file_name']}" if lora.get('folder') else lora['file_name'], 'model_name': lora.get('model_name', lora['file_name']), 'folder': lora.get('folder', '')}
            usage_tips = lora.get('usage_tips')
            if usage_tips:
                entry['usage_tips'] = usage_tips
            result.append(entry)
        return result
