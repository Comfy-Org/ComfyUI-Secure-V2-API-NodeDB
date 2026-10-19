from comfy_api.latest import io
from ._runtime import SCHEMAS, schema_for, execute_node, validate

class ttN_tinyLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN tinyLoader')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN tinyLoader', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN tinyLoader', kwargs)

class ttN_conditioning(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets')
    @classmethod
    def define_schema(cls):return schema_for('ttN conditioning')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN conditioning', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN conditioning', kwargs)

class ttN_KSampler_v2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'sample', 'output', 'ui', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN KSampler_v2')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN KSampler_v2', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN KSampler_v2', kwargs)

class ttN_pipeLoader_v2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeLoader_v2')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeLoader_v2', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeLoader_v2', kwargs)

class ttN_pipeKSampler_v2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'sample', 'output', 'ui', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeKSampler_v2')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeKSampler_v2', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeKSampler_v2', kwargs)

class ttN_pipeKSamplerAdvanced_v2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'sample', 'output', 'ui', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeKSamplerAdvanced_v2')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeKSamplerAdvanced_v2', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeKSamplerAdvanced_v2', kwargs)

class ttN_pipeLoaderSDXL_v2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeLoaderSDXL_v2')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeLoaderSDXL_v2', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeLoaderSDXL_v2', kwargs)

class ttN_pipeKSamplerSDXL_v2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'sample', 'output', 'ui', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeKSamplerSDXL_v2')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeKSamplerSDXL_v2', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeKSamplerSDXL_v2', kwargs)

class ttN_advanced_XYPlot(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN advanced xyPlot')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN advanced xyPlot', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN advanced xyPlot', kwargs)

class ttN_advPlot_images(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'graph.expand', 'graph.expand.upstream', 'graph.input_options', 'graph.expand.configuration', 'assets', 'output', 'ui', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN advPlot images')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN advPlot images', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN advPlot images', kwargs)

_PLOT_BASE=SCHEMAS['ttN advPlot images']['id']
_CELL=io.Custom('TTN_PLOT_CELL')
_PLANE=io.Custom('TTN_PLOT_PLANE')

class ttN_PlotCell(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id=_PLOT_BASE+' Cell',category='ttN/internal',is_input_list=True,
            inputs=[io.Image.Input('image'),_CELL.Input('prior',optional=True)],
            outputs=[_CELL.Output()])
    @classmethod
    async def execute(cls,image,prior=None):
        from ._plot import convert_cell
        return io.NodeOutput(await convert_cell(image))

class ttN_PlotPlane(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('raw','assets')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id=_PLOT_BASE+' Plane',category='ttN/internal',is_input_list=True,
            inputs=[io.AnyType.Input('cells'),io.String.Input('metadata'),
                    _PLANE.Input('previous',optional=True)],outputs=[_PLANE.Output()])
    @classmethod
    async def execute(cls,cells,metadata,previous=None):
        from ._plot import render_plane
        return io.NodeOutput(await render_plane(cells,metadata,previous))

class ttN_PlotFinish(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('raw','assets','output','ui')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id=_PLOT_BASE+' Finish',category='ttN/internal',is_input_list=True,
            inputs=[io.AnyType.Input('planes'),io.String.Input('metadata')],
            outputs=[io.Image.Output(),io.Image.Output()])
    @classmethod
    async def execute(cls,planes,metadata):
        from ._plot import finish
        return await finish(planes,metadata)

class ttN_PlotFailure(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id=_PLOT_BASE+' Failure',category='ttN/internal',is_input_list=True,
            inputs=[io.String.Input('metadata'),_CELL.Input('prior'),
                    _PLANE.Input('plane',optional=True)],outputs=[io.Image.Output(),io.Image.Output()])
    @classmethod
    async def execute(cls,metadata,prior,plane=None):
        import json
        error=json.loads(metadata[0])
        kind={'KeyError':KeyError,'ValueError':ValueError,'TypeError':TypeError,'OverflowError':OverflowError}[error['kind']]
        raise kind(*error['args'])

class ttN_advPlot_range(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN advPlot range')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN advPlot range', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN advPlot range', kwargs)

class ttN_advPlot_string(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN advPlot string')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN advPlot string', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN advPlot string', kwargs)

class ttN_advPlot_combo(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'graph.input_options', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN advPlot combo')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN advPlot combo', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN advPlot combo', kwargs)

class ttN_advPlot_merge(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN advPlot merge')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN advPlot merge', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN advPlot merge', kwargs)

class ttN_pipe_EDIT(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeEDIT')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeEDIT', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeEDIT', kwargs)

class ttN_pipe_2BASIC(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN pipe2BASIC')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipe2BASIC', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipe2BASIC', kwargs)

class ttN_pipe_2DETAILER(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN pipe2DETAILER')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipe2DETAILER', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipe2DETAILER', kwargs)

class ttN_pipeEncodeConcat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets')
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeEncodeConcat')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeEncodeConcat', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeEncodeConcat', kwargs)

class ttN_pipeLoraStack(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets',)
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeLoraStack')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeLoraStack', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeLoraStack', kwargs)

class ttN_multiModelMerge(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN multiModelMerge')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN multiModelMerge', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN multiModelMerge', kwargs)

class ttN_debugInput(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN debugInput')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN debugInput', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN debugInput', kwargs)

class ttN_text(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN text')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN text', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN text', kwargs)

class ttN_textDebug(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('graph.prompt_json', 'graph')
    @classmethod
    def define_schema(cls):return schema_for('ttN textDebug')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN textDebug', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN textDebug', kwargs)

    @classmethod
    def fingerprint_inputs(cls, execute="On Change", **kwargs):return float("nan") if execute=="Always" else None

class ttN_concat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN concat')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN concat', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN concat', kwargs)

class ttN_text3BOX_3WAYconcat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN text3BOX_3WAYconcat')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN text3BOX_3WAYconcat', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN text3BOX_3WAYconcat', kwargs)

class ttN_text7BOX_concat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN text7BOX_concat')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN text7BOX_concat', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN text7BOX_concat', kwargs)

class ttN_textCycleLine(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN textCycleLine')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN textCycleLine', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN textCycleLine', kwargs)

class ttN_textOUPUT(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'output', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN textOutput')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN textOutput', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN textOutput', kwargs)

class ttN_imageOUPUT(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'output', 'ui', 'graph.prompt_json', 'output.overwrite')
    @classmethod
    def define_schema(cls):return schema_for('ttN imageOutput')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN imageOutput', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN imageOutput', kwargs)

class ttN_imageREMBG(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'output', 'ui', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN imageREMBG')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN imageREMBG', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN imageREMBG', kwargs)

class ttN_modelScale(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'output', 'ui', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN hiresfixScale')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN hiresfixScale', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN hiresfixScale', kwargs)

class ttN_INT(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN int')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN int', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN int', kwargs)

class ttN_FLOAT(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN float')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN float', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN float', kwargs)

class ttN_SEED(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN seed')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN seed', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN seed', kwargs)

class ttN_XYPlot(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN xyPlot')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN xyPlot', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN xyPlot', kwargs)

class ttN_pipe_IN(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeIN')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeIN', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeIN', kwargs)

class ttN_pipe_OUT(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeOUT')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeOUT', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeOUT', kwargs)

class ttN_TSC_pipeLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeLoader')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeLoader', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeLoader', kwargs)

class ttN_TSC_pipeKSampler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'sample', 'output', 'ui', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeKSampler')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeKSampler', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeKSampler', kwargs)

class ttN_pipeKSamplerAdvanced(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'sample', 'output', 'ui', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeKSamplerAdvanced')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeKSamplerAdvanced', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeKSamplerAdvanced', kwargs)

class ttN_pipeLoaderSDXL(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeLoaderSDXL')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeLoaderSDXL', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeLoaderSDXL', kwargs)

class ttN_pipeKSamplerSDXL(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'sample', 'output', 'ui', 'graph.prompt_json')
    @classmethod
    def define_schema(cls):return schema_for('ttN pipeKSamplerSDXL')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN pipeKSamplerSDXL', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN pipeKSamplerSDXL', kwargs)

class ttN_compareInput(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):return schema_for('ttN compareInput')
    @classmethod
    async def execute(cls, **kwargs):return await execute_node(cls, 'ttN compareInput', kwargs)
    @classmethod
    def validate_inputs(cls, **kwargs):return validate('ttN compareInput', kwargs)

NODE_CLASS_MAPPINGS = {
    'ttN_tinyLoader_c80deffd6042c4a897866d79': ttN_tinyLoader,
    'ttN_conditioning_00ee7fb58d6217b61d28ffda': ttN_conditioning,
    'ttN_KSampler_v2_b96111c6c532990ae4d2a22d': ttN_KSampler_v2,
    'ttN_pipeLoader_v2_58246dfb20bdc0271e2f0da1': ttN_pipeLoader_v2,
    'ttN_pipeKSampler_v2_384e6bf1e6bdf16dab3403be': ttN_pipeKSampler_v2,
    'ttN_pipeKSamplerAdvanced_v2_0bde6a2fc6fd2b1f3148c941': ttN_pipeKSamplerAdvanced_v2,
    'ttN_pipeLoaderSDXL_v2_2315fee49000ac73ed2b4205': ttN_pipeLoaderSDXL_v2,
    'ttN_pipeKSamplerSDXL_v2_d7a835b65f8b639485e83a20': ttN_pipeKSamplerSDXL_v2,
    'ttN_advanced_xyPlot_5660b5693fff3e6a7b6ac6be': ttN_advanced_XYPlot,
    'ttN_advPlot_images_9464f7f009faedbbe64f8aee': ttN_advPlot_images,
    'ttN_advPlot_range_ae4d61a6cbdb5c6824e46a98': ttN_advPlot_range,
    'ttN_advPlot_string_abb8997c9782d24ce63175fb': ttN_advPlot_string,
    'ttN_advPlot_combo_2175b2f2a4848cce66909124': ttN_advPlot_combo,
    'ttN_advPlot_merge_174e015dbe69c2712c571e31': ttN_advPlot_merge,
    'ttN_pipeEDIT_aa5a200004e9fb4314a1b528': ttN_pipe_EDIT,
    'ttN_pipe2BASIC_748c46ff86c489ba345bbb37': ttN_pipe_2BASIC,
    'ttN_pipe2DETAILER_fb799f9f4e6a3a0b893bacef': ttN_pipe_2DETAILER,
    'ttN_pipeEncodeConcat_7974130fa1ef7a3d6966bb0a': ttN_pipeEncodeConcat,
    'ttN_pipeLoraStack_2ec4cdc8dd3715945346a19e': ttN_pipeLoraStack,
    'ttN_multiModelMerge_9930284c5606dcc14e190be2': ttN_multiModelMerge,
    'ttN_debugInput_b1bdfd3890f7007c8f93b9a5': ttN_debugInput,
    'ttN_text_17f67ffa52c37f580bb94011': ttN_text,
    'ttN_textDebug_0be2c3c83aa3a0e9be121654': ttN_textDebug,
    'ttN_concat_98a12dae0cccc980d9c7b338': ttN_concat,
    'ttN_text3BOX_3WAYconcat_d6bfacdd1e94a341253109a6': ttN_text3BOX_3WAYconcat,
    'ttN_text7BOX_concat_e768585a58ce525b0095c15f': ttN_text7BOX_concat,
    'ttN_textCycleLine_07efecfd0109e56a0112fcc3': ttN_textCycleLine,
    'ttN_textOutput_561c7568d7a8609efb4c9c40': ttN_textOUPUT,
    'ttN_imageOutput_9d7e52569d2d64b9e9e58352': ttN_imageOUPUT,
    'ttN_imageREMBG_d75ef8a3e919f3bfc66f9795': ttN_imageREMBG,
    'ttN_hiresfixScale_30b24f506f9af9321f1ae901': ttN_modelScale,
    'ttN_int_3b12e0212a0b8b0be03416b7': ttN_INT,
    'ttN_float_135744bce0eed7150cbe9f22': ttN_FLOAT,
    'ttN_seed_0fffce90a3d1a81a1e11489e': ttN_SEED,
    'ttN_xyPlot_544de9d62d33978b709f2eee': ttN_XYPlot,
    'ttN_pipeIN_0f4a584cca428eb3e2db18ec': ttN_pipe_IN,
    'ttN_pipeOUT_ddb0379afad4f093ff872f5d': ttN_pipe_OUT,
    'ttN_pipeLoader_b6c51abd124a0a79c7ba8c93': ttN_TSC_pipeLoader,
    'ttN_pipeKSampler_aab002d291a2f516b9550bf3': ttN_TSC_pipeKSampler,
    'ttN_pipeKSamplerAdvanced_ba5a6ba9874ab2faac51c05a': ttN_pipeKSamplerAdvanced,
    'ttN_pipeLoaderSDXL_48a01436a42cd167b68fb47f': ttN_pipeLoaderSDXL,
    'ttN_pipeKSamplerSDXL_a19bff1409f78f89af7781cd': ttN_pipeKSamplerSDXL,
    'ttN_compareInput_0cbbb1699b9e429b0a797dde': ttN_compareInput,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'ttN_tinyLoader_c80deffd6042c4a897866d79': 'tinyLoader',
    'ttN_conditioning_00ee7fb58d6217b61d28ffda': 'tinyConditioning',
    'ttN_KSampler_v2_b96111c6c532990ae4d2a22d': 'tinyKSampler',
    'ttN_pipeLoader_v2_58246dfb20bdc0271e2f0da1': 'pipeLoader',
    'ttN_pipeKSampler_v2_384e6bf1e6bdf16dab3403be': 'pipeKSampler',
    'ttN_pipeKSamplerAdvanced_v2_0bde6a2fc6fd2b1f3148c941': 'pipeKSamplerAdvanced',
    'ttN_pipeLoaderSDXL_v2_2315fee49000ac73ed2b4205': 'pipeLoaderSDXL',
    'ttN_pipeKSamplerSDXL_v2_d7a835b65f8b639485e83a20': 'pipeKSamplerSDXL',
    'ttN_advanced_xyPlot_5660b5693fff3e6a7b6ac6be': 'advanced xyPlot',
    'ttN_advPlot_images_9464f7f009faedbbe64f8aee': 'advPlot images',
    'ttN_advPlot_range_ae4d61a6cbdb5c6824e46a98': 'advPlot range',
    'ttN_advPlot_string_abb8997c9782d24ce63175fb': 'advPlot string',
    'ttN_advPlot_combo_2175b2f2a4848cce66909124': 'advPlot combo',
    'ttN_advPlot_merge_174e015dbe69c2712c571e31': 'advPlot merge',
    'ttN_pipeEDIT_aa5a200004e9fb4314a1b528': 'pipeEDIT',
    'ttN_pipe2BASIC_748c46ff86c489ba345bbb37': 'pipe > basic_pipe',
    'ttN_pipe2DETAILER_fb799f9f4e6a3a0b893bacef': 'pipe > detailer_pipe',
    'ttN_pipeEncodeConcat_7974130fa1ef7a3d6966bb0a': 'pipeEncodeConcat',
    'ttN_pipeLoraStack_2ec4cdc8dd3715945346a19e': 'pipeLoraStack',
    'ttN_multiModelMerge_9930284c5606dcc14e190be2': 'multiModelMerge',
    'ttN_debugInput_b1bdfd3890f7007c8f93b9a5': 'debugInput',
    'ttN_text_17f67ffa52c37f580bb94011': 'text',
    'ttN_textDebug_0be2c3c83aa3a0e9be121654': 'textDebug',
    'ttN_concat_98a12dae0cccc980d9c7b338': 'textConcat',
    'ttN_text3BOX_3WAYconcat_d6bfacdd1e94a341253109a6': '3x TXT Loader MultiConcat',
    'ttN_text7BOX_concat_e768585a58ce525b0095c15f': '7x TXT Loader Concat',
    'ttN_textCycleLine_07efecfd0109e56a0112fcc3': 'textCycleLine',
    'ttN_textOutput_561c7568d7a8609efb4c9c40': 'textOutput',
    'ttN_imageOutput_9d7e52569d2d64b9e9e58352': 'imageOutput',
    'ttN_imageREMBG_d75ef8a3e919f3bfc66f9795': 'imageRemBG',
    'ttN_hiresfixScale_30b24f506f9af9321f1ae901': 'hiresfixScale',
    'ttN_int_3b12e0212a0b8b0be03416b7': 'int',
    'ttN_float_135744bce0eed7150cbe9f22': 'float',
    'ttN_seed_0fffce90a3d1a81a1e11489e': 'seed',
    'ttN_xyPlot_544de9d62d33978b709f2eee': 'xyPlot',
    'ttN_pipeIN_0f4a584cca428eb3e2db18ec': 'pipeIN (Legacy)',
    'ttN_pipeOUT_ddb0379afad4f093ff872f5d': 'pipeOUT (Legacy)',
    'ttN_pipeLoader_b6c51abd124a0a79c7ba8c93': 'pipeLoader v1 (Legacy)',
    'ttN_pipeKSampler_aab002d291a2f516b9550bf3': 'pipeKSampler v1 (Legacy)',
    'ttN_pipeKSamplerAdvanced_ba5a6ba9874ab2faac51c05a': 'pipeKSamplerAdvanced v1 (Legacy)',
    'ttN_pipeLoaderSDXL_48a01436a42cd167b68fb47f': 'pipeLoaderSDXL v1 (Legacy)',
    'ttN_pipeKSamplerSDXL_a19bff1409f78f89af7781cd': 'pipeKSamplerSDXL v1 (Legacy)',
    'ttN_compareInput_0cbbb1699b9e429b0a797dde': 'compareInput',
}

for _class in (ttN_PlotCell,ttN_PlotPlane,ttN_PlotFinish,ttN_PlotFailure):
    _id=_PLOT_BASE+' '+_class.__name__.removeprefix('ttN_Plot')
    NODE_CLASS_MAPPINGS[_id]=_class
    NODE_DISPLAY_NAME_MAPPINGS[_id]=_class.__name__
