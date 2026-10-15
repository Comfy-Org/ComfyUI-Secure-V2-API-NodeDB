"""Exact pinned Wan cache state lifetimes; no tensor/model/SDK imports.

These mutable objects remain guest-local. No serializer, global cache, LOS
model payload, cap, device mapping, RNG normalization or reset rule is added.
"""

class TeaCacheState:
    def __init__(self, cache_device='cpu'):
        self.cache_device = cache_device
        self.states = {}
        self._next_pred_id = 0
    
    def new_prediction(self, cache_device='cpu'):
        """Create new prediction state and return its ID"""
        self.cache_device = cache_device
        pred_id = self._next_pred_id
        self._next_pred_id += 1
        self.states[pred_id] = {
            'previous_residual': None,
            'accumulated_rel_l1_distance': 0,
            'previous_modulated_input': None,
            'skipped_steps': [],
        }
        return pred_id
    
    def update(self, pred_id, **kwargs):
        """Update state for specific prediction"""
        if pred_id not in self.states:
            return None
        for key, value in kwargs.items():
            self.states[pred_id][key] = value
    
    def get(self, pred_id):
        return self.states.get(pred_id, {})
    
    def clear_all(self):
        self.states = {}
        self._next_pred_id = 0


class MagCacheState:
    def __init__(self, cache_device='cpu'):
        self.cache_device = cache_device
        self.states = {}
        self._next_pred_id = 0
    
    def new_prediction(self, cache_device='cpu'):
        """Create new prediction state and return its ID"""
        self.cache_device = cache_device
        pred_id = self._next_pred_id
        self._next_pred_id += 1
        self.states[pred_id] = {
            'residual_cache': None,
            'accumulated_ratio': 1.0,
            'accumulated_steps': 0,
            'accumulated_err': 0,
            'skipped_steps': [],
        }
        return pred_id
    
    def update(self, pred_id, **kwargs):
        """Update state for specific prediction"""
        if pred_id not in self.states:
            return None
        for key, value in kwargs.items():
            self.states[pred_id][key] = value
    
    def get(self, pred_id):
        return self.states.get(pred_id, {})
    
    def clear_all(self):
        self.states = {}
        self._next_pred_id = 0


class EasyCacheState:
    def __init__(self, cache_device='cpu'):
        self.cache_device = cache_device
        self.states = {}
        self._next_pred_id = 0

    def new_prediction(self, cache_device='cpu'):
        """Create a new prediction state and return its ID."""
        self.cache_device = cache_device
        pred_id = self._next_pred_id
        self._next_pred_id += 1
        self.states[pred_id] = {
            'previous_raw_input': None,
            'previous_raw_output': None,
            'cache': None,
            'accumulated_error': 0.0,
            'skipped_steps': [],
            'cache_ovi': None,
        }
        return pred_id

    def update(self, pred_id, **kwargs):
        """Update state for a specific prediction."""
        if pred_id not in self.states:
            return None
        for key, value in kwargs.items():
            self.states[pred_id][key] = value

    def get(self, pred_id):
        return self.states.get(pred_id, {})

    def clear_all(self):
        self.states = {}
        self._next_pred_id = 0

