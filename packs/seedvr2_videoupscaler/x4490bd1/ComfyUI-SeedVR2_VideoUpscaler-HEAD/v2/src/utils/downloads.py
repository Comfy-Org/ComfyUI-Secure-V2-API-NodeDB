"""
Downloads utility module for SeedVR2
Handles model and VAE downloads from HuggingFace repositories with integrity validation
"""

import os
import hashlib
import json
from typing import Optional
from tqdm import tqdm
import time

from .model_registry import MODEL_REGISTRY, DEFAULT_VAE
from .constants import (
    get_base_cache_dir,
    get_all_model_paths,
    find_model_file,
    get_validation_cache_path,
    HUGGINGFACE_BASE_URL,
    DOWNLOAD_CHUNK_SIZE,
    DOWNLOAD_MAX_RETRIES,
    DOWNLOAD_RETRY_DELAY
)

def load_validation_cache(cache_dir: Optional[str] = None):
    """
    Load validation cache.
    
    Args:
        cache_dir: Optional directory containing cache file. If None, uses default.
    """
    cache_path = get_validation_cache_path(cache_dir)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_validation_cache(cache, cache_dir: Optional[str] = None):
    """
    Save validation cache.
    
    Args:
        cache: Cache dictionary to save
        cache_dir: Optional directory for cache file. If None, uses default.
    """
    cache_path = get_validation_cache_path(cache_dir)
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(cache, f, indent=2)
    except:
        pass


def is_file_validated_cached(filepath: str, cache_dir: Optional[str] = None) -> bool:
    """
    Check if file is validated using cache (fast).
    
    Args:
        filepath: Path to file to check
        cache_dir: Optional directory containing cache file. If None, uses default.
    """
    if not os.path.exists(filepath):
        return False
    
    cache = load_validation_cache(cache_dir)
    filename = os.path.basename(filepath)
    
    if filename in cache:
        cached = cache[filename]
        # Check if file hasn't changed since validation
        if (cached.get('size') == os.path.getsize(filepath) and 
            abs(cached.get('mtime', 0) - os.path.getmtime(filepath)) < 2):
            return True
    
    return False


def validate_file(filepath: str, expected_hash: Optional[str] = None, cache_dir: Optional[str] = None) -> bool:
    """
    File validation with hash check and cache update.
    
    Args:
        filepath: Path to file to validate
        expected_hash: Optional SHA256 hash to verify against
        cache_dir: Optional directory for cache file. If None, uses default.
    """
    if not os.path.exists(filepath):
        return False
    
    file_size = os.path.getsize(filepath)
    if file_size == 0:
        return False
    
    # Quick safetensors header check
    if filepath.endswith('.safetensors'):
        try:
            with open(filepath, 'rb') as f:
                header_size = int.from_bytes(f.read(8), 'little')
                if header_size <= 0 or header_size > file_size:
                    return False
        except:
            return False
    
    # Only calculate hash if we have an expected hash to compare
    if expected_hash:
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(DOWNLOAD_CHUNK_SIZE):
                sha256.update(chunk)
        actual_hash = sha256.hexdigest()
        
        if actual_hash != expected_hash:
            return False
        
        # Update cache with validated info
        cache = load_validation_cache(cache_dir)
        cache[os.path.basename(filepath)] = {
            "size": os.path.getsize(filepath),
            "mtime": os.path.getmtime(filepath),
            "hash": expected_hash
        }
        save_validation_cache(cache, cache_dir)
    
    return True


def download_with_resume(url: str, filepath: str, debug=None) -> bool:
    """Secure Nodes V2: a guest never downloads; checkpoints are declared, brokered weights."""
    raise RuntimeError("seedvr2_videoupscaler: Secure Nodes V2 never downloads models at run time")


def download_weight(dit_model: str, vae_model: str, model_dir: Optional[str] = None, debug=None) -> bool:
    """Secure Nodes V2: a guest never downloads.

    The secure node has already fetched both checkpoints as declared, sha256-pinned brokered weights
    (src/_sn_weights.py). This only checks that they were supplied, in place of the original
    find/validate/download steps.
    """
    from .._sn_weights import require_supplied
    require_supplied(dit_model, vae_model)
    return True
