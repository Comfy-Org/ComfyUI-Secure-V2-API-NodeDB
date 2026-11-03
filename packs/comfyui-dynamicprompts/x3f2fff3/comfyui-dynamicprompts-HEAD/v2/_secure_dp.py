"""Secure Nodes V2 classes for comfyui-dynamicprompts (pin 3f2fff32358c).

All six node ids keep their original inputs, options, outputs, categories and display names.

Converted. These run the original classes from nodes/, which are byte-identical copies.
  - DPRandomGenerator and DPCombinatorialGenerator. Core keeps one instance of a V1 node class per
    workflow node id, and these nodes keep their sampling state on that instance: the prompt
    iterator, the current template and the wildcard tree. So the guest keeps one original instance
    per (node id, node type) for the life of the pack's guest process. The runtime does the same for
    legacy classes (comfy_secure_nodes/guest/adapter.py, _LEGACY_INSTANCES). get_prompt runs
    unchanged, including its reseeding of the library's shared DEFAULT_RANDOM.
    Boundary edit: the original read its wildcard folder from the host file system (ComfyUI/wildcards,
    else the pack's own wildcards folder). Here the files come from the "dynamicprompts_wildcards"
    asset kind, read through the SDK when the instance is created. The library builds its tree from
    them with its own rules (_WildcardFolder below).
  - DPJinja: a new original instance per run. The original keeps no state between runs.
  - DPOutput: calls the original method the way Core calls it. Upstream this always fails, because
    the method takes `string` but the input is named `text`. It fails the same way here.
Refused by name, at queue time (validate_inputs) and in execute:
  - DPMagicPrompt: it needs a GPT-2 text-generation model.
  - DPFeelingLucky: it fetches prompts from an online service at run time.
"""
import hashlib
import io as _stdio
from pathlib import PurePosixPath

from comfy_api.latest import io, sdk

from .nodes import combinatorial as _combinatorial
from .nodes import generator as _generator
from .nodes import jinja as _jinja
from .nodes import output_node as _output_node
from .nodes import random as _random
from .nodes import sampler as _sampler

PACK = "comfyui-dynamicprompts"
WILDCARD_KIND = "dynamicprompts_wildcards"
# dynamicprompts/wildcards/tree/build.py: its folder walk reads these suffixes (case-sensitive) and
# skips directories whose names start with ".".
_WILDCARD_SUFFIXES = (".txt", ".json", ".yaml")


class NotConvertedError(RuntimeError):
    """A registered node that refuses to run in Secure Nodes V2."""


class WildcardsUnavailableError(Exception):
    """A template sampled a wildcard, but the host's wildcard files could not be listed.

    Not a RuntimeError: nodes/sampler.py restarts its iterator on RuntimeError.
    """


def _refusal(node_id, reason):
    return f"{PACK}/{node_id} is not yet converted to Secure Nodes V2: {reason}"


MAGIC_PROMPT_REFUSAL = _refusal(
    "DPMagicPrompt", "it rewrites prompts with a GPT-2 text-generation model, which this pack's guest does not have")
FEELING_LUCKY_REFUSAL = _refusal(
    "DPFeelingLucky", "it fetches prompts from an online search service at run time, and a Secure Nodes V2 guest has "
    "no network")


def _sampler_schema(node_id, display_name):
    # nodes/sampler.py DPAbstractSamplerNode: INPUT_TYPES, RETURN_TYPES and CATEGORY.
    return io.Schema(
        node_id=node_id,
        display_name=display_name,
        category="Dynamic Prompts",
        inputs=[
            io.String.Input("text", multiline=True, dynamic_prompts=False),
            io.Int.Input("seed", default=0, display_mode=io.NumberDisplay.number),
            io.Combo.Input("autorefresh", options=["Yes", "No"], default="No"),
        ],
        outputs=[io.String.Output()],
    )


# ---------------------------------------------------------------- wildcards, read through the SDK
class _WildcardFile(PurePosixPath):
    """A wildcard file as the library uses it: pure path operations for its name and suffix, and
    open() / read_text() over the bytes read through the SDK (the original opened the host file)."""

    def __init__(self, *segments, content=None):
        super().__init__(*segments)
        self._content = content

    def open(self, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        if mode != "r" or self._content is None:
            raise OSError(f"{self} is not a readable wildcard file")
        return _stdio.TextIOWrapper(_stdio.BytesIO(self._content), encoding=encoding, errors=errors, newline=newline)

    def read_text(self, encoding=None, errors=None, newline=None):
        with self.open(encoding=encoding, errors=errors, newline=newline) as handle:
            return handle.read()


def _walk_order(names):
    """The listed files the library's folder walk would read, in os.walk order over sorted entries.

    build_tree_from_path visits a directory's files, then its subdirectories, and skips directories
    whose names start with "."; a later file wins when two files give one wildcard name.
    """
    tree = {}
    for name in names:
        parts = name.split("/")
        if any(part.startswith(".") for part in parts[:-1]):
            continue
        if PurePosixPath(parts[-1]).suffix not in _WILDCARD_SUFFIXES:
            continue
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(("dir", part), {})
        node[("file", parts[-1])] = name
    order = []

    def walk(node):
        order.extend(node[key] for key in sorted(k for k in node if k[0] == "file"))
        for key in sorted(k for k in node if k[0] == "dir"):
            walk(node[key])

    walk(tree)
    return order


class _WildcardFolder:
    """The library's view of the wildcard folder. It is built at the first wildcard an instance
    samples, the moment the original's WildcardManager walked ComfyUI/wildcards
    (dynamicprompts/wildcards/tree/build.py build_tree_from_path). Each file goes through the
    library's own _get_wildcard_collections_from_path, which applies the same names, suffixes and
    text, JSON and YAML parsing as before."""

    def __init__(self, node_type, files=None, problem=None):
        self._node_type = node_type
        self._files = files
        self._problem = problem

    def items(self):  # called by dynamicprompts.wildcards.tree.build.build_tree_from_root_map
        if self._problem is not None:
            raise WildcardsUnavailableError(
                f"{PACK}/{self._node_type}: this template samples a wildcard, but the host's {WILDCARD_KIND} "
                f"asset kind cannot be listed ({self._problem}). The original read wildcard files from the host "
                "file system, which a Secure Nodes V2 guest cannot do.")
        from dynamicprompts.wildcards.tree.build import _get_wildcard_collections_from_path
        from dynamicprompts.wildcards.tree.tree import WildcardTree

        root = _WildcardFile(WILDCARD_KIND)
        path_to_file = {}
        for name, content in self._files.items():
            path_to_file.update(_get_wildcard_collections_from_path(
                file_path=_WildcardFile(WILDCARD_KIND, *name.split("/"), content=content), root_path=root))
        return dict(WildcardTree.from_map(path_to_file).map).items()


# Instances created while the folder holds the same files share one manager. Each manager's tree
# depends only on those files, so sharing is not observable, and the guest keeps one copy of them.
_SHARED_FOLDER = {"key": None, "manager": None}


async def _wildcard_manager(node_type):
    """The wildcard manager for a new instance (nodes/sampler.py __init__ makes one per instance)."""
    from dynamicprompts.wildcards import WildcardManager

    assets = sdk.ctx().assets
    try:
        names = await assets.list(WILDCARD_KIND, recursive=True)
    except PermissionError:
        raise
    except Exception as exc:  # the host has no such kind, or the listing exceeds its name limit
        return WildcardManager(root_map={"": [_WildcardFolder(node_type, problem=f"{type(exc).__name__}: {exc}")]})
    files = {}
    for name in _walk_order(names):
        files[name] = await assets.read_bytes(await assets.resolve(WILDCARD_KIND, name))
    key = tuple((name, hashlib.sha256(content).hexdigest()) for name, content in files.items())
    if _SHARED_FOLDER["key"] != key:
        _SHARED_FOLDER.update(key=key, manager=WildcardManager(root_map={"": [_WildcardFolder(node_type, files=files)]}))
    return _SHARED_FOLDER["manager"]


# ---------------------------------------------------------------- per-node instances
def _no_host_wildcard_folder(self):
    return None  # the host file system lookup; _sampler_instance sets the wildcard manager instead


def _guest_class(original):
    # A subclass of the original V1 class (not of a V3 node) with the same name, so any message that
    # names the instance's class reads as before.
    return type(original.__name__, (original,), {"_find_wildcards_folder": _no_host_wildcard_folder,
                                                  "__qualname__": original.__qualname__})


_GUEST_CLASSES = {
    "DPRandomGenerator": _guest_class(_random.DPRandomGenerator),
    "DPCombinatorialGenerator": _guest_class(_combinatorial.DPCombinatorialGenerator),
}
_INSTANCES = {}  # (node id, node type) -> original instance, as Core's object cache keys them


async def _sampler_instance(node_type):
    key = (await sdk.ctx().graph.current_node_id(), node_type)
    instance = _INSTANCES.get(key)
    if instance is None:
        instance = _GUEST_CLASSES[node_type]()
        instance._wildcard_manager = await _wildcard_manager(node_type)
        _INSTANCES[key] = instance
    return instance


# ---------------------------------------------------------------- converted nodes
class DPRandomGenerator(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "graph")

    @classmethod
    def define_schema(cls):
        return _sampler_schema("DPRandomGenerator", "Random Prompts")

    @classmethod
    def fingerprint_inputs(cls, text=None, seed=None, autorefresh=None):
        return _sampler.DPAbstractSamplerNode.IS_CHANGED(text, seed, autorefresh)

    @classmethod
    async def execute(cls, text, seed, autorefresh):
        instance = await _sampler_instance("DPRandomGenerator")
        return io.NodeOutput(*instance.get_prompt(text, seed, autorefresh))


class DPCombinatorialGenerator(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "graph")

    @classmethod
    def define_schema(cls):
        return _sampler_schema("DPCombinatorialGenerator", "Combinatorial Prompts")

    @classmethod
    def fingerprint_inputs(cls, text=None, seed=None, autorefresh=None):
        return _sampler.DPAbstractSamplerNode.IS_CHANGED(text, seed, autorefresh)

    @classmethod
    async def execute(cls, text, seed, autorefresh):
        instance = await _sampler_instance("DPCombinatorialGenerator")
        return io.NodeOutput(*instance.get_prompt(text, seed, autorefresh))


class DPJinja(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        # nodes/generator.py DPGeneratorNode: INPUT_TYPES, RETURN_TYPES and CATEGORY.
        return io.Schema(
            node_id="DPJinja",
            display_name="Jinja2 Templates",
            category="Dynamic Prompts",
            inputs=[
                io.String.Input("text", multiline=True),
                io.Combo.Input("autorefresh", options=["Yes", "No"]),
            ],
            outputs=[io.String.Output()],
        )

    @classmethod
    def fingerprint_inputs(cls, text=None, autorefresh=None):
        return _generator.DPGeneratorNode.IS_CHANGED(text, autorefresh)

    @classmethod
    async def execute(cls, text, autorefresh):
        return io.NodeOutput(*_jinja.DPJinja().get_prompt(text, autorefresh))


class DPOutput(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        # nodes/output_node.py OutputString: one STRING input with no options, no outputs, an output node.
        return io.Schema(
            node_id="DPOutput",
            display_name="OutputString",
            category="utils",
            inputs=[io.String.Input("text", multiline=None)],
            outputs=[],
            is_output_node=True,
        )

    @classmethod
    async def execute(cls, text):
        # Core calls a V1 node's FUNCTION with its inputs as keywords: output_string(text=...).
        return _output_node.OutputString().output_string(text=text)


# ---------------------------------------------------------------- refused nodes
class DPMagicPrompt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return _sampler_schema("DPMagicPrompt", "Magic Prompt")

    @classmethod
    def validate_inputs(cls, text=None, seed=None, autorefresh=None):
        # Naming the inputs makes Core show this refusal at queue time instead of checking them.
        return MAGIC_PROMPT_REFUSAL

    @classmethod
    async def execute(cls, text=None, seed=None, autorefresh=None):
        raise NotConvertedError(MAGIC_PROMPT_REFUSAL)


class DPFeelingLucky(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return _sampler_schema("DPFeelingLucky", "I'm Feeling Lucky")

    @classmethod
    def validate_inputs(cls, text=None, seed=None, autorefresh=None):
        # Naming the inputs makes Core show this refusal at queue time instead of checking them.
        return FEELING_LUCKY_REFUSAL

    @classmethod
    async def execute(cls, text=None, seed=None, autorefresh=None):
        raise NotConvertedError(FEELING_LUCKY_REFUSAL)


# Same ids, order and display names as the original nodes/__init__.py.
NODE_CLASS_MAPPINGS = {
    "DPRandomGenerator": DPRandomGenerator,
    "DPCombinatorialGenerator": DPCombinatorialGenerator,
    "DPFeelingLucky": DPFeelingLucky,
    "DPJinja": DPJinja,
    "DPMagicPrompt": DPMagicPrompt,
    "DPOutput": DPOutput,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DPRandomGenerator": "Random Prompts",
    "DPCombinatorialGenerator": "Combinatorial Prompts",
    "DPFeelingLucky": "I'm Feeling Lucky",
    "DPJinja": "Jinja2 Templates",
    "DPMagicPrompt": "Magic Prompt",
    "DPOutput": "OutputString",
}
