"""Pinned native schemas and algorithms through the actual value-mode SDK."""
import json
from pathlib import Path
from comfy_api.latest import io, ComfyExtension
SCHEMAS = json.loads(Path(__file__).with_name('_schemas.json').read_text())
KINDS = {'IMAGE': io.Image, 'MASK': io.Mask, 'LATENT': io.Latent, 'INT': io.Int, 'FLOAT': io.Float, 'STRING': io.String, 'BOOLEAN': io.Boolean}

def kind(name):
    return KINDS[name] if name in KINDS else io.Custom(name)

def schema(node_id):
    record = SCHEMAS[node_id]
    inputs = []
    for group, fields in record['inputs'].items():
        for name, spec in fields.items():
            settings = dict(spec[1] if len(spec) > 1 else {})
            settings['optional'] = group == 'optional'
            if isinstance(spec[0], list):
                inputs.append(io.Combo.Input(name, options=spec[0], **settings))
            else:
                inputs.append(kind(spec[0]).Input(name, **settings))
    outputs = []
    for i, output_type in enumerate(record['return_types']):
        names, lists = (record['return_names'], record['output_is_list'])
        settings = dict(id=f'output_{i}', display_name=names[i] if names else None, is_output_list=bool(lists and lists[i]))
        if isinstance(output_type, list):
            outputs.append(io.Combo.Output(options=output_type, **settings))
        else:
            outputs.append(kind(output_type).Output(**settings))
    return io.Schema(node_id=node_id, display_name=record['display_name'], category=record['category'], inputs=inputs, outputs=outputs, is_output_node=record['output_node'], enable_expand=(node_id == 'ExecuteAllControlNetPreprocessors'))


_EDGE_NODE_IDS = ('PiDiNetPreprocessor', 'Scribble_PiDiNet_Preprocessor', 'M-LSDPreprocessor')
_LINEART_NODE_IDS = ('LineArtPreprocessor', 'AnimeLineArtPreprocessor')
_POSE_NODE_IDS = ('FacialPartColoringFromPoseKps', 'UpperBodyTrackingFromPoseKps', 'RenderPeopleKps', 'RenderAnimalKps')

class _Node(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return schema(cls.NODE_ID)

    @classmethod
    async def execute(cls, **values):
        if cls.NODE_ID == 'ExecuteAllControlNetPreprocessors':
            from ._execute_all import expand_all
            return io.NodeOutput.from_dict(expand_all(**values))
        if cls.NODE_ID == 'AIO_Preprocessor':
            from . import _aio
            preprocessor = values['preprocessor']
            image = values['image']
            if preprocessor == 'none':
                return io.NodeOutput(image)
            aux_class = {key: NODE_CLASS_MAPPINGS[key] for key in _aio.AUX_NODE_IDS}[preprocessor]
            params = _aio.parameters(SCHEMAS[preprocessor]['inputs'], image, values.get('resolution', 512))
            return await aux_class.execute(**params)
        if cls.NODE_ID == 'DepthAnythingV2Preprocessor':
            from . import _depth_v2_managed
            return io.NodeOutput(*await _depth_v2_managed.execute(**values))
        if cls.NODE_ID == 'DepthAnythingPreprocessor':
            from . import _modern_depth_anything
            return io.NodeOutput(*await _modern_depth_anything.execute(**values))
        if cls.NODE_ID in ('Zoe-DepthMapPreprocessor', 'Zoe_DepthAnythingPreprocessor'):
            from . import _modern_zoe
            return io.NodeOutput(*await _modern_zoe.execute(cls.NODE_ID, **values))
        if cls.NODE_ID in ('OneFormer-COCO-SemSegPreprocessor', 'OneFormer-ADE20K-SemSegPreprocessor'):
            from . import _modern_oneformer
            return io.NodeOutput(*await _modern_oneformer.execute(cls.NODE_ID, **values))
        if cls.NODE_ID == 'SAMPreprocessor':
            from . import _modern_sam
            return io.NodeOutput(*await _modern_sam.execute(**values))
        if cls.NODE_ID == 'MediaPipe-FaceMeshPreprocessor':
            from . import _facemesh
            return io.NodeOutput(*await _facemesh.execute(**values))
        if cls.NODE_ID == 'DiffusionEdge_Preprocessor':
            from . import _diffusionedge
            return io.NodeOutput(*await _diffusionedge.execute(**values))
        if cls.NODE_ID == 'Unimatch_OptFlowPreprocessor':
            from . import _unimatch
            return io.NodeOutput(*await _unimatch.execute(**values))
        if cls.NODE_ID == 'MeshGraphormer+ImpactDetector-DepthMapPreprocessor':
            from . import _meshgraphormer
            return io.NodeOutput(*await _meshgraphormer.execute_impact(**values))
        if cls.NODE_ID == 'MeshGraphormer-DepthMapPreprocessor':
            from . import _meshgraphormer
            return io.NodeOutput(*await _meshgraphormer.execute(**values))
        if cls.NODE_ID in ('Metric3D-DepthMapPreprocessor', 'Metric3D-NormalMapPreprocessor'):
            from . import _metric3d
            return io.NodeOutput(*await _metric3d.execute(cls.NODE_ID, **values))
        if cls.NODE_ID in ('UniFormer-SemSegPreprocessor', 'SemSegPreprocessor'):
            from . import _uniformer
            return io.NodeOutput(*await _uniformer.execute(**values))
        if cls.NODE_ID == 'DensePosePreprocessor':
            from . import _densepose
            return io.NodeOutput(*await _densepose.execute(**values))
        if cls.NODE_ID == 'OpenposePreprocessor':
            from . import _openpose
            return io.NodeOutput.from_dict(await _openpose.execute(**values))
        if cls.NODE_ID in ('DWPreprocessor', 'AnimalPosePreprocessor'):
            from . import _dwpose
            return io.NodeOutput.from_dict(await _dwpose.execute(cls.NODE_ID, **values))
        if cls.NODE_ID == 'LeReS-DepthMapPreprocessor':
            from . import _leres
            return io.NodeOutput(*await _leres.execute(**values))
        if cls.NODE_ID == 'DSINE-NormalMapPreprocessor':
            from . import _dsine
            return io.NodeOutput(*await _dsine.execute(**values))
        if cls.NODE_ID in ('MiDaS-DepthMapPreprocessor', 'MiDaS-NormalMapPreprocessor'):
            from . import _midas
            return io.NodeOutput(*await _midas.execute(cls.NODE_ID, **values))
        if cls.NODE_ID == 'BAE-NormalMapPreprocessor':
            from . import _normalbae
            return io.NodeOutput(await _normalbae.execute(**values))
        if cls.NODE_ID == 'AnimeFace_SemSegPreprocessor':
            from . import _anime_face
            return io.NodeOutput(*await _anime_face.execute(**values))
        if cls.NODE_ID == 'AnyLineArtPreprocessor_aux':
            from . import _anyline
            return io.NodeOutput(await _anyline.execute(**values))
        if cls.NODE_ID == 'SavePoseKpsAsJsonFile':
            from . import _pose_output
            await _pose_output.execute(**values)
            return io.NodeOutput()
        if cls.NODE_ID == 'MaskOptFlow':
            from . import _flow_mask
            mask = values['mask']
            return io.NodeOutput(*_flow_mask.MaskOptFlow().mask_opt_flow(values['optical_flow'], mask))
        if cls.NODE_ID == 'Manga2Anime_LineArt_Preprocessor':
            from . import _manga
            return io.NodeOutput(await _manga.execute(**values))
        if cls.NODE_ID in _LINEART_NODE_IDS:
            from . import _lineart
            return io.NodeOutput(await _lineart.execute(cls.NODE_ID, **values))
        if cls.NODE_ID == 'TEEDPreprocessor':
            from . import _teed
            return io.NodeOutput(await _teed.execute(**values))
        if cls.NODE_ID in _POSE_NODE_IDS:
            from . import _pose_algorithms
            legacy = _pose_algorithms.IMPLEMENTED[cls.NODE_ID]
            return io.NodeOutput(*getattr(legacy(), legacy.FUNCTION)(**values))
        if cls.NODE_ID in _EDGE_NODE_IDS:
            from . import _edges
            return io.NodeOutput(await _edges.execute(cls.NODE_ID, **values))
        if cls.NODE_ID in ('HEDPreprocessor', 'FakeScribblePreprocessor'):
            from . import _hed
            return io.NodeOutput(await _hed.execute(cls.NODE_ID, **values))
        if cls.NODE_ID == 'ControlNetPreprocessorSelector':
            from ._selector_native import ControlNetPreprocessorSelector
            return io.NodeOutput(*ControlNetPreprocessorSelector().get_preprocessor(**values))
        from . import _algorithms
        legacy = _algorithms.IMPLEMENTED.get(cls.NODE_ID)
        if legacy is None:
            raise RuntimeError(cls.NODE_ID + ': model/asset port remains pending; no support claim')
        return io.NodeOutput(*getattr(legacy(), legacy.FUNCTION)(**values))
from comfy_api.latest import sdk
_DECLARATIONS = json.loads(Path(__file__).with_name('secure-nodes.json').read_text())['nodes']
NODE_CLASS_MAPPINGS = {}
for node_id in SCHEMAS:
    declaration = _DECLARATIONS[node_id]
    NODE_CLASS_MAPPINGS[node_id] = type(node_id.replace('-', '_').replace('+', '_'), (_Node,), {'NODE_ID': node_id, '__module__': __name__, 'SDK_PERMISSIONS': tuple(declaration.get('permissions', ())), 'SDK_REQUIRED_WEIGHTS': tuple((sdk.HuggingFaceWeight(**record) for record in declaration.get('required_weights', ())))})
NODE_DISPLAY_NAME_MAPPINGS = {node_id: row['display_name'] for node_id, row in SCHEMAS.items()}
globals().update({cls.__name__: cls for cls in NODE_CLASS_MAPPINGS.values()})

class Extension(ComfyExtension):

    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())

async def comfy_entrypoint():
    return Extension()
