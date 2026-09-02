"""Compile AIGODLIKE's legacy dictionaries into native V2 locale data.

The schema conversion belongs to this pack.  Core receives only its ordinary
locale-catalog shape and never needs to know what ``Nodes/``, ``Menu.json`` or
the phrase-keyed tooltip dictionaries meant.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator


LOCALES = {
    "zh": "zh-CN",
    "zh-TW": "zh-TW",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "ru": "ru-RU",
}
HOST_BUNDLES = {
    "main": "main.json",
    "commands": "commands.json",
    "settings": "settings.json",
}
SYNTAX_CHARACTERS = frozenset("@${}|%")


def _read_json(path: Path) -> dict[str, Any]:
    for encoding in ("utf-8", "gbk"):
        try:
            value = json.loads(path.read_text(encoding=encoding))
        except (UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict):
            raise TypeError(f"locale file must contain an object: {path}")
        return value
    raise ValueError(f"locale file is not valid UTF-8 or GBK JSON: {path}")


def _merge_files(paths: list[Path]) -> tuple[dict[str, Any], int]:
    merged: dict[str, Any] = {}
    duplicate_count = 0
    for path in paths:
        for key, value in _read_json(path).items():
            duplicate_count += int(key in merged)
            merged[key] = value
    return merged, duplicate_count


def _locale_files(directory: Path, plural: str, single: str) -> list[Path]:
    paths = sorted((directory / plural).glob("*.json"))
    exact = directory / single
    if exact.is_file():
        paths.append(exact)
    # The Japanese contribution is named menu.json.  The legacy Linux route
    # accidentally skipped it; its documented intent is unambiguously a menu
    # catalog, and case-insensitive installs did load it.
    folded = {path.name.casefold() for path in paths}
    for candidate in sorted(directory.glob("*.json")):
        if candidate.name.casefold() == single.casefold() \
                and candidate.name.casefold() not in folded:
            paths.append(candidate)
            folded.add(candidate.name.casefold())
    return paths


def load_legacy(root: Path, locale: str) -> dict[str, dict[str, Any]]:
    directory = root / locale
    nodes, node_duplicates = _merge_files(
        sorted((directory / "Nodes").glob("*.json"))
    )
    categories, category_duplicates = _merge_files(
        _locale_files(directory, "Categories", "NodeCategory.json")
    )
    menus, menu_duplicates = _merge_files(
        _locale_files(directory, "Menus", "Menu.json")
    )
    return {
        "Nodes": nodes,
        "NodeCategory": categories,
        "Menu": menus,
        "_duplicates": {
            "Nodes": node_duplicates,
            "NodeCategory": category_duplicates,
            "Menu": menu_duplicates,
        },
    }


def _walk_strings(value: Any, path: tuple[str, ...] = ()) \
        -> Iterator[tuple[tuple[str, ...], str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_strings(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_strings(child, (*path, str(index)))


def _put(root: dict[str, Any], path: tuple[str, ...], value: str) -> None:
    if not path:
        raise ValueError("a locale value cannot replace the catalog root")
    cursor = root
    for segment in path[:-1]:
        existing = cursor.get(segment)
        if not isinstance(existing, dict):
            existing = {}
            cursor[segment] = existing
        cursor = existing
    cursor[path[-1]] = value


def _normalize_key(value: str) -> str:
    return value.replace(".", "_")


def _escape_message(value: str) -> str:
    value = value.replace("\\", "\\\\")
    return "".join(
        f"{{'{character}'}}" if character in SYNTAX_CHARACTERS else character
        for character in value
    )


def build_host_messages(
    legacy: dict[str, dict[str, Any]], frontend_locales: Path
) -> tuple[dict[str, Any], dict[str, int]]:
    menu = {
        key: value
        for key, value in legacy["Menu"].items()
        if isinstance(key, str) and isinstance(value, str)
    }
    messages: dict[str, Any] = {}
    matched_source_phrases: set[str] = set()
    matched_host_leaves = 0

    for bundle, filename in HOST_BUNDLES.items():
        english = _read_json(frontend_locales / "en" / filename)
        prefix = () if bundle == "main" else (bundle,)
        for path, phrase in _walk_strings(english):
            translated = menu.get(phrase)
            if translated is None:
                translated = menu.get(phrase.strip())
            if not isinstance(translated, str) or translated == phrase:
                continue
            _put(messages, (*prefix, *path), _escape_message(translated))
            matched_host_leaves += 1
            matched_source_phrases.add(phrase if phrase in menu else phrase.strip())

    categories = {
        _normalize_key(key): _escape_message(value)
        for key, value in legacy["NodeCategory"].items()
        if isinstance(key, str) and isinstance(value, str) and value != key
    }
    if categories:
        existing = messages.setdefault("nodeCategories", {})
        if not isinstance(existing, dict):
            raise TypeError("host nodeCategories catalog is not an object")
        existing.update(categories)

    return messages, {
        "menu_source_phrases": len(menu),
        "matched_menu_source_phrases": len(matched_source_phrases),
        "matched_host_leaves": matched_host_leaves,
        "node_categories": len(categories),
    }


def build_phrase_catalog(legacy: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Return the exact-string fallback used at host-owned render points.

    Values stay raw: unlike keyed vue-i18n messages, phrase fallbacks are not
    passed through the message compiler.
    """
    return {
        key: value
        for key, value in legacy["Menu"].items()
        if isinstance(key, str)
        and isinstance(value, str)
        and key
        and value != key
    }


def _write_module(path: Path, value: dict[str, Any]) -> None:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    path.write_text(
        "// Generated by tools/build_catalogs.py; do not hand-edit.\n"
        f"export default {encoded};\n",
        encoding="utf-8",
    )


def build(root: Path, frontend_locales: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, Any] = {
        "format": "aigodlike-native-catalog-v1",
        "locales": {},
    }
    for host_locale, legacy_locale in LOCALES.items():
        legacy = load_legacy(root, legacy_locale)
        messages, stats = build_host_messages(legacy, frontend_locales)
        value = {
            "messages": messages,
            "nodes": legacy["Nodes"],
            "phrases": build_phrase_catalog(legacy),
        }
        destination = output / f"{host_locale}.js"
        _write_module(destination, value)
        metadata["locales"][host_locale] = {
            "legacy_locale": legacy_locale,
            "node_definitions": len(legacy["Nodes"]),
            "duplicates": legacy["_duplicates"],
            "generated_bytes": destination.stat().st_size,
            **stats,
        }

    (output / "catalog-meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="complete V2 sibling containing the pristine locale directories",
    )
    parser.add_argument(
        "--frontend-locales",
        type=Path,
        required=True,
        help="pinned ComfyUI frontend src/locales directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="generated module directory (defaults to ROOT/catalogs)",
    )
    args = parser.parse_args()
    output = args.output or args.root / "catalogs"
    metadata = build(
        args.root.resolve(),
        args.frontend_locales.resolve(),
        output.resolve(),
    )
    print(json.dumps(metadata, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
