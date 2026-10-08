"""Render-local Agg figures: no pyplot manager/backend/rc mutation."""
from contextlib import contextmanager
from contextvars import ContextVar
import io
import math
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib import cm

_figures=ContextVar('image_analysis_figures',default=None)

@contextmanager
def scope():
    figures=[]
    token=_figures.set(figures)
    try:yield
    finally:
        for figure in figures:figure.clear()
        _figures.reset(token)

def subplots(*args,**kwargs):
    subplot_kw=kwargs.pop('subplot_kw',None)
    width,height=kwargs.get('figsize',(6,6))
    dpi=kwargs.get('dpi',100)
    if not all(type(v) in (int,float) and math.isfinite(v) and 0<v<=limit for v,limit in ((width,6),(height,6),(dpi,150))):
        raise ValueError('projected plot canvas bound')
    figures=_figures.get()
    if figures is None:raise RuntimeError('figure requires execution-local scope')
    figure=Figure(**kwargs)
    FigureCanvasAgg(figure)
    figures.append(figure)
    return figure,figure.subplots(*args,subplot_kw=subplot_kw)

def colorbar(mappable,**kwargs):return mappable.axes.figure.colorbar(mappable,**kwargs)
def close(figure):figure.clear()

class PNGBuffer(io.BytesIO):
    def write(self,value):
        if self.tell()+len(value)>16*1024*1024:
            raise ValueError('projected encoded PNG publication bound')
        return super().write(value)

def save_png(figure,buffer):
    # Source controls remain PNG/150 dpi/tight/white. Fixed source labels,
    # dimensions and bounded option strings reserve a twofold tight-box margin.
    width,height=figure.get_size_inches()
    projected=math.ceil(width*150*2)*math.ceil(height*150*2)
    if projected*16>64*1024*1024:
        raise ValueError('projected plot publication bound')
    figure.savefig(buffer,format='png',dpi=150,bbox_inches='tight',facecolor='white')

def admit_png(size):
    width,height=size
    if width<=0 or height<=0 or width*height*16>64*1024*1024:
        raise ValueError('projected decoded PNG publication bound')
