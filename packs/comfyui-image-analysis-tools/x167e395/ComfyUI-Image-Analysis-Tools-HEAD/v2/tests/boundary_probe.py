"""Test-only public control; deliberately absent from release registrations."""
import importlib.util
from comfy_api.latest import io

class OutsideBoundaryProbe(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='JackOutsideAnalysisProbe',inputs=[io.String.Input('outside')],outputs=[io.String.Output()])
    @classmethod
    async def execute(cls,outside):
        failures=[]
        try:
            with open(outside,'rb') as file:file.read(1)
        except PermissionError:failures.append('read')
        spec=importlib.util.spec_from_file_location('_jack_outside_analysis',outside)
        module=importlib.util.module_from_spec(spec)
        try:spec.loader.exec_module(module)
        except PermissionError:failures.append('import')
        return io.NodeOutput(','.join(failures))

class RuntimeProbe(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='JackAnalysisRuntimeProbe',inputs=[],outputs=[io.String.Output()])
    @classmethod
    async def execute(cls):
        import importlib.metadata as metadata
        import json
        import sys
        import numpy, cv2, matplotlib, sklearn, PIL, torch, scipy
        names=('numpy','opencv-python','opencv-python-headless','matplotlib','scikit-learn','Pillow','torch','scipy')
        modules=(numpy,cv2,matplotlib,sklearn,PIL,torch,scipy)
        result={'distributions':{name:{'version':metadata.version(name),'metadata_root':str(metadata.distribution(name).locate_file(''))} for name in names},
            'module_origins':{module.__name__:module.__file__ for module in modules},'pyplot_loaded':'matplotlib.pyplot' in sys.modules}
        return io.NodeOutput(json.dumps(result))
