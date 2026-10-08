"""Test-only public operations; absent from release registrations/manifest."""
import importlib.util
from comfy_api.latest import io

class OutsideBoundaryProbe(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='JackOutsideMathProbe',inputs=[io.String.Input('outside')],outputs=[io.String.Output()])
    @classmethod
    async def execute(cls,outside):
        failures=[]
        try:
            with open(outside,'rb') as file:file.read(1)
        except PermissionError:failures.append('read')
        spec=importlib.util.spec_from_file_location('_jack_outside_math',outside)
        module=importlib.util.module_from_spec(spec)
        try:spec.loader.exec_module(module)
        except PermissionError:failures.append('import')
        return io.NodeOutput(','.join(failures))

class RawImageProbe(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='JackMathRawProbe',inputs=[io.Image.Input('image')],outputs=[io.Int.Output()])
    @classmethod
    async def execute(cls,image):
        value=await image.raw()
        return io.NodeOutput(int(value.numel()))
