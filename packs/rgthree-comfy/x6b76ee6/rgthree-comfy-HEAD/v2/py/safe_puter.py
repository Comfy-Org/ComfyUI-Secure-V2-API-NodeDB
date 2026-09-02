"""Bounded expression evaluator used by the secure Power Puter node.

This keeps rgthree's Python-like expression language, but the code is parsed as
data and interpreted inside the guest. Imports, definitions, arbitrary builtins,
dunder traversal, and unbounded loops are deliberately unavailable.
"""
from __future__ import annotations

import ast
import datetime
import hashlib
import math
import operator
import random
import re
from collections.abc import Iterable
from typing import Any

import torch

from .image_ops import common_upscale


MAX_STEPS = 100_000
MAX_RANGE = 10_000
MAX_COLLECTION = 10_000
MAX_TEXT = 1_000_000
MAX_INTEGER_BITS = 4096
MAX_POWER = 1024
MAX_BATCH_INPUTS = 64
MAX_BATCH_ITEMS = 256


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class _Return(Exception):
    def __init__(self, value: Any):
        self.value = value


def update_code(code: str) -> str:
    """Apply the two syntax migrations supported by the upstream node."""
    code = re.sub(r"input_node\(([^'\"].*?)\)", r'input_node("\1")', code)
    code = re.sub(r"random_int\(", "random.int(", code)
    return re.sub(r"random_choice\(", "random.choice(", code)


def is_nondeterministic(code: str) -> bool:
    cleaned = re.sub(r"'[^']*'|\"[^\"]*\"|#.*?$", "", code, flags=re.M)
    if re.search(r"(?<!input_)(?:node|nodes)\(", cleaned):
        return True
    call = re.search(r"(?<!\.)(random\.(?:int|choice))\(", cleaned)
    seed = re.search(r"random\.seed\(", cleaned)
    return bool(call and (not seed or seed.start() > call.start()))


def _batch_images(values: list[torch.Tensor]) -> torch.Tensor:
    first = values[0]
    result = first
    for image in values[1:]:
        if result.shape[-1] != image.shape[-1]:
            if result.shape[-1] > image.shape[-1]:
                image = torch.nn.functional.pad(
                    image, (0, 1), mode="constant", value=1.0
                )
            else:
                result = torch.nn.functional.pad(
                    result, (0, 1), mode="constant", value=1.0
                )
        if result.shape[1:] != image.shape[1:]:
            image = common_upscale(
                image.movedim(-1, 1),
                result.shape[2],
                result.shape[1],
                "bilinear",
                "center",
            ).movedim(1, -1)
        result = torch.cat((result, image), dim=0)
    return result


def _batch_latents(values: list[dict[str, Any]]) -> dict[str, Any]:
    result = dict(values[0])
    samples = result["samples"]
    indices = list(result.get("batch_index", range(samples.shape[0])))
    for latent in values[1:]:
        other = latent["samples"]
        if other.shape[1:] != samples.shape[1:]:
            other = common_upscale(
                other, samples.shape[-1], samples.shape[-2], "bilinear", "center"
            )
        samples = torch.cat((samples, other), dim=0)
        indices.extend(latent.get("batch_index", range(other.shape[0])))
    result["samples"] = samples
    result["batch_index"] = indices
    return result


def batch(*values: Any) -> Any:
    if len(values) < 2:
        raise ValueError("batch() requires at least two values")
    if len(values) > MAX_BATCH_INPUTS:
        raise ValueError(
            f"batch() is limited to {MAX_BATCH_INPUTS} input values"
        )
    latent = isinstance(values[0], dict) and "samples" in values[0]
    if any((isinstance(value, dict) and "samples" in value) != latent for value in values):
        raise ValueError("batch() cannot mix IMAGE and LATENT values")
    if latent:
        if sum(int(value["samples"].shape[0]) for value in values) > MAX_BATCH_ITEMS:
            raise ValueError(
                f"batch() is limited to {MAX_BATCH_ITEMS} output items"
            )
        return _batch_latents(list(values))
    if not all(isinstance(value, torch.Tensor) for value in values):
        raise TypeError("batch() accepts IMAGE tensors or LATENT dictionaries")
    if sum(int(value.shape[0]) for value in values) > MAX_BATCH_ITEMS:
        raise ValueError(
            f"batch() is limited to {MAX_BATCH_ITEMS} output items"
        )
    return _batch_images(list(values))


_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.MatMult: operator.matmul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.RShift: operator.rshift,
    ast.LShift: operator.lshift,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.BitAnd: operator.and_,
    ast.FloorDiv: operator.floordiv,
}
_UNARY = {
    ast.Invert: operator.invert,
    ast.Not: operator.not_,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_COMPARE = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.In: lambda left, right: left in right,
    ast.NotIn: lambda left, right: left not in right,
}

_SAFE_STRING_METHODS = {
    "capitalize", "casefold", "center", "count", "endswith", "find",
    "index", "isalnum", "isalpha", "isascii", "isdecimal",
    "isdigit", "isidentifier", "islower", "isnumeric", "isprintable",
    "isspace", "istitle", "isupper", "join", "ljust", "lower", "lstrip",
    "partition", "removeprefix", "removesuffix", "replace", "rfind",
    "rindex", "rjust", "rpartition", "rsplit", "rstrip", "split",
    "splitlines", "startswith", "strip", "swapcase", "title", "upper",
    "zfill",
}
_SAFE_MAPPING_METHODS = {"copy", "get", "items", "keys", "values"}
_SAFE_LIST_METHODS = {"count", "index"}
_SAFE_PATTERN_METHODS = {
    "findall", "finditer", "fullmatch", "match", "search", "split", "sub", "subn",
}


def _checked_value(value: Any) -> Any:
    """Reject scalar/container results that could exhaust the guest cheaply."""
    if isinstance(value, int) and not isinstance(value, bool):
        if value.bit_length() > MAX_INTEGER_BITS:
            raise ValueError(
                f"Power Puter integers are limited to {MAX_INTEGER_BITS} bits"
            )
    elif isinstance(value, (str, bytes)) and len(value) > MAX_TEXT:
        raise ValueError(
            f"Power Puter text is limited to {MAX_TEXT} characters"
        )
    elif isinstance(value, (list, tuple, dict, set, frozenset)):
        if len(value) > MAX_COLLECTION:
            raise ValueError(
                f"Power Puter collections are limited to {MAX_COLLECTION} items"
            )
    return value


def _checked_binary(operator_type: type[ast.operator], left: Any, right: Any) -> Any:
    """Apply an operator after bounding its expansion-shaped arguments."""
    if operator_type is ast.Pow and isinstance(right, (int, float)):
        finite = True if isinstance(right, int) else math.isfinite(right)
        if not finite or abs(right) > MAX_POWER:
            raise ValueError(
                f"Power Puter exponents are limited to +/-{MAX_POWER}"
            )
        if (
            isinstance(left, int)
            and isinstance(right, int)
            and right >= 0
            and max(1, left.bit_length()) * right > MAX_INTEGER_BITS
        ):
            raise ValueError(
                f"Power Puter integers are limited to {MAX_INTEGER_BITS} bits"
            )
    if operator_type is ast.LShift and isinstance(right, int):
        if right < 0 or right > MAX_INTEGER_BITS:
            raise ValueError("Power Puter shift is outside its bounded range")
    if operator_type is ast.Mult:
        sequence, count = (
            (left, right)
            if isinstance(left, (str, bytes, list, tuple)) and isinstance(right, int)
            else (right, left)
        )
        if isinstance(sequence, (str, bytes, list, tuple)) and isinstance(count, int):
            limit = MAX_TEXT if isinstance(sequence, (str, bytes)) else MAX_COLLECTION
            if count > 0 and len(sequence) * count > limit:
                raise ValueError("Power Puter sequence multiplication is too large")
    fn = _BINARY.get(operator_type)
    if fn is None:
        raise ValueError("unsupported binary operator")
    return _checked_value(fn(left, right))


class Evaluator:
    def __init__(
        self,
        *,
        code: str,
        values: dict[str, Any],
        prompt: dict[str, Any] | None = None,
        unique_id: str = "",
    ) -> None:
        self.code = update_code(code)
        self.values = dict(values)
        self.prompt = prompt if isinstance(prompt, dict) else {}
        self.unique_id = str(unique_id)
        self.steps = 0

    def execute(self) -> Any:
        tree = ast.parse(self.code, mode="exec")
        state = random.getstate()
        random.seed(datetime.datetime.now().timestamp())
        context = {letter: self.values.get(letter) for letter in "abcdefghijklmnopqrstuvwxyz"}
        last = None
        try:
            for statement in tree.body:
                last = self._eval(statement, context)
        except _Return as returned:
            last = returned.value
        finally:
            random.setstate(state)
        return last

    def _tick(self) -> None:
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise RuntimeError("Power Puter evaluation exceeded its operation limit")

    def _nodes(self, selector: Any = None) -> list[dict[str, Any]]:
        nodes = [
            {"id": str(node_id), **dict(node)}
            for node_id, node in self.prompt.items()
            if isinstance(node, dict)
        ]
        if selector is None:
            return nodes
        if isinstance(selector, re.Pattern):
            return [
                node for node in nodes
                if selector.search(str(node.get("_meta", {}).get("title", "")))
            ]
        wanted = str(selector)
        by_id = [node for node in nodes if str(node["id"]) == wanted]
        if by_id:
            return by_id
        return [
            node for node in nodes
            if str(node.get("_meta", {}).get("title", "")) == wanted
        ]

    def _node(self, selector: Any = None) -> dict[str, Any] | None:
        if selector is None:
            selector = self.unique_id
        found = self._nodes(selector)
        return found[0] if found else None

    def _input_node(self, input_name: str, node: dict[str, Any] | None = None):
        source = node or self._node()
        if not isinstance(source, dict):
            return None
        link = source.get("inputs", {}).get(str(input_name))
        if not isinstance(link, (list, tuple)) or not link:
            return None
        return self._node(link[0])

    @staticmethod
    def _power_loras(node: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            value for name, value in node.get("inputs", {}).items()
            if str(name).startswith("lora_")
            and isinstance(value, dict)
            and value.get("on")
        ]

    def _attribute(self, value: Any, name: str, *, for_call: bool = False) -> Any:
        if not isinstance(name, str) or name.startswith("_") or "__" in name:
            raise ValueError(f"Power Puter disallows attribute {name!r}")
        if isinstance(value, dict):
            if name in value:
                return value[name]
            if name == "loras" and value.get("class_type") == "Power Lora Loader (rgthree)":
                return self._power_loras(value)
            if name == "triggers" and value.get("class_type") == "Power Lora Loader (rgthree)":
                return []
            if name in _SAFE_MAPPING_METHODS:
                return getattr(value, name)
            return None
        if isinstance(value, str) and name in _SAFE_STRING_METHODS:
            method = getattr(value, name)

            def checked_string_method(*args, **kwargs):
                # Expansion-oriented string methods accept widths/counts. Cap
                # every numeric/string argument before calling them so the
                # result cannot allocate first and be rejected only afterward.
                _checked_value(value)
                for item in (*args, *kwargs.values()):
                    _checked_value(item)
                    if isinstance(item, int) and abs(item) > MAX_TEXT:
                        raise ValueError("Power Puter string argument is too large")
                if name == "join" and args:
                    items = list(args[0])
                    _checked_value(items)
                    if not all(isinstance(item, str) for item in items):
                        raise TypeError("Power Puter join() items must be strings")
                    if sum(map(len, items)) + len(value) * max(0, len(items) - 1) > MAX_TEXT:
                        raise ValueError("Power Puter join() result is too large")
                    args = (items, *args[1:])
                elif name == "replace" and len(args) >= 2:
                    old, new = args[:2]
                    if isinstance(old, str) and isinstance(new, str):
                        matches = len(value) + 1 if old == "" else len(value) // max(1, len(old))
                        if len(value) + matches * len(new) > MAX_TEXT:
                            raise ValueError("Power Puter replace() result is too large")
                return _checked_value(method(*args, **kwargs))

            return checked_string_method
        if isinstance(value, (list, tuple)) and name in _SAFE_LIST_METHODS:
            return getattr(value, name)
        if isinstance(value, re.Pattern) and name in _SAFE_PATTERN_METHODS:
            method = getattr(value, name)

            def checked_pattern_method(*args, **kwargs):
                for item in (*args, *kwargs.values()):
                    _checked_value(item)
                strings = [item for item in args if isinstance(item, str)]
                if any(len(item) > MAX_TEXT // 10 for item in strings):
                    raise ValueError("Power Puter regex input is too large")
                if name in {"sub", "subn"} and len(strings) >= 2:
                    replacement, source = strings[0], strings[1]
                    if (len(source) + 1) * max(1, len(replacement)) > MAX_TEXT:
                        raise ValueError("Power Puter regex replacement is too large")
                return _checked_value(method(*args, **kwargs))

            return checked_pattern_method
        if isinstance(value, torch.Tensor) and name in {"shape", "dtype", "ndim"}:
            return getattr(value, name)
        if isinstance(value, datetime.datetime) and name in {
            "day", "hour", "microsecond", "minute", "month", "second",
            "date", "isoformat", "strftime", "time", "timestamp", "weekday",
            "year",
        }:
            return getattr(value, name)
        if isinstance(value, datetime.date) and name in {
            "day", "isoformat", "month", "strftime", "weekday", "year",
        }:
            return getattr(value, name)
        if isinstance(value, datetime.time) and name in {
            "hour", "isoformat", "microsecond", "minute", "second", "strftime",
        }:
            return getattr(value, name)
        if isinstance(value, datetime.timedelta) and name in {
            "days", "microseconds", "seconds", "total_seconds",
        }:
            return getattr(value, name)
        if isinstance(value, _RandomNamespace) and name in {"int", "choice", "seed"}:
            return getattr(value, name)
        if isinstance(value, _DateTimeNamespace) and name in {
            "date", "datetime", "time", "timedelta", "timezone",
        }:
            return getattr(value, name)
        if isinstance(value, _DateTimeFactory) and name in {
            "combine", "fromisoformat", "fromtimestamp", "now", "strptime",
            "today", "utcfromtimestamp", "utcnow",
        }:
            return getattr(value, name)
        raise ValueError(f"Power Puter disallows {type(value).__name__}.{name}")

    def _builtin(self, name: str):
        functions = {
            "round": round,
            "ceil": math.ceil,
            "floor": math.floor,
            "sqrt": math.sqrt,
            "min": min,
            "max": max,
            "re": re.compile,
            "len": len,
            "enumerate": enumerate,
            "range": self._range,
            "now": datetime.datetime.now,
            "strftime": lambda value: datetime.datetime.now().strftime(value),
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "list": list,
            "tuple": tuple,
            "dir": lambda value: [name for name in dir(value) if not name.startswith("_")],
            "type": lambda value: type(value).__name__,
            "print": print,
            "sha264": lambda value: hashlib.sha256(str(value).encode()).hexdigest(),
            "node": self._node,
            "nodes": self._nodes,
            "input_node": self._input_node,
            "batch": batch,
        }
        if name == "random":
            return _RandomNamespace()
        if name == "datetime":
            return _DateTimeNamespace()
        if name == "purge_vram":
            return lambda *_args: None
        if name not in functions:
            raise NameError(f"Name not found: {name}")
        return functions[name]

    @staticmethod
    def _range(*args: int) -> range:
        value = range(*args)
        if len(value) > MAX_RANGE:
            raise ValueError(f"range() is limited to {MAX_RANGE} items")
        return value

    @staticmethod
    def _assign(target: ast.AST, value: Any, context: dict[str, Any]) -> None:
        if isinstance(target, ast.Name):
            context[target.id] = value
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            items = list(value)
            if len(items) != len(target.elts):
                raise ValueError("unpacking assignment length mismatch")
            for child, item in zip(target.elts, items, strict=True):
                Evaluator._assign(child, item, context)
            return
        if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
            container = context[target.value.id]
            if not isinstance(container, (list, dict)):
                raise ValueError(
                    "Power Puter subscript assignment is limited to lists and dictionaries"
                )
            key = Evaluator._literal_slice(target.slice, context)
            container[key] = value
            return
        raise ValueError("unsupported Power Puter assignment target")

    @staticmethod
    def _literal_slice(node: ast.AST, context: dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return _checked_value(node.value)
        if isinstance(node, ast.Name) and node.id in context:
            return context[node.id]
        raise ValueError("unsupported assignment subscript")

    def _eval(self, node: ast.AST, context: dict[str, Any]) -> Any:
        self._tick()
        if isinstance(node, ast.Expr):
            return self._eval(node.value, context)
        if isinstance(node, ast.Constant):
            return _checked_value(node.value)
        if isinstance(node, ast.Name):
            return (
                _checked_value(context[node.id])
                if node.id in context
                else self._builtin(node.id)
            )
        if isinstance(node, ast.List):
            return _checked_value([self._eval(item, context) for item in node.elts])
        if isinstance(node, ast.Tuple):
            return _checked_value(tuple(self._eval(item, context) for item in node.elts))
        if isinstance(node, ast.Dict):
            return _checked_value({
                self._eval(key, context): self._eval(value, context)
                for key, value in zip(node.keys, node.values, strict=True)
            })
        if isinstance(node, ast.BinOp):
            return _checked_binary(
                type(node.op),
                self._eval(node.left, context),
                self._eval(node.right, context),
            )
        if isinstance(node, ast.UnaryOp):
            fn = _UNARY.get(type(node.op))
            if fn is None:
                raise ValueError("unsupported unary operator")
            return fn(self._eval(node.operand, context))
        if isinstance(node, ast.BoolOp):
            value = self._eval(node.values[0], context)
            for child in node.values[1:]:
                if isinstance(node.op, ast.And):
                    if not value:
                        return value
                elif value:
                    return value
                value = self._eval(child, context)
            return value
        if isinstance(node, ast.Compare):
            left = self._eval(node.left, context)
            for operation, comparator in zip(node.ops, node.comparators, strict=True):
                right = self._eval(comparator, context)
                fn = _COMPARE.get(type(operation))
                if fn is None or not fn(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            selected = node.body if self._eval(node.test, context) else node.orelse
            return self._eval(selected, context)
        if isinstance(node, ast.JoinedStr):
            parts = [str(self._eval(item, context)) for item in node.values]
            if sum(map(len, parts)) > MAX_TEXT:
                raise ValueError("Power Puter formatted text is too large")
            return "".join(parts)
        if isinstance(node, ast.FormattedValue):
            return self._eval(node.value, context)
        if isinstance(node, ast.Subscript):
            value = self._eval(node.value, context)
            key = self._eval(node.slice, context)
            return value[key]
        if isinstance(node, ast.Slice):
            return slice(
                self._eval(node.lower, context) if node.lower else None,
                self._eval(node.upper, context) if node.upper else None,
                self._eval(node.step, context) if node.step else None,
            )
        if isinstance(node, ast.Attribute):
            return self._attribute(self._eval(node.value, context), node.attr)
        if isinstance(node, ast.Call):
            if node.keywords and any(item.arg is None for item in node.keywords):
                raise ValueError("Power Puter does not support **kwargs expansion")
            fn = self._eval(node.func, context)
            if not callable(fn):
                raise TypeError("Power Puter call target is not callable")
            args = [self._eval(item, context) for item in node.args]
            kwargs = {item.arg: self._eval(item.value, context) for item in node.keywords}
            return _checked_value(fn(*args, **kwargs))
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                raise ValueError("Power Puter supports one assignment target")
            value = self._eval(node.value, context)
            self._assign(node.targets[0], value, context)
            return value
        if isinstance(node, ast.AugAssign):
            if not isinstance(node.target, ast.Name) or type(node.op) not in _BINARY:
                raise ValueError("unsupported augmented assignment")
            value = _checked_binary(
                type(node.op),
                context[node.target.id],
                self._eval(node.value, context),
            )
            context[node.target.id] = value
            return value
        if isinstance(node, ast.NamedExpr):
            value = self._eval(node.value, context)
            self._assign(node.target, value, context)
            return value
        if isinstance(node, ast.If):
            body = node.body if self._eval(node.test, context) else node.orelse
            value = None
            for statement in body:
                value = self._eval(statement, context)
            return value
        if isinstance(node, ast.For):
            iterable = self._eval(node.iter, context)
            if not isinstance(iterable, Iterable):
                raise TypeError("Power Puter for-loop value is not iterable")
            value = None
            for index, item in enumerate(iterable):
                if index >= MAX_RANGE:
                    raise ValueError(f"loops are limited to {MAX_RANGE} iterations")
                self._assign(node.target, item, context)
                try:
                    for statement in node.body:
                        value = self._eval(statement, context)
                except _Continue:
                    continue
                except _Break:
                    break
            return value
        if isinstance(node, ast.While):
            value = None
            for _ in range(MAX_RANGE):
                if not self._eval(node.test, context):
                    return value
                try:
                    for statement in node.body:
                        value = self._eval(statement, context)
                except _Continue:
                    continue
                except _Break:
                    return value
            raise ValueError(f"while loops are limited to {MAX_RANGE} iterations")
        if isinstance(node, ast.ListComp):
            result: list[Any] = []

            def expand(index: int, local: dict[str, Any]) -> None:
                if len(result) >= MAX_RANGE:
                    raise ValueError(f"comprehensions are limited to {MAX_RANGE} items")
                generator = node.generators[index]
                iterable = self._eval(generator.iter, local)
                for item in iterable:
                    child = dict(local)
                    self._assign(generator.target, item, child)
                    if not all(self._eval(condition, child) for condition in generator.ifs):
                        continue
                    if index + 1 < len(node.generators):
                        expand(index + 1, child)
                    else:
                        result.append(self._eval(node.elt, child))

            expand(0, dict(context))
            return result
        if isinstance(node, ast.Return):
            raise _Return(self._eval(node.value, context) if node.value else None)
        if isinstance(node, ast.Break):
            raise _Break()
        if isinstance(node, ast.Continue):
            raise _Continue()
        if isinstance(node, ast.Pass):
            return None
        raise ValueError(f"unsupported Power Puter syntax: {type(node).__name__}")


class _RandomNamespace:
    @staticmethod
    def int(start: int, end: int) -> int:
        return random.randint(start, end)

    @staticmethod
    def choice(values: Any) -> Any:
        return random.choice(values)

    @staticmethod
    def seed(value: Any) -> None:
        random.seed(value)


class _DateTimeFactory:
    """Callable, attribute-limited view of ``datetime.datetime``."""

    def __call__(self, *args, **kwargs):
        return datetime.datetime(*args, **kwargs)

    @staticmethod
    def combine(*args, **kwargs):
        return datetime.datetime.combine(*args, **kwargs)

    @staticmethod
    def fromisoformat(*args, **kwargs):
        return datetime.datetime.fromisoformat(*args, **kwargs)

    @staticmethod
    def fromtimestamp(*args, **kwargs):
        return datetime.datetime.fromtimestamp(*args, **kwargs)

    @staticmethod
    def now(*args, **kwargs):
        return datetime.datetime.now(*args, **kwargs)

    @staticmethod
    def strptime(*args, **kwargs):
        return datetime.datetime.strptime(*args, **kwargs)

    @staticmethod
    def today(*args, **kwargs):
        return datetime.datetime.today(*args, **kwargs)

    @staticmethod
    def utcfromtimestamp(*args, **kwargs):
        return datetime.datetime.utcfromtimestamp(*args, **kwargs)

    @staticmethod
    def utcnow(*args, **kwargs):
        return datetime.datetime.utcnow(*args, **kwargs)


class _DateTimeNamespace:
    """Read-only subset of the datetime module exposed by upstream."""

    date = datetime.date
    time = datetime.time
    timedelta = datetime.timedelta
    timezone = datetime.timezone
    datetime = _DateTimeFactory()


__all__ = ["Evaluator", "is_nondeterministic", "update_code"]
