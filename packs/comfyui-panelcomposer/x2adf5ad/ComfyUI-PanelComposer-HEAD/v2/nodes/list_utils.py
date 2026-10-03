"""Generic list/tuple indexing utilities for Secure Nodes V2."""

from comfy_api.latest import io


class ListGetItem(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ListGetItem",
            display_name="List Get Item",
            category="utils/list",
            inputs=[
                io.AnyType.Input("list_or_tuple"),
                io.Int.Input(
                    "index",
                    default=0,
                    min=-1_000_000,
                    max=1_000_000,
                    step=1,
                ),
            ],
            outputs=[io.AnyType.Output("item", display_name="item")],
        )

    @classmethod
    async def execute(cls, list_or_tuple, index) -> io.NodeOutput:
        try:
            length = len(list_or_tuple)
        except TypeError as exc:
            raise ValueError(
                f"List Get Item: input isn't indexable/has no length: {exc}"
            ) from exc
        if length == 0:
            raise ValueError("List Get Item: input is empty, there's no item to return.")
        clamped = max(-length, min(int(index), length - 1))
        return io.NodeOutput(list_or_tuple[clamped])


class TupleUnpack(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="TupleUnpack",
            display_name="Tuple Unpack",
            category="utils/list",
            inputs=[io.AnyType.Input("tuple_or_list")],
            outputs=[
                io.AnyType.Output("item_0", display_name="item_0"),
                io.AnyType.Output("item_1", display_name="item_1"),
                io.AnyType.Output("item_2", display_name="item_2"),
                io.AnyType.Output("item_3", display_name="item_3"),
            ],
        )

    @classmethod
    async def execute(cls, tuple_or_list) -> io.NodeOutput:
        items = (list(tuple_or_list) + [None, None, None, None])[:4]
        return io.NodeOutput(*items)


NODE_CLASS_MAPPINGS = {
    "ListGetItem": ListGetItem,
    "TupleUnpack": TupleUnpack,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ListGetItem": "List Get Item",
    "TupleUnpack": "Tuple Unpack",
}
