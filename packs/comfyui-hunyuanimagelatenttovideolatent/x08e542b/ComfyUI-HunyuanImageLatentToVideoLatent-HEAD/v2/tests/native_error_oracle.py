"""Disposable same-guest pristine error oracle; never a released registration."""
import torch
from comfy_api.latest import io
from ._secure_nodes import HunyuanConvertSecure
from .source_algorithm import HunyuanImageLatentToVideoLatent as Source

class NedPristineErrorOracle(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    FUNCTION='execute'

    @classmethod
    def define_schema(cls):
        schema=HunyuanConvertSecure.define_schema()
        schema.node_id='NedPristineErrorOracle'
        schema.outputs=[io.String.Output(),io.String.Output(),io.String.Output()]
        return schema

    @classmethod
    def execute(cls,**values):
        try:
            Source().run_node(**values)
        except Exception as error:
            return io.NodeOutput(type(error).__name__,str(error),str(torch.__version__))
        raise AssertionError('error oracle unexpectedly succeeded')
