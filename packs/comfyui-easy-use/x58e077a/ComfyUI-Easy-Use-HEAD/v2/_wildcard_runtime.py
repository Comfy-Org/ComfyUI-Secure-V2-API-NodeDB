"""Bounded wildcard catalogue loading and prompt expansion.

Wildcard files are data, not filesystem authority.  The caller supplies a
pack-specific asset folder and this module only resolves names returned by
that catalogue.  Parsing stays in the sandbox and never receives a host path.
"""
from __future__ import annotations

import json
import math
import random
import re
from pathlib import PurePosixPath
from typing import Any


_MAX_FILES = 1024
_MAX_FILE_BYTES = 2 * 1024 * 1024
_MAX_TOTAL_BYTES = 16 * 1024 * 1024
_MAX_ENTRY_CHARS = 64 * 1024
_MAX_OUTPUT_CHARS = 1024 * 1024
_MAX_MATRIX_OUTPUTS = 4096
_TOKEN = re.compile(r"__([\w\s.\-+/*\\]+?)__")
_QUANTIFIED_TOKEN = re.compile(
    r"(?P<count>\d+)#__(?P<key>[\w.\-+/*\\]+?)__", re.IGNORECASE
)
_NUMBER = re.compile(r"^-?(?:\d*\.?\d+|\d+\.?\d*)$")
_CACHE: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {}


def _normalize(value: str, style: str) -> str:
    value = value.replace("\\", "/").lower()
    return value.replace(" ", "-") if style == "impact" else value


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, (str, int, float)):
        return [str(value)]
    return []


def _flatten(
    target: dict[str, tuple[str, ...]], key: str, value: Any, style: str,
) -> None:
    if isinstance(value, dict):
        for child, child_value in value.items():
            nested = f"{key}/{child}" if key else str(child)
            _flatten(target, nested, child_value, style)
        return
    values = _strings(value)
    if not key or not values:
        return
    if any(len(item) > _MAX_ENTRY_CHARS for item in values):
        raise ValueError(f"wildcard {key!r} contains an oversized entry")
    target[_normalize(key, style)] = tuple(values)


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("iso-8859-1")


def _decode_file(
    target: dict[str, tuple[str, ...]], name: str, data: bytes, style: str,
) -> None:
    suffix = PurePosixPath(name).suffix.lower()
    text = _decode_text(data)
    if suffix == ".txt":
        key = str(PurePosixPath(name).with_suffix(""))
        lines = text.splitlines()
        if style == "impact":
            lines = [
                line for line in lines
                if line.strip() and not line.strip().startswith("#")
            ]
        _flatten(target, key, lines, style)
        return
    if suffix == ".json":
        if style != "easy":
            return
        document = json.loads(text)
    else:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - base runtime has PyYAML
            raise RuntimeError(
                "YAML wildcard assets require the sealed PyYAML runtime"
            ) from exc
        document = yaml.safe_load(text)
    if document is None:
        return
    if not isinstance(document, dict):
        raise ValueError(f"wildcard data file {name!r} must contain a mapping")
    for key, value in document.items():
        _flatten(target, str(key), value, style)


async def load_catalogue(ctx, folder: str, *, style: str) -> dict[str, tuple[str, ...]]:
    """Load a declared wildcard folder once per persistent guest."""
    if style not in {"easy", "impact"}:
        raise ValueError("unknown wildcard dialect")
    cache_key = (folder, style)
    cached = _CACHE.get(cache_key)
    if cached is not None:
        return cached
    suffixes = {".txt", ".yaml", ".yml"}
    if style == "easy":
        suffixes.add(".json")
    names = [
        str(name) for name in await ctx.assets.list(folder, recursive=True)
        if PurePosixPath(str(name)).suffix.lower() in suffixes
    ]
    if len(names) > _MAX_FILES:
        raise ValueError(
            f"wildcard catalogue has {len(names)} files; limit is {_MAX_FILES}"
        )
    target: dict[str, tuple[str, ...]] = {}
    total = 0
    for name in sorted(names):
        ref = await ctx.assets.resolve(folder, name)
        data = await ctx.assets.read_bytes(ref)
        if len(data) > _MAX_FILE_BYTES:
            raise ValueError(
                f"wildcard file {name!r} exceeds {_MAX_FILE_BYTES} bytes"
            )
        total += len(data)
        if total > _MAX_TOTAL_BYTES:
            raise ValueError(
                f"wildcard catalogue exceeds {_MAX_TOTAL_BYTES} bytes"
            )
        _decode_file(target, name, data, style)
    _CACHE[cache_key] = target
    return target


def _depth_match(key: str, requested: str) -> bool:
    return (
        key == requested
        or key.endswith("/" + requested)
        or key.startswith(requested + "/")
        or ("/" + requested + "/") in key
    )


def wildcard_choices(
    raw_key: str, catalogue: dict[str, tuple[str, ...]], *, style: str,
) -> tuple[str, ...] | None:
    key = _normalize(raw_key, style)
    direct = catalogue.get(key)
    if direct is not None:
        return direct
    matches: list[str] = []
    if "*" in key:
        if key.startswith("*/"):
            requested = key[2:]
            for candidate, values in catalogue.items():
                if _depth_match(candidate, requested):
                    matches.extend(values)
        else:
            pattern = re.compile(re.escape(key).replace(r"\*", ".*"))
            for candidate, values in catalogue.items():
                if pattern.match(candidate) or pattern.match(candidate + "/"):
                    matches.extend(values)
    elif "/" not in key:
        for candidate, values in catalogue.items():
            if _depth_match(candidate, key):
                matches.extend(values)
    return tuple(matches) if matches else None


def _weighted(value: str) -> tuple[float, str]:
    parts = str(value).split("::", 1)
    if len(parts) == 2 and _NUMBER.fullmatch(parts[0].strip()):
        weight = float(parts[0].strip())
        if not math.isfinite(weight) or weight < 0:
            raise ValueError("wildcard weights must be finite and non-negative")
        return weight, parts[1]
    return 1.0, str(value)


def _pick_one(options: list[str] | tuple[str, ...], rng: random.Random) -> str:
    if not options:
        raise ValueError("wildcard has no choices")
    weighted = [_weighted(option) for option in options]
    total = sum(weight for weight, _ in weighted)
    if total <= 0:
        raise ValueError("wildcard choices have zero total weight")
    mark = rng.random() * total
    for weight, value in weighted:
        mark -= weight
        if mark <= 0:
            return value
    return weighted[-1][1]


def _pick_many(
    options: list[str], count: int, separator: str, rng: random.Random,
) -> str:
    count = max(0, min(count, len(options)))
    pool = list(options)
    selected: list[str] = []
    for _ in range(count):
        weighted = [_weighted(option) for option in pool]
        total = sum(weight for weight, _ in weighted)
        if total <= 0:
            raise ValueError("wildcard choices have zero total weight")
        mark = rng.random() * total
        index = len(pool) - 1
        for candidate, (weight, _value) in enumerate(weighted):
            mark -= weight
            if mark <= 0:
                index = candidate
                break
        selected.append(weighted[index][1])
        pool.pop(index)
    return separator.join(selected)


def _inline_choice(
    raw: str,
    rng: random.Random,
    catalogue: dict[str, tuple[str, ...]],
    style: str,
) -> str:
    options = raw.split("|")
    pieces = options[0].split("$$")
    select_range: tuple[int, int] | None = None
    separator = " "
    if len(pieces) in (2, 3):
        match = re.match(r"^(\d+)(?:-(\d+))?", pieces[0])
        if match:
            low = int(match.group(1))
            high = int(match.group(2) or low)
        else:
            match = re.match(r"^-(\d+)", pieces[0])
            low, high = (1, int(match.group(1))) if match else (0, -1)
        if match:
            if high < low:
                low, high = high, low
            select_range = (low, high)
            if len(pieces) == 2:
                options[0] = pieces[1]
            else:
                separator = pieces[1]
                options[0] = pieces[2]
    if select_range is None:
        return _pick_one(options, rng)
    if len(options) == 1:
        named = _TOKEN.fullmatch(options[0])
        if named is not None:
            expanded = wildcard_choices(
                named.group(1), catalogue, style=style
            )
            if expanded is not None:
                options = list(expanded)
    count = rng.randint(*select_range)
    return _pick_many(options, count, separator, rng)


def _comment_filter(text: str) -> str:
    output: list[str] = []
    skipped = False
    for line in text.split("\n"):
        if line.lstrip().startswith("#"):
            skipped = True
            continue
        if not output:
            output.append(line)
        elif skipped:
            output[-1] += " " + line
            skipped = False
        else:
            output.append(line)
    return "\n".join(output)


def populate(
    text: str,
    seed: int,
    catalogue: dict[str, tuple[str, ...]],
    *,
    style: str,
) -> str:
    """Populate inline and named wildcards, including nested replacements."""
    result = _comment_filter(str(text)) if style == "impact" else str(text)
    rng = random.Random(int(seed))
    inline = (
        re.compile(r"(?<!\\)\{((?:[^{}]|(?<=\\)[{}])*?)(?<!\\)\}")
        if style == "impact" else re.compile(r"\{([^{}]*?)\}")
    )
    for _ in range(99):
        changed = False
        if style == "impact":
            def quantified(match: re.Match[str]) -> str:
                count = int(match.group("count"))
                if count > 128:
                    raise ValueError("wildcard quantifier exceeds the secure limit of 128")
                token = f"__{match.group('key')}__"
                return "|".join([token] * count)
            expanded = _QUANTIFIED_TOKEN.sub(quantified, result)
            changed = expanded != result
            result = expanded
        while True:
            match = inline.search(result)
            if match is None:
                break
            replacement = _inline_choice(
                match.group(1), rng, catalogue, style
            )
            result = result[:match.start()] + replacement + result[match.end():]
            changed = True
            if len(result) > _MAX_OUTPUT_CHARS:
                raise ValueError("populated wildcard prompt exceeds the secure size limit")
        matches = list(_TOKEN.finditer(result))
        if matches:
            match = matches[0]
            options = wildcard_choices(match.group(1), catalogue, style=style)
            if options is not None:
                replacement = _pick_one(options, rng)
                result = result[:match.start()] + replacement + result[match.end():]
                changed = True
                if len(result) > _MAX_OUTPUT_CHARS:
                    raise ValueError("populated wildcard prompt exceeds the secure size limit")
        if not changed:
            break
    return result


def matrix(
    text: str,
    catalogue: dict[str, tuple[str, ...]],
    offset: int,
    output_limit: int,
) -> tuple[list[str], int, list[int]]:
    """Enumerate Easy Use's independent inline/named wildcard dimensions."""
    source = str(text)
    replacer = re.compile(r"\{([^{}]*?)\}|__([\w\s.\-+/*\\]+?)__")
    blocks: list[str] = []
    choices: list[tuple[str, ...]] = []
    tail = 0
    for match in replacer.finditer(source):
        blocks.append(source[tail:match.start()])
        blocks.append(f"\0{len(choices)}\0")
        if match.group(1) is not None:
            current = tuple(match.group(1).split("|"))
        else:
            current = wildcard_choices(match.group(2), catalogue, style="easy")
            if current is None:
                raise ValueError(
                    f"named wildcard {match.group(0)!r} is not in the declared catalogue"
                )
        if not current:
            raise ValueError(f"wildcard {match.group(0)!r} has no choices")
        choices.append(tuple(current))
        tail = match.end()
    blocks.append(source[tail:])
    template = "".join(blocks)
    factors = [len(group) for group in choices]
    total = math.prod(factors) if factors else 1
    requested = total if int(output_limit) == -1 else max(0, min(total, int(output_limit)))
    if requested > _MAX_MATRIX_OUTPUTS:
        raise ValueError(
            f"wildcard matrix requests {requested} outputs; secure limit is {_MAX_MATRIX_OUTPUTS}"
        )
    start = 0 if int(output_limit) == -1 else int(offset) % total
    output: list[str] = []
    for position in range(start, start + requested):
        remainder = position % total
        value = template
        for index, group in enumerate(choices):
            selected = remainder % len(group)
            remainder //= len(group)
            value = value.replace(f"\0{index}\0", group[selected], 1)
        output.append(value)
    return output, total, factors
