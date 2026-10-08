"""Pinned StyleBars with bounded virtual-cubic native-transform strip rendering."""
import io as buffers
from PIL import Image
from comfy_api.latest import io
from .secure_matplot import np,plt,pil2tensor,_render_lock,_preflight as _base
from .secure_schedules import _output
from .secure_style_bars_strips import compatible,allocation_plan,add_artist
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

def _make_figure(width,height):
    # Private native PNG canvas; never select or monkeypatch the global backend.
    fig=Figure(figsize=(width/100,height/100))
    FigureCanvasAgg(fig)
    return fig,fig.subplots()

def _dispose_figure(fig):
    # Break only our private/native canvas ownership, including the retained
    # Agg pixel buffer; do not depend on delayed cyclic GC for renderer release.
    canvas=fig.canvas
    try:
        fig.clear()
    finally:
        fig.set_canvas(None)
        if canvas is not None:
            if hasattr(canvas,'renderer'):
                canvas.renderer=None
            canvas.figure=None
def _preflight(values):
    _base('CR Style Bars',values)
    width=values['width'];height=values['height'];orientation=values['orientation']
    # Source flattens one HxW zeros input through meshgrid; TWO grids and
    # colors/math/imshow/resample buffers need cubic cell budgeting.
    cells=max(0,height)*max(0,width)**2 if orientation=='vertical' else max(0,height)**2*max(0,width)
    if compatible(values):
        return allocation_plan(width,height,orientation=='vertical')
    if cells*128+max(0,width)*max(0,height)*96>128*1024*1024:
        raise ValueError('Pinned cubic StyleBars grid workload exceeds bound; native strip contract unavailable')
    return None

class CR_StyleBars(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Style Bars',display_name='🟪 CR Style Bars',category='🧩 Comfyroll Studio/👾 Graphics/🌈 Pattern',inputs=[io.Combo.Input('mode',options=['color bars', 'sin wave', 'gradient bars']),io.Int.Input('width',default=512,min=64,max=4096),io.Int.Input('height',default=512,min=64,max=4096),io.Combo.Input('bar_style',options=['Accent', 'afmhot', 'autumn', 'binary', 'Blues', 'bone', 'BrBG', 'brg', 'BuGn', 'BuPu', 'bwr', 'cividis', 'CMRmap', 'cool', 'coolwarm', 'copper', 'cubehelix', 'Dark2', 'flag', 'gist_earth', 'gist_gray', 'gist_heat', 'gist_rainbow', 'gist_stern', 'gist_yarg', 'GnBu', 'gnuplot', 'gnuplot2', 'gray', 'Greens', 'Greys', 'hot', 'hsv', 'inferno', 'jet', 'magma', 'nipy_spectral', 'ocean', 'Oranges', 'OrRd', 'Paired', 'Pastel1', 'Pastel2', 'pink', 'PiYG', 'plasma', 'PRGn', 'prism', 'PuBu', 'PuBuGn', 'PuOr', 'PuRd', 'Purples', 'rainbow', 'RdBu', 'RdGy', 'RdPu', 'RdYlBu', 'RdYlGn', 'Reds', 'seismic', 'Set1', 'Set2', 'Set3', 'Spectral', 'spring', 'summer', 'tab10', 'tab20', 'tab20b', 'tab20c', 'terrain', 'turbo', 'twilight', 'twilight_shifted', 'viridis', 'winter', 'Wistia', 'YlGn', 'YlGnBu', 'YlOrBr', 'YlOrRd']),io.Combo.Input('orientation',options=['vertical', 'horizontal']),io.Int.Input('bar_frequency',default=5,min=1,max=200,step=1)],outputs=[io.Image.Output(display_name='IMAGE'),io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, mode, width, height, bar_style, orientation, bar_frequency):
        plan=_preflight({'mode': mode, 'width': width, 'height': height, 'bar_style': bar_style, 'orientation': orientation, 'bar_frequency': bar_frequency})
        if plan is not None:
            with _render_lock:
                fig=None
                try:
                    axis=np.linspace(0,1,width if orientation=='vertical' else height)
                    if mode=='color bars':
                        values=axis//(1/bar_frequency)%2
                    elif mode=='sin wave':
                        values=np.sin(2*np.pi*bar_frequency*axis)
                    else:
                        values=axis*bar_frequency*2%2
                    fig,ax=_make_figure(width,height)
                    add_artist(ax,values,orientation=='vertical',plan,bar_style)
                    ax.axis('off')
                    fig.tight_layout(pad=0,w_pad=0,h_pad=0)
                    ax.autoscale(tight=True)
                    with buffers.BytesIO() as img_buf:
                        fig.savefig(img_buf,format='png')
                        with Image.open(img_buf) as img:
                            image_out=pil2tensor(img.convert('RGB'))
                    return _output((image_out,'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes#cr-style-bars'))
                finally:
                    if fig is not None:
                        _dispose_figure(fig)
        with _render_lock:
            fig=None
            try:
                if orientation == 'vertical':
                    x = np.linspace(0, 1, width)
                    y = np.zeros((height, width))
                elif orientation == 'horizontal':
                    x = np.zeros((height, width))
                    y = np.linspace(0, 1, height)
                X, Y = np.meshgrid(x, y)
                if mode == 'color bars':
                    bar_width = 1 / bar_frequency
                    if orientation == 'vertical':
                        colors = X // bar_width % 2
                    elif orientation == 'horizontal':
                        colors = Y // bar_width % 2
                elif mode == 'sin wave':
                    if orientation == 'vertical':
                        colors = np.sin(2 * np.pi * bar_frequency * X)
                    elif orientation == 'horizontal':
                        colors = np.sin(2 * np.pi * bar_frequency * Y)
                elif mode == 'gradient bars':
                    if orientation == 'vertical':
                        colors = X * bar_frequency * 2 % 2
                    elif orientation == 'horizontal':
                        colors = Y * bar_frequency * 2 % 2
                fig, ax = plt.subplots(figsize=(width / 100, height / 100))
                ax.imshow(colors, cmap=bar_style, aspect='auto')
                plt.axis('off')
                plt.tight_layout(pad=0, w_pad=0, h_pad=0)
                plt.autoscale(tight=True)
                img_buf = buffers.BytesIO()
                plt.savefig(img_buf, format='png')
                img = Image.open(img_buf)
                image_out = pil2tensor(img.convert('RGB'))
                show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pattern-Nodes#cr-style-bars'
                return _output((image_out, show_help))
            finally:
                if fig is not None:
                    plt.close(fig)
                    _dispose_figure(fig)

NODE_CLASS_MAPPINGS={'CR Style Bars':CR_StyleBars}
NODE_DISPLAY_NAME_MAPPINGS={'CR Style Bars':'🟪 CR Style Bars'}
