"""Pinned metadata filename rules over explicit workflow data.

Clock identity and execution ancestry are not supplied by this pure adapter.
All output names still require the owned output broker's path validation.
"""
from __future__ import annotations

import os
import re
from typing import NoReturn, Optional



def sanitize_folder_name(
    name: str, replacement: str = "_", max_length: Optional[int] = None
) -> str:
    """Sanitize a folder name by removing or replacing invalid characters.

    Args:
        name: The original folder name.
        replacement: The character to use when replacing invalid characters.
        max_length: Optional maximum length for the resulting name. Longer
            names are truncated (and re-trimmed) so that a single untrusted
            value cannot blow past filesystem path limits.

    Returns:
        A sanitized folder name safe to use across common filesystems.
    """

    if not name:
        return ""

    # Replace invalid characters commonly restricted on Windows and POSIX
    invalid_chars_pattern = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars_pattern, replacement, name)

    # Trim whitespace introduced during sanitization
    sanitized = sanitized.strip()

    # Collapse repeated replacement characters to a single instance
    if replacement:
        sanitized = re.sub(f"{re.escape(replacement)}+", replacement, sanitized)
        # Combine stripping to be idempotent:
        # Right side: strip replacement, space, and dot (Windows restriction)
        # Left side: strip replacement and space (leading dots are allowed)
        sanitized = sanitized.rstrip(" ." + replacement).lstrip(" " + replacement)
    else:
        # If no replacement, just strip spaces and dots from right, spaces from left
        sanitized = sanitized.rstrip(" .").lstrip(" ")

    if max_length is not None and max_length > 0 and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
        # Re-trim separators and spaces exposed by the cut so the truncated
        # name stays filesystem-safe.
        if replacement:
            sanitized = sanitized.rstrip(" ." + replacement).lstrip(" " + replacement)
        else:
            sanitized = sanitized.rstrip(" .").lstrip(" ")

    if not sanitized:
        return "unnamed"

    return sanitized


class ImageFilenameFormatter:
    pattern_format = re.compile(r"(%[^%]+%)")

    def _date_now(self) -> NoReturn:
        """Keep clock ownership held at its native position in traversal."""
        raise NotImplementedError('Filename date clock identity remains pending')

    def format_filename(self, filename, metadata_dict):
        """Format filename with metadata values"""
        if not metadata_dict:
            return filename

        result = re.findall(self.pattern_format, filename)
        for segment in result:
            parts = segment.replace("%", "").split(":")
            key = parts[0]

            if key == "seed" and "seed" in metadata_dict:
                seed_value = metadata_dict.get("seed")
                if seed_value is not None:
                    filename = filename.replace(segment, str(seed_value))
                else:
                    # Fallback if seed was not captured by metadata collector
                    filename = filename.replace(segment, "0")
            elif key == "width" and "size" in metadata_dict:
                size = metadata_dict.get("size", "x")
                w = size.split("x")[0] if isinstance(size, str) else size[0]
                filename = filename.replace(segment, str(w))
            elif key == "height" and "size" in metadata_dict:
                size = metadata_dict.get("size", "x")
                h = size.split("x")[1] if isinstance(size, str) else size[1]
                filename = filename.replace(segment, str(h))
            elif key == "pprompt" and "prompt" in metadata_dict:
                prompt = metadata_dict.get("prompt", "").replace("\n", " ")
                prompt = sanitize_folder_name(prompt)
                if len(parts) >= 2:
                    length = int(parts[1])
                    prompt = prompt[:length]
                filename = filename.replace(segment, prompt.strip())
            elif key == "nprompt" and "negative_prompt" in metadata_dict:
                prompt = metadata_dict.get("negative_prompt", "").replace("\n", " ")
                prompt = sanitize_folder_name(prompt)
                if len(parts) >= 2:
                    length = int(parts[1])
                    prompt = prompt[:length]
                filename = filename.replace(segment, prompt.strip())
            elif key == "model":
                model_value = metadata_dict.get("checkpoint")
                if isinstance(model_value, (bytes, os.PathLike)):
                    model_value = str(model_value)

                if not isinstance(model_value, str) or not model_value:
                    model = "model_unavailable"
                else:
                    model = os.path.splitext(os.path.basename(model_value))[0]
                    model = sanitize_folder_name(model)
                if len(parts) >= 2:
                    length = int(parts[1])
                    model = model[:length]
                filename = filename.replace(segment, model)
            elif key == "date":
                now = self._date_now()
                date_table = {
                    "yyyy": f"{now.year:04d}",
                    "yy": f"{now.year % 100:02d}",
                    "MM": f"{now.month:02d}",
                    "dd": f"{now.day:02d}",
                    "hh": f"{now.hour:02d}",
                    "mm": f"{now.minute:02d}",
                    "ss": f"{now.second:02d}",
                }
                if len(parts) >= 2:
                    date_format = parts[1]
                    for k, v in date_table.items():
                        date_format = date_format.replace(k, v)
                    filename = filename.replace(segment, date_format)
                else:
                    date_format = "yyyyMMddhhmmss"
                    for k, v in date_table.items():
                        date_format = date_format.replace(k, v)
                    filename = filename.replace(segment, date_format)

        return filename




def image_filename(filename, metadata=None):
    # The writer owns path confinement. The formatter reaches the held date
    # clock in native segment order, preserving errors in preceding segments.
    return ImageFilenameFormatter().format_filename(filename, metadata)
