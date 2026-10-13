"""Public schema boundary; original parser implementation remains byte-identical."""
from comfy_api.latest import io
from .json_string_to_object_node import JSONStringToObjectNode as NativeJSONStringToObjectNode

class JSONStringToObjectNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='JSONStringToObjectNode', display_name='JSON String to Object',
            category='sd',
            inputs=[io.String.Input('json_string', multiline=True)],
            outputs=[io.Custom('JSON').Output(display_name='JSON')],
        )

    @classmethod
    def execute(cls, json_string):
        return io.NodeOutput(*NativeJSONStringToObjectNode().convert_string_to_json(json_string))

NODE_CLASS_MAPPINGS = {'JSONStringToObjectNode': JSONStringToObjectNode}
NODE_DISPLAY_NAME_MAPPINGS = {'JSONStringToObjectNode': 'JSON String to Object'}
