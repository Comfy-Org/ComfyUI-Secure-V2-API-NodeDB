"""Pinned torch.cat pack-side; reviewed empty/single-list cardinality repairs."""
import torch
from comfy_api.latest import io,sdk
from .categories import icons
from .secure_tensors import _preflight
class CR_MakeBatchFromImageList(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Batch Images From List',display_name='🛠️ CR Batch Images From List',category=icons['Comfyroll/List/Utils'],is_input_list=True,inputs=[io.Image.Input('image_list')],outputs=[io.Image.Output(display_name='image_batch'),io.String.Output(display_name='show_help')])
    @classmethod
    async def execute(cls,image_list):
        help_url='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-binary-to-list'
        if not isinstance(image_list,(list,tuple)) or len(image_list)>64:raise ValueError('Image list batch workload exceeds bound')
        if not image_list:raise ValueError('Cannot batch an empty image list')
        if any(not isinstance(image,sdk.ImageRef) for image in image_list):raise ValueError('Image list requires typed IMAGE handles')
        if len(image_list)==1:return io.NodeOutput(image_list[0],help_url)
        images=[await image.raw() for image in image_list]
        _preflight('CR Batch Images From List',{'image_list':images})
        image=torch.cat(images,dim=0)
        return io.NodeOutput(await sdk.ImageRef.from_value(image),help_url)
NODE_CLASS_MAPPINGS={'CR Batch Images From List':CR_MakeBatchFromImageList}
NODE_DISPLAY_NAME_MAPPINGS={'CR Batch Images From List':'🛠️ CR Batch Images From List'}
