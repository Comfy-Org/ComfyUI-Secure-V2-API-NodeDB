"""Gate-only independent logical-byte oracle; no production tensor is normalized."""
from itertools import product
import torch


def storage_projection(value):
    storage = bytes(value.untyped_storage())
    itemsize = value.element_size()
    output = bytearray()
    for index in product(*(range(size) for size in value.shape)):
        element = value.storage_offset() + sum(position * stride for position, stride in zip(index, value.stride(), strict=True))
        start = element * itemsize
        output.extend(storage[start:start + itemsize])
    return bytes(output)


def run_checks(reader, fixture):
    checked = []
    signed_zero = 0

    def check(value, label):
        before = (value.dtype, tuple(value.shape), tuple(value.stride()), value.storage_offset(), bytes(value.untyped_storage()))
        expected = storage_projection(value)
        actual = reader(value)
        assert actual == expected, label
        after = (value.dtype, tuple(value.shape), tuple(value.stride()), value.storage_offset(), bytes(value.untyped_storage()))
        assert before == after, ('byte reader changed input', label)
        checked.append(label)

    for dtype in ('float16', 'bfloat16', 'float32', 'float64', 'uint8', 'int64'):
        for channels in (1, 3):
            for view in ('contiguous', 'permute', 'slice', 'transpose', 'offset', 'expand'):
                check(fixture({'fixture': 'image', 'shape': [2, 5, 7, channels], 'dtype': dtype,
                    'view': view, 'seed': 17, 'values': 'pattern'}), f'{dtype}/{channels}/{view}')
        check(fixture({'fixture': 'image', 'shape': [2, 5, 7, 3], 'dtype': dtype,
            'view': 'rgba_rgb', 'seed': 19, 'values': 'pattern'}), f'{dtype}/rgba-rgb')
        base = torch.arange(64, dtype=torch.float64).to(getattr(torch, dtype))
        singleton = base.as_strided((1, 1, 1, 1), (63, 55, 7, 35), storage_offset=3)
        check(singleton, f'{dtype}/all-singleton-stride35-offset3')
        check(torch.empty((0, 5, 7, 1), dtype=getattr(torch, dtype)), f'{dtype}/empty')
    for dtype in ('float16', 'bfloat16', 'float32', 'float64'):
        value = torch.tensor([0.0, -0.0], dtype=getattr(torch, dtype)).reshape(1, 1, 1, 2)
        check(value, f'{dtype}/signed-zero')
        raw = reader(value)
        size = value.element_size()
        assert raw[:size] != raw[size:], ('signed zero lost', dtype)
        signed_zero += 1
    assert len(checked) == 94 and signed_zero == 4
    return {'cases': len(checked), 'signed_zero_cases': signed_zero,
        'oracle': 'Independent element-index projection from original CPU storage bytes using shape/stride/storage_offset',
        'all_original_metadata_and_storage_unchanged': True, 'labels': checked,
        'scope': 'Test byte-reader logical copy only; production output comparisons still require exact original dtype/shape/stride/storage_offset before byte packing.'}
