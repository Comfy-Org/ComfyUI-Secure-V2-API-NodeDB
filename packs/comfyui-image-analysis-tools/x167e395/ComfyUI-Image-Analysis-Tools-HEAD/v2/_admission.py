"""Explicit local workload envelope; not a kernel/physical resource profile."""
MAX_INPUT_BYTES=64*1024*1024
MAX_WORKSPACE_BYTES=192*1024*1024
MAX_OUTPUT_BYTES=64*1024*1024
MAX_KMEANS_WORK=300_000_000

async def admit(algorithm, fields):
    info=await fields['image'].describe(max_value_chars=128)
    shape=info.get('shape')
    if not isinstance(shape,(tuple,list)) or len(shape)!=4 or any(type(n) is not int for n in shape):
        raise ValueError('expected bounded BHWC image metadata')
    b,h,w,c=shape
    if not (1<=b<=4 and 1<=h<=1024 and 1<=w<=1024 and 1<=c<=4):
        raise ValueError('image dimensions exceed local workload envelope')
    # Public describe has no dtype field: reserve16bytes per input element.
    elements=b*h*w*c
    if elements*16>MAX_INPUT_BYTES:raise ValueError('projected input import exceeds64MiB')
    pixels=h*w
    # First-image copies/FFTcomplex + plotRGBA/PNG/decoded float publication.
    if elements*16+pixels*96+32*1024*1024>MAX_WORKSPACE_BYTES:
        raise ValueError('projected workspace exceeds192MiB')
    for key,value in fields.items():
        if key=='image':continue
        if type(value) is str:
            if len(value.encode('utf-8'))>128:raise ValueError('option text too large')
        elif type(value) not in (bool,int,float):raise TypeError('expected inert builtin option scalar')
        elif type(value) is int and value.bit_length()>32:raise ValueError('option integer too large')
    if 'block_size' in fields:
        block=fields['block_size']
        if type(block) not in (bool,int) or abs(block)>128:raise ValueError('block_size outside local envelope')
        # Admitted zero/negative small-domain values keep native errors/fallback.
    if algorithm=='color_harmony_analyzer':
        clusters=fields['num_clusters']
        if type(clusters) not in (bool,int) or abs(clusters)>8:raise ValueError('cluster count outside local envelope')
        if pixels*max(1,abs(clusters))*304>MAX_KMEANS_WORK:
            raise ValueError('projected KMeans work exceeds300M')

def admit_outputs(result):
    import torch
    total=0
    for value in result:
        if isinstance(value,torch.Tensor):
            count=value.numel()*value.element_size()
            if value.ndim!=4 or value.shape[-1]!=3 or count>MAX_OUTPUT_BYTES:
                raise ValueError('image publication exceeds local envelope')
            total+=count
        elif type(value) is str:
            if len(value.encode('utf-8'))>65536:raise ValueError('text publication too large')
        elif type(value) not in (int,float):
            import numpy as np
            # Native FFT arithmetic returns canonical NumPy float64 values.
            # Preserve them verbatim; no arbitrary object/subclass admission.
            if type(value) is not np.float64:
                raise TypeError('unexpected source output type')
    if total>MAX_OUTPUT_BYTES:raise ValueError('aggregate image publication exceeds64MiB')
