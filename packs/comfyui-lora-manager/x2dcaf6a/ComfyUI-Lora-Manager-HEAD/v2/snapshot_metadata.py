"""Metadata-only projection of actual SDK observations for native algorithms."""
from __future__ import annotations

import json
from pathlib import Path

from .native_metadata.constants import METADATA_CATEGORIES, OVERWRITE
from .native_metadata.node_extractors import NODE_EXTRACTORS, GenericNodeExtractor
from .native_metadata.semantic_fields import UnsupportedMetadataField

CLASS_NAMES = json.loads(Path(__file__).with_name('native_class_names.json').read_text())


class TensorDescription:
    __slots__ = ('shape', 'dtype')

    def __init__(self, value):
        self.shape = tuple(value['shape'])
        self.dtype = value['dtype']


class OpaqueDescription:
    __slots__ = ('description',)

    def __init__(self, value):
        self.description = value

    def __getattr__(self, key):
        if key == 'seed' and 'seed' in self.description:
            return self.description['seed']
        raise UnsupportedMetadataField('Opaque metadata field is unavailable: ' + key)


class OwnedPrompt:
    def __init__(self, snapshot):
        self.original_prompt = snapshot['prompt']
        self.nodes = snapshot['nodes']
        self.observations = snapshot['observations']

    def get_node(self, node_id):
        return self.nodes[node_id]

    def get_parent_node_id(self, node_id):
        return self.observations[node_id].get('parent_node_id')


class Descriptions:
    def __init__(self):
        self.identities = {}

    def decode(self, value):
        if not isinstance(value, dict):
            return value
        kind = value.get('kind')
        identity = value.get('identity')
        if identity is not None and identity in self.identities:
            return self.identities[identity]
        if kind == 'tensor':
            return TensorDescription(value)
        if kind == 'opaque':
            result = OpaqueDescription(value)
        elif kind == 'dict':
            result = {self.decode(key): self.decode(item) for key, item in value['items']}
        elif kind in ('list', 'tuple'):
            items = [self.decode(item) for item in value['items']]
            result = items if kind == 'list' else tuple(items)
        else:
            raise UnsupportedMetadataField('Unknown owned observation descriptor: ' + str(kind))
        if identity is not None:
            self.identities[identity] = result
        return result


def from_snapshot(snapshot):
    descriptions = Descriptions()
    metadata = {category: {} for category in METADATA_CATEGORIES}
    metadata.update(execution_order=list(snapshot['execution_order']), current_prompt=OwnedPrompt(snapshot),
        extra_data={'extra_pnginfo': snapshot['extra_pnginfo']})
    observations = snapshot['observations']
    def apply(node_id, destination):
        row = observations[node_id]
        class_name = CLASS_NAMES.get(row['class_type'], row['class_name'])
        inputs = {name: descriptions.decode(values[0]) if values else [] for name, values in row['inputs'].items()}
        extractor = NODE_EXTRACTORS.get(class_name, GenericNodeExtractor)
        if extractor is GenericNodeExtractor:
            extractor.extract(node_id, inputs, None, destination, return_types=row['return_types'])
        else:
            extractor.extract(node_id, inputs, None, destination)
        if row.get('outputs') is not None:
            slots = row['outputs']
            # Current observation API has per-socket values. Nonuniform mapped
            # lists cannot recover native per-call tuple grouping faithfully.
            lengths = {len(values) for values in slots}
            if len(lengths) > 1:
                raise UnsupportedMetadataField('Nonuniform mapped outputs require native tuple grouping')
            outputs = [tuple(descriptions.decode(values[index]) for values in slots)
                       for index in range(next(iter(lengths), 0))]
            if extractor is GenericNodeExtractor:
                extractor.update(node_id, outputs, destination, return_types=row['return_types'])
            elif hasattr(extractor, 'update'):
                extractor.update(node_id, outputs, destination)
    for node_id in snapshot['execution_order']:
        apply(node_id, metadata)
    # The API supplies available actual cached inputs/outputs; native cache
    # fill does not append these nodes to the execution order.
    for node_id, row in observations.items():
        if node_id in snapshot['execution_order']:
            continue
        if not row.get('cached'):
            raise UnsupportedMetadataField('Observation is neither entered nor cached: ' + node_id)
        cached = {category: {} for category in METADATA_CATEGORIES}
        cached['current_prompt'] = metadata['current_prompt']
        apply(node_id, cached)
        disabled = snapshot['prompt'].get(node_id, {}).get('mode', 0) in (2, 4)
        for category in METADATA_CATEGORIES:
            if category == OVERWRITE and disabled:
                continue
            if node_id in cached[category] and node_id not in metadata[category]:
                metadata[category][node_id] = cached[category][node_id]
    return metadata
