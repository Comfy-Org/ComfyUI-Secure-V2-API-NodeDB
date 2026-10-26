"""Catalogue membership with explicit Core-compatible linked-type validation.

Compatibility follows qualified Core validate_node_input's non-strict rules,
source SHA74e97925e04fff5de5e529c4246e74ef087f487e1bf8a5969b1dc76ddedf8ac2.
No host module or private SDK is imported by the pack.
"""
from comfy_api.latest import io, sdk


def compatible(received, expected):
    # Preserve Core's legacy __ne__ behavior before normal string comparisons.
    if not received != expected:
        return True
    if received == io.AnyType.io_type or expected == io.AnyType.io_type:
        return True
    if received == io.MatchType.io_type or expected == io.MatchType.io_type:
        return True
    if isinstance(received, list) and expected == io.Combo.io_type:
        return True
    if isinstance(received, list) and isinstance(expected, list):
        return any(value in expected for value in received)
    if not isinstance(received, str) or not isinstance(expected, str):
        return False
    source = {value.strip() for value in received.split(',')}
    target = {value.strip() for value in expected.split(',')}
    return io.AnyType.io_type in source or io.AnyType.io_type in target or bool(source & target)


async def checkpoint_member(value):
    if type(value) is not str:
        return "Checkpoint name must be a string"
    names = await sdk.ctx().assets.list("checkpoints")
    return True if value in names else "Checkpoint is not in the current checkpoints catalogue"


async def validate_checkpoint_input(node_class, name, value, input_types):
    # Core supplies input_types from actual linked producer RETURN_TYPES. Asking
    # for it transfers ALL linked-type checks to this function, so check every
    # declared linked input, including IMAGE and numeric links, before deferral.
    if input_types is None:
        input_types = {}
    if type(input_types) is not dict:
        return "Linked input types must be a dictionary"
    expected = {item.id: item.io_type for item in node_class.define_schema().inputs}
    for linked, received in input_types.items():
        if linked not in expected or not compatible(received, expected[linked]):
            return "Linked input type does not match the declared input: " + str(linked)
    if value is None and name in input_types:
        # A typed unresolved graph link is not a literal None. The execute
        # method must recheck the resolved value against the current catalogue.
        return True
    return await checkpoint_member(value)


async def require_checkpoint(value):
    result = await checkpoint_member(value)
    if result is not True:
        raise ValueError(result)
