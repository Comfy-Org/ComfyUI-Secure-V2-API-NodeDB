"""Names-only catalogues; immutable pack resources stay distinct from admitted host fonts."""
from pathlib import Path
from comfy_api.latest import io,sdk
from .categories import icons
from .secure_graphics import FONT_NAMES
from .secure_managed_image_lists import _logical,WorkloadError
from .secure_schedules import _guard

def _names(values):
    if type(values) is not list or len(values)>4096:
        raise WorkloadError('Font catalogue exceeds bounded names')
    size=0
    for name in values:
        if type(name) is not str or not name or len(name.encode('utf8'))>255 or '/' in name or '\\' in name or ':' in name or any(ord(c)<32 for c in name) or not name.lower().endswith('.ttf'):
            raise ValueError('Font catalogue requires immediate TTF basenames')
        size+=len(name.encode('utf8'))
    if size>1024*1024:raise WorkloadError('Font catalogue exceeds bounded UTF8 bytes')
    return values

def _bundled():
    # Read only the assigned immutable resource directory; retain native directory order.
    directory=Path(__file__).parent/'fonts'
    values=[]
    for scanned,entry in enumerate(directory.iterdir(),1):
        if scanned>64:raise WorkloadError('Bundled font directory exceeds bounded scan')
        if entry.name.lower().endswith('.ttf') and entry.is_file():
            if entry.name not in FONT_NAMES or entry.is_symlink():
                raise ValueError('Unexpected immutable bundled font resource')
            values.append(entry.name)
    return _names(values)

class CR_FontFileList(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('assets',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Font File List',display_name='⌨️ CR Font File List',category=icons['Comfyroll/List/IO'],inputs=[io.Combo.Input('source_folder',options=['system','Comfyroll','from folder']),io.Int.Input('start_index',default=0,min=0,max=9999),io.Int.Input('max_rows',default=1000,min=1,max=9999),io.String.Input('folder_path',default='C:\\Windows\\Fonts',multiline=False,optional=True)],outputs=[io.AnyType.Output(display_name='LIST',is_output_list=True),io.String.Output(display_name='show_help',is_output_list=False)])
    @classmethod
    async def execute(cls,source_folder,start_index,max_rows,folder_path='C:\\Windows\\Fonts'):
        _guard(dict(source_folder=source_folder,start_index=start_index,max_rows=max_rows,folder_path=folder_path))
        show_help='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-font-file-list'
        if source_folder=='system':
            file_list=_names(await sdk.ctx().assets.font_names('system'))
        elif source_folder=='Comfyroll':
            file_list=_bundled()
        elif source_folder=='from folder':
            if folder_path=='' or folder_path is None:return None
            prefix=_logical(folder_path,False)
            if len(prefix.encode('utf8'))>1024:raise WorkloadError('Font logical prefix exceeds bound')
            file_list=_names(await sdk.ctx().assets.font_names('input',prefix=prefix))
        # Unknown direct source retains the native unbound-list failure; no silent fallback.
        start_index=max(0,min(start_index,len(file_list)-1))
        end_index=min(start_index+max_rows,len(file_list))
        return io.NodeOutput(file_list[start_index:end_index],show_help)

class CR_SelectFont(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Select Font',display_name='🔤️ CR Select Font',category=icons['Comfyroll/Graphics/Text'],inputs=[io.Combo.Input('font_name',options=[],remote=io.RemoteOptions(route='/secure-nodes/fonts/system',refresh_button=True))],outputs=[io.AnyType.Output(display_name='font_name'),io.String.Output(display_name='show_help')])
    @classmethod
    def execute(cls,font_name):
        _guard(dict(font_name=font_name))
        return io.NodeOutput(font_name,'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Text-Nodes#cr-select-font')

NODE_CLASS_MAPPINGS={'CR Font File List':CR_FontFileList,'CR Select Font':CR_SelectFont}
NODE_DISPLAY_NAME_MAPPINGS={'CR Font File List':'⌨️ CR Font File List','CR Select Font':'🔤️ CR Select Font'}
