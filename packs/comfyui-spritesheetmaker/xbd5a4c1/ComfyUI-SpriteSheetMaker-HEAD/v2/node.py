"""Managed-directory SpriteSheetMaker; grid composition remains pack-owned."""
import io as bytes_io

from comfy_api.latest import io, sdk

MAX_FILES = 128
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_ENCODED_BYTES = 64 * 1024 * 1024
MAX_OUTPUT_BYTES = 32 * 1024 * 1024
MAX_OWNED_BYTES = 128 * 1024 * 1024
MAX_AXIS = 4096
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}


def logical_directory(value):
    if (type(value) is not str or len(value.encode('utf-8')) > 1024
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or any(c in value for c in '\\%:') or value.startswith('/')
            or any(part in {'.', '..', ''} for part in value.split('/') if value)):
        raise ValueError('bounded relative managed directory required')
    return value


def axis(value):
    if type(value) is not int or abs(value) > MAX_AXIS:
        raise ValueError('grid axis exceeds bounded integer profile')
    return value


def image_names(directory, names):
    if type(names) is not list or len(names) > 4096:
        raise ValueError('managed catalogue exceeds bound')
    prefix = directory + '/' if directory else ''
    selected = []
    for name in names:
        if type(name) is not str or not name.startswith(prefix):
            raise ValueError('managed catalogue returned a foreign name')
        basename = name[len(prefix):]
        if not basename or '/' in basename or logical_directory(name) != name:
            raise ValueError('managed catalogue returned a non-immediate name')
        suffix = '.' + basename.rsplit('.', 1)[-1].lower() if '.' in basename else ''
        if suffix in IMAGE_EXTENSIONS:
            selected.append(name)
    if len(selected) > MAX_FILES:
        raise ValueError('sprite image count exceeds bound')
    return selected


async def bounded_read(assets, ref, size):
    if type(size) is not int or not 0 <= size <= MAX_FILE_BYTES:
        raise ValueError('encoded image exceeds bound')
    payload = bytearray()
    while len(payload) < size:
        count = min(1024 * 1024, size - len(payload))
        chunk = await assets.read_range(ref, len(payload), count)
        if len(chunk) != count:
            raise ValueError('managed image changed size while reading')
        payload.extend(chunk)
    tail = await assets.read_range(ref, size, 1)
    if tail or await assets.size(ref) != size:
        raise ValueError('managed image changed size while reading')
    return bytes(payload)


def ownership_plan(sizes, encoded_bytes, rows, columns):
    rows, columns = axis(rows), axis(columns)
    if len(sizes) > MAX_FILES or encoded_bytes > MAX_ENCODED_BYTES:
        raise ValueError('sprite input exceeds cumulative bound')
    if any(type(w) is not int or type(h) is not int or w < 0 or h < 0 for w, h in sizes):
        raise ValueError('invalid image geometry')
    if not sizes:
        raise ValueError('No image files found in the specified folder.')
    width = max(w for w, h in sizes)
    height = max(h for w, h in sizes)
    pixels = width * max(columns, 0) * height * max(rows, 0)
    output = pixels * 12
    projected = 2 * encoded_bytes + 4 * sum(w * h for w, h in sizes) + 60 * pixels + 8 * 1024 * 1024
    if output > MAX_OUTPUT_BYTES or projected > MAX_OWNED_BYTES:
        raise ValueError('sprite projected ownership exceeds bound')
    return {'output_bytes': output, 'projected_bytes': projected}


class ImageGridNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'raw')

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='SpriteSheetMaker', category='ImageGrid',
            inputs=[io.Combo.Input('images_directory', options=[], remote=io.RemoteOptions(
                '/secure-nodes/assets/input?kind=directory', True, initial_selection='first')),
                io.Int.Input('row_count', default=2), io.Int.Input('column_count', default=2)],
            outputs=[io.Image.Output('sprite_image')])

    @classmethod
    async def execute(cls, images_directory, row_count, column_count):
        directory = logical_directory(images_directory)
        rows, columns = axis(row_count), axis(column_count)
        assets = sdk.ctx().assets
        names = image_names(directory, await assets.list('input', prefix=directory, recursive=False))
        if not names:
            raise ValueError('No image files found in the specified folder.')
        refs, lengths = [], []
        for name in names:
            ref = await assets.resolve('input', name)
            length = await assets.size(ref)
            if type(length) is not int or not 0 <= length <= MAX_FILE_BYTES:
                raise ValueError('encoded image exceeds bound')
            refs.append(ref)
            lengths.append(length)
        encoded_total = sum(lengths)
        if encoded_total > MAX_ENCODED_BYTES:
            raise ValueError('sprite cumulative encoded bytes exceed bound')
        from PIL import Image
        images, streams = [], []
        try:
            for name, ref, length in zip(names, refs, lengths):
                stream = bytes_io.BytesIO(await bounded_read(assets, ref, length))
                streams.append(stream)
                image = Image.open(stream)
                images.append(image)
                if image.size != images[0].size:
                    raise ValueError(f'Size mismatch: {name.rsplit("/", 1)[-1]} has size {image.size}, expected {images[0].size}')
            ownership_plan([image.size for image in images], encoded_total, rows, columns)
            from ._grid import OriginalGrid
            import numpy as np
            import torch
            sprite = OriginalGrid().create_image_grid(images, rows, columns)
            try:
                value = np.array(sprite).astype(np.float32) / 255.0
                tensor = torch.from_numpy(value)[None,]
                return io.NodeOutput(await sdk.ImageRef.from_value(tensor))
            finally:
                sprite.close()
        finally:
            for image in images:
                image.close()
            for stream in streams:
                stream.close()
