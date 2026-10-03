"""Immutable layouts and bounded custom-layout decoding for Secure Nodes V2.

Built-ins are compiled into the module, so guest execution never opens a pack
path. User layouts live in the frontend's per-user ``comfy.storage``. When a
user selects one, the frontend serializes the validated layout into the
existing ``layout_preset`` widget value; the workflow therefore remains
self-contained and execution never depends on mutable shared server state.
"""

import json
import math

from ..utils.geometry import polygon_centroid
from .builtin_layouts import BUILTIN_LAYOUTS

_BUILTIN_PRESETS = BUILTIN_LAYOUTS
CUSTOM_LAYOUT_PREFIX = "__panelcomposer_v2__:"
MAX_CUSTOM_LAYOUT_BYTES = 128 * 1024
MAX_PANELS = 64
MAX_POINTS_PER_PANEL = 64


def _validate_presets(raw_presets, source_label):
    """Filters `raw_presets` down to entries with a usable 'category'/
    'label'/'panels' shape, warning and skipping anything else instead of
    letting it through. `_rebuild()` runs unconditionally at import, so one
    malformed sealed entry must not take down the whole node pack."""
    valid = {}
    for name, data in raw_presets.items():
        if (
            isinstance(data, dict)
            and isinstance(data.get("category"), str)
            and isinstance(data.get("label"), str)
            and isinstance(data.get("panels"), list)
        ):
            valid[name] = data
        else:
            print(
                f"[ComfyUI-PanelComposer] WARNING: skipping malformed preset {name!r} in "
                f"{source_label} (needs string 'category'/'label' and a list "
                f"'panels') — fix or remove this entry to restore it."
            )
    return valid


def _rebuild():
    """Build the immutable backend lookup tables from sealed presets."""
    global _PRESETS, LAYOUT_NAMES, LAYOUT_CHOICES, LAYOUT_CHOICE_TO_NAME, READING_GROUPS
    # `is_builtin` distinguishes sealed presets from embedded custom values.
    _PRESETS = {
        name: {**data, "is_builtin": True}
        for name, data in _validate_presets(_BUILTIN_PRESETS, "bundled layouts").items()
    }
    LAYOUT_NAMES = list(_PRESETS.keys())
    # A flat dropdown of built-in + user preset keys gets unwieldy, and
    # ComfyUI's combo widget has no native grouping — so the dropdown shown
    # to the user is "Category / Label" strings (grouped by construction:
    # same-category entries share a prefix and sit together in list order)
    # instead of raw keys, with LAYOUT_CHOICE_TO_NAME mapping the selected
    # choice back to the real preset key.
    LAYOUT_CHOICES = [f"{data['category']} / {data['label']}" for data in _PRESETS.values()]
    LAYOUT_CHOICE_TO_NAME = {
        f"{data['category']} / {data['label']}": name for name, data in _PRESETS.items()
    }
    # An embedded custom preset may omit reading_groups. In that case,
    # apply_reading_order uses literal panel-array order.
    READING_GROUPS = {name: data.get("reading_groups") for name, data in _PRESETS.items()}


_rebuild()


def _validate_custom_layout(data):
    if not isinstance(data, dict):
        raise ValueError("custom layout payload must be an object")
    category = data.get("category")
    label = data.get("label")
    panels = data.get("panels")
    reading_groups = data.get("reading_groups")
    if not isinstance(category, str) or not category.strip() or len(category) > 80:
        raise ValueError("custom layout category must contain 1-80 characters")
    if not isinstance(label, str) or not label.strip() or len(label) > 80:
        raise ValueError("custom layout label must contain 1-80 characters")
    if not isinstance(panels, list) or not 1 <= len(panels) <= MAX_PANELS:
        raise ValueError(f"custom layout must contain 1-{MAX_PANELS} panels")
    normalized = []
    for polygon in panels:
        if not isinstance(polygon, list) or not 3 <= len(polygon) <= MAX_POINTS_PER_PANEL:
            raise ValueError(f"every panel needs 3-{MAX_POINTS_PER_PANEL} points")
        normalized_polygon = []
        for point in polygon:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or not all(
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                    and 0.0 <= value <= 1.0
                    for value in point
                )
            ):
                raise ValueError("every custom-layout point must be a finite [x, y] pair in [0, 1]")
            normalized_polygon.append([float(point[0]), float(point[1])])
        normalized.append(normalized_polygon)
    if reading_groups is not None:
        _validate_reading_groups(reading_groups, len(normalized))
        ids = []

        def collect(group):
            if isinstance(group, int):
                ids.append(group)
            else:
                for child in group:
                    collect(child)

        collect(reading_groups)
        if sorted(ids) != list(range(len(normalized))):
            raise ValueError("reading_groups must reference every panel exactly once")
    return {
        "category": category.strip(),
        "label": label.strip(),
        "panels": normalized,
        "reading_groups": reading_groups,
        "is_builtin": False,
    }


def decode_layout_choice(choice):
    """Resolve a built-in display choice or a bounded embedded custom layout."""
    if not isinstance(choice, str):
        raise ValueError("layout_preset must be a string")
    if choice.startswith(CUSTOM_LAYOUT_PREFIX):
        payload = choice[len(CUSTOM_LAYOUT_PREFIX):]
        if len(payload.encode("utf-8")) > MAX_CUSTOM_LAYOUT_BYTES:
            raise ValueError("custom layout payload exceeds 128 KiB")
        try:
            return _validate_custom_layout(json.loads(payload))
        except json.JSONDecodeError as exc:
            raise ValueError(f"custom layout payload is not valid JSON: {exc}") from exc
    name = LAYOUT_CHOICE_TO_NAME.get(choice, choice)
    if name not in _PRESETS:
        raise ValueError(f"unknown layout preset {choice!r}")
    return _PRESETS[name]


def get_layout(preset_choice):
    polygons = decode_layout_choice(preset_choice)["panels"]
    return [
        {"id": i, "order": i, "polygon": [list(point) for point in polygon]}
        for i, polygon in enumerate(polygons)
    ]


def _group_centroid(group, centroids):
    """Average centroid of every panel id under `group` (recursively)."""
    if isinstance(group, int):
        return centroids[group]
    points = [_group_centroid(g, centroids) for g in group]
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


def _ordered_ids(group, centroids, reading_order):
    """Flattens `group` into a list of panel ids in reading order, sorting at
    each nesting level by whichever axis (X or Y) has more spread among that
    level's sub-groups — Y (rows, top-to-bottom) is never reversed by
    reading_order; X (left-right within a row) is reversed for
    right_to_left. This is what makes the order adapt correctly to
    whatever the *rotated* geometry looks like, rather than assuming the
    layout is still in its original (rotation="0") orientation."""
    if isinstance(group, int):
        return [group]

    sub_centroids = [_group_centroid(g, centroids) for g in group]
    xs = [c[0] for c in sub_centroids]
    ys = [c[1] for c in sub_centroids]
    y_spread = max(ys) - min(ys) if len(ys) > 1 else 0.0
    x_spread = max(xs) - min(xs) if len(xs) > 1 else 0.0

    indices = list(range(len(group)))
    if y_spread >= x_spread:
        indices.sort(key=lambda i: sub_centroids[i][1])
    else:
        indices.sort(key=lambda i: sub_centroids[i][0], reverse=(reading_order == "right_to_left"))

    ordered = []
    for i in indices:
        ordered.extend(_ordered_ids(group[i], centroids, reading_order))
    return ordered


def apply_reading_order(panels, reading_order, preset_choice):
    """Reassigns each panel's `order` (never `id`, which stays a stable
    identity for the panel regardless of reading order or rotation) based
    on the panels' CURRENT polygons — call this after apply_rotation, not
    before, so the order reflects the final rotated layout. Returns the
    panels sorted by the new order.

    `group is None` (no reading_groups at all) falls back to literal
    panel-array order (`p["order"]`, which apply_rotation never touches) —
    this is deliberately how a user-drawn preset with a *manual*
    reading-order override is represented: there is
    no way to encode an arbitrary literal order through the centroid-sort
    structure below (nested groups always re-sort by geometry, regardless
    of array position — that's the whole point, so built-in presets stay
    correct under rotation), so a manual override instead omits
    reading_groups entirely and bakes the order directly into the saved
    panels array's position. The trade-off: an explicitly manual-ordered
    preset doesn't adapt to canvas_rotation the way an auto-derived one
    does — an accepted cost for honoring the user's explicit choice."""
    group = decode_layout_choice(preset_choice).get("reading_groups")
    if group is None:
        return sorted(panels, key=lambda p: p["order"])

    centroids = {p["id"]: polygon_centroid(p["polygon"]) for p in panels}
    ordered_ids = _ordered_ids(group, centroids, reading_order)
    order_by_id = {panel_id: order for order, panel_id in enumerate(ordered_ids)}

    panels = [{**p, "order": order_by_id[p["id"]]} for p in panels]
    return sorted(panels, key=lambda p: p["order"])


_ROTATION_TRANSFORMS = {
    "0": lambda x, y: [x, y],
    "90": lambda x, y: [1.0 - y, x],
    "180": lambda x, y: [1.0 - x, 1.0 - y],
    "270": lambda x, y: [y, 1.0 - x],
}


def apply_rotation(panels, rotation):
    """Rotates every panel's polygon by 0/90/180/270 degrees (clockwise)
    around the page center. `id` and `order` are untouched — this is a pure
    geometry transform."""
    if rotation == "0":
        return panels
    transform = _ROTATION_TRANSFORMS[rotation]
    return [
        {**p, "polygon": [transform(x, y) for x, y in p["polygon"]]}
        for p in panels
    ]


_MAX_READING_GROUP_DEPTH = 50


def _validate_reading_groups(group, num_panels, depth=0):
    """Recursively checks `reading_groups` has the shape _group_centroid/
    _ordered_ids actually expect: arbitrarily-nested lists bottoming out at
    panel-id ints in range. Without this, a saved preset with a bad id
    (e.g. out of range) only fails later, at node-execution time, with a
    raw KeyError out of _group_centroid; a group nested deeper than any
    real layout would ever need can blow Python's recursion limit. Both are
    rejected while decoding the bounded workflow value."""
    if depth > _MAX_READING_GROUP_DEPTH:
        raise ValueError("reading_groups is nested too deeply")
    if isinstance(group, bool) or not isinstance(group, (int, list)):
        raise ValueError("reading_groups must be made of panel-id ints and lists of them")
    if isinstance(group, int):
        if not (0 <= group < num_panels):
            raise ValueError(
                f"reading_groups references panel id {group}, but only {num_panels} panels were supplied"
            )
        return
    if len(group) == 0:
        raise ValueError("reading_groups must not contain an empty group")
    for sub in group:
        _validate_reading_groups(sub, num_panels, depth + 1)
