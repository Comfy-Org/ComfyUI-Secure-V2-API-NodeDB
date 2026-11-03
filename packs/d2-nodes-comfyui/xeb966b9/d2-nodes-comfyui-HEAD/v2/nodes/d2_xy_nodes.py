from comfy_api.latest import io, sdk
from ._secure_boundary import SecureConversionRefusal, data_input
from .modules import util


def _seed_rng_refusal(seeds):
    try:
        for seed in seeds.strip().split('\n'):
            if int(seed) == -1:
                return ('d2-nodes-comfyui/D2 XY Seed: seeds containing int(-1) '
                        'require the source host-global Python RNG; this branch '
                        'is not yet converted to Secure Nodes V2')
    except (AttributeError, TypeError, ValueError, OverflowError):
        # Let execute retain the original error and its left-to-right order.
        return None
    return None


def _seed2_rng_refusal(initial_number, count, mode):
    try:
        initial_seed = int(initial_number)
    except (TypeError, ValueError, OverflowError):
        return None
    if initial_seed == -1:
        # The source draws this seed before range(count), even for count=0.
        return ('d2-nodes-comfyui/D2 XY Seed2: initial_number int(-1) requires '
                'the source host-global Python RNG; this branch is not yet '
                'converted to Secure Nodes V2')
    if mode == 'randomize':
        try:
            positive_count = range(count).stop > 0
        except TypeError:
            return None
        if positive_count:
            return ("d2-nodes-comfyui/D2 XY Seed2: mode='randomize' with count > 0 "
                    'requires the source host-global Python RNG; this branch '
                    'is not yet converted to Secure Nodes V2')
    return None


class D2_XYAnnotation(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 XY Annotation', display_name='D2 XY Annotation', category='D2/XY Plot', inputs=[io.String.Input('title', default=''), io.String.Input('list', multiline=True)], outputs=[io.Custom('D2_TAnnotation').Output(display_name='x / y_annotation')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 XY Annotation is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 XY Annotation is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_XYPlot(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 XY Plot', display_name='D2 XY Plot', category='D2/XY Plot', inputs=[io.Combo.Input('x_type', options=['STRING', 'INT', 'FLOAT']), io.String.Input('x_title', default=''), io.String.Input('x_list', multiline=True), io.Combo.Input('y_type', options=['STRING', 'INT', 'FLOAT']), io.String.Input('y_title', default=''), io.String.Input('y_list', multiline=True), io.Boolean.Input('auto_queue', default=True), io.Int.Input('start_index', default=0, max=65535), io.Custom('D2_BUTTON').Input('reset', optional=True), io.Custom('D2_XYPLOT_INDEX').Input('index', optional=True), io.Custom('D2_TIME').Input('remaining_time', optional=True), io.Custom('D2_SEED').Input('xy_seed', optional=True), io.Custom('D2_PROGRESS_BAR').Input('progress_bar', optional=True)], outputs=[io.Custom('D2_TGridPipe').Output(display_name='grid_pipe'), io.AnyType.Output(display_name='X'), io.AnyType.Output(display_name='Y'), io.Custom('D2_TAnnotation').Output(display_name='x_annotation'), io.Custom('D2_TAnnotation').Output(display_name='y_annotation'), io.String.Output(display_name='status'), io.Int.Output(display_name='index')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 XY Plot is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 XY Plot is not yet converted to Secure Nodes V2: The source caches random annotations across executions and emits mutable annotation dataclasses; no faithful public guest representation.')


class D2_XYPlotEasy(io.ComfyNode):
    SDK_REFS = True

    XY_INPUT_TYPES = ["none", "positive", "negative", "ckpt_name", "seed", "steps", "cfg", "sampler_name",
                          "scheduler", "denoise", "STRING", "INT", "FLOAT"]

    @classmethod
    def _xy_inputs(cls):
        return [io.String.Input('positive', multiline=True), io.String.Input('negative', multiline=True), io.Combo.Input('ckpt_name', options=[], remote=io.RemoteOptions(route='/models/checkpoints', refresh_button=True)), io.Combo.Input('unet_name', options=[], remote=io.RemoteOptions(route='/models/diffusion_models', refresh_button=True)), io.Combo.Input('ckpt_type', options=['stable_diffusion', 'diffusion']), io.Int.Input('seed', default=0, min=0, max=18446744073709551615), io.Int.Input('steps', default=20, min=1, max=10000), io.Float.Input('cfg', default=7.0, min=0.0, max=100.0), io.Combo.Input('sampler_name', options=['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'cfgpp_ud10_ab', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2']), io.Combo.Input('scheduler', options=['simple', 'sgm_uniform', 'karras', 'exponential', 'ddim_uniform', 'beta', 'normal', 'linear_quadratic', 'kl_optimal']), io.Float.Input('denoise', default=1.0, min=0.0, max=1.0, step=0.01), io.Combo.Input('x_type', options=cls.XY_INPUT_TYPES), io.String.Input('x_list', multiline=True), io.Combo.Input('y_type', options=cls.XY_INPUT_TYPES), io.String.Input('y_list', multiline=True), io.Boolean.Input('auto_queue', default=True), io.Int.Input('start_index', default=0, max=65535), io.Custom('D2_BUTTON').Input('reset', optional=True), io.Custom('D2_XYPLOT_INDEX').Input('index', optional=True), io.Custom('D2_TIME').Input('remaining_time', optional=True), io.Custom('D2_SEED').Input('xy_seed', optional=True), io.Custom('D2_PROGRESS_BAR').Input('progress_bar', optional=True)]

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 XY Plot Easy', display_name='D2 XY Plot Easy', category='D2/XY Plot', inputs=cls._xy_inputs(), outputs=[io.Custom('D2_TD2Pipe').Output(display_name='d2_pipe'), io.Custom('D2_TGridPipe').Output(display_name='grid_pipe'), io.String.Output(display_name='positive'), io.String.Output(display_name='negative'), io.AnyType.Output(display_name='ckpt_name'), io.String.Output(display_name='ckpt_type'), io.Int.Output(display_name='seed'), io.Int.Output(display_name='steps'), io.Float.Output(display_name='cfg'), io.AnyType.Output(display_name='sampler_name'), io.AnyType.Output(display_name='scheduler'), io.Float.Output(display_name='denoise'), io.AnyType.Output(display_name='x_other'), io.AnyType.Output(display_name='y_other'), io.Custom('D2_TAnnotation').Output(display_name='x_annotation'), io.Custom('D2_TAnnotation').Output(display_name='y_annotation'), io.String.Output(display_name='status'), io.Int.Output(display_name='index')], hidden=[io.Hidden.unique_id])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 XY Plot Easy is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 XY Plot Easy is not yet converted to Secure Nodes V2: The source caches random annotations across executions and emits D2_TD2Pipe/D2_TGridPipe dataclasses; public guests cannot preserve that opaque state and output contract.')


class D2_XYPlotEasyMini(D2_XYPlotEasy):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 XY Plot Easy Mini', display_name='D2 XY Plot Easy Mini', category='D2/XY Plot', inputs=cls._xy_inputs(), outputs=[io.Custom('D2_TD2Pipe').Output(display_name='d2_pipe'), io.Custom('D2_TGridPipe').Output(display_name='grid_pipe'), io.String.Output(display_name='positive'), io.String.Output(display_name='negative'), io.AnyType.Output(display_name='ckpt_name'), io.String.Output(display_name='ckpt_type'), io.AnyType.Output(display_name='x_other'), io.AnyType.Output(display_name='y_other')], hidden=[io.Hidden.unique_id])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 XY Plot Easy Mini is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 XY Plot Easy Mini is not yet converted to Secure Nodes V2: The source inherits cross-execution annotation state and emits D2 pipe/grid dataclasses; no faithful public guest representation.')


class D2_XYGridImage(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 XY Grid Image', display_name='D2 XY Grid Image', category='D2/XY Plot', inputs=[io.Image.Input('images'), io.Int.Input('font_size', default=24), io.Int.Input('grid_gap', default=0), io.Boolean.Input('swap_dimensions', default=False), io.Boolean.Input('grid_only', default=True), io.Boolean.Input('draw_x_label', default=True), io.Boolean.Input('draw_y_label', default=True), io.Custom('D2_TAnnotation').Input('x_annotation', optional=True), io.Custom('D2_TAnnotation').Input('y_annotation', optional=True), io.String.Input('status', force_input=True, optional=True), io.Custom('D2_TGridPipe').Input('grid_pipe', optional=True)], outputs=[io.Image.Output(display_name='images'), io.String.Output(display_name='memo')], hidden=[io.Hidden.unique_id])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 XY Grid Image is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 XY Grid Image is not yet converted to Secure Nodes V2: The source accumulates tensors across separate executions, reads opaque annotation/grid dataclasses, and emits an ExecutionBlocker until FINISH; no faithful public guest representation.')


class D2_XYModelList(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="D2 XY Model List",
            display_name="D2 XY Model List",
            category="D2/XY Plot",
            inputs=[
                io.Combo.Input("model_type", options=["checkpoints", "loras", "diffusion_models", "samplers", "schedulers", "upscaler", "bbox_segm", "controlnet"]),
                io.String.Input("filter", default=""),
                io.Combo.Input("mode", options=["simple", "a1111"]),
                io.Combo.Input("sort_by", options=["Name", "Date"], default="Name"),
                io.Combo.Input("order_by", options=["A-Z", "Z-A"], default="A-Z"),
                io.Custom("D2_BUTTON").Input("get_list", optional=True),
                io.String.Input("model_list", multiline=True, optional=True),
            ],
            outputs=[
                io.String.Output(display_name="x / y_list"),
                io.Custom("LIST").Output(display_name="LIST"),
            ],
        )

    @classmethod
    def execute(cls, model_type, filter="", mode="simple", sort_by="Name", order_by="A-Z", get_list=None, model_list="") -> io.NodeOutput:
        list_list = model_list.split("\n")
        return io.NodeOutput(model_list, list_list)

class D2_XYPromptSR(io.ComfyNode):
    SDK_REFS = True


    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="D2 XY Prompt SR",
            display_name="D2 XY Prompt SR",
            category="D2/XY Plot",
            inputs=[
                io.String.Input("prompt", multiline=True, default=""),
                io.String.Input("search", default=""),
                io.String.Input("replace", multiline=True, default=""),
            ],
            outputs=[
                io.String.Output(display_name="x / y_list"),
                io.Custom("LIST").Output(display_name="LIST"),
            ],
        )

    @classmethod
    def execute(cls, prompt, search, replace) -> io.NodeOutput:
        # 置換文字列を改行で分割
        replace_items = replace.strip().split('\n')

        # 出力リスト
        output_list = [prompt]

        # 文字列を検索して置換
        for item in replace_items:
            new_prompt = prompt.replace(search, item)
            output_list.append(new_prompt)

        output_xy = "\n".join([prompt.replace('\n','') for prompt in output_list])

        return io.NodeOutput(output_xy, output_list)

class D2_XYPromptSR2(io.ComfyNode):
    SDK_REFS = True


    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="D2 XY Prompt SR2",
            display_name="D2 XY Prompt SR2",
            category="D2/XY Plot",
            inputs=[
                io.String.Input("search"),
                io.String.Input("prompt", multiline=True),
                io.String.Input("x_y", force_input=True),
            ],
            outputs=[
                io.String.Output(display_name="STRING"),
            ],
        )

    @classmethod
    def execute(cls, search, prompt, x_y) -> io.NodeOutput:
        new_prompt = prompt.replace(search, x_y)
        return io.NodeOutput(new_prompt)

class D2_XYSeed(io.ComfyNode):
    SDK_REFS = True


    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="D2 XY Seed",
            display_name="D2 XY Seed",
            category="D2/XY Plot",
            inputs=[
                io.String.Input("seeds", multiline=True, default="-1\n-1"),
            ],
            outputs=[
                io.String.Output(display_name="x / y_list"),
                io.Custom("LIST").Output(display_name="LIST"),
                # V1 の OUTPUT_IS_LIST=(False, False, True) を踏襲。BATCH はリスト出力
                io.AnyType.Output(display_name="BATCH", is_output_list=True),
            ],
        )

    @classmethod
    def validate_inputs(cls, seeds):
        return _seed_rng_refusal(seeds) or True

    @classmethod
    def execute(cls, seeds) -> io.NodeOutput:
        refusal = _seed_rng_refusal(seeds)
        if refusal:
            raise SecureConversionRefusal(refusal)

        # 入力文字列を改行で分割
        seed_list = seeds.strip().split('\n')

        # seed値を生成
        output_list = [util.create_seed(seed) for seed in seed_list]
        output_xy = "\n".join(str(x) for x in output_list)

        return io.NodeOutput(output_xy, output_list, output_list)

class D2_XYSeed2(io.ComfyNode):
    SDK_REFS = True


    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="D2 XY Seed2",
            display_name="D2 XY Seed2",
            category="D2/XY Plot",
            inputs=[
                io.Int.Input("initial_number", default=-1, min=-1, max=0xffffffffffffffff),
                io.Int.Input("count", default=1, min=0, max=0xffffffffffffffff),
                io.Combo.Input("mode", options=["fixed", "increment", "decrement", "randomize"], default="randomize"),
            ],
            outputs=[
                io.String.Output(display_name="x / y_list"),
                io.Custom("LIST").Output(display_name="LIST"),
                # V1 の OUTPUT_IS_LIST=(False, False, True) を踏襲。BATCH はリスト出力
                io.AnyType.Output(display_name="BATCH", is_output_list=True),
            ],
        )

    """
    seed値を生成する
    initial_number: 元の数値
    count: 生成個数
    mode: モード（fixed / increment / decrement / randomize）
    """
    @classmethod
    def validate_inputs(cls, initial_number, count, mode):
        return _seed2_rng_refusal(initial_number, count, mode) or True

    @classmethod
    def execute(cls, initial_number, count, mode) -> io.NodeOutput:
        refusal = _seed2_rng_refusal(initial_number, count, mode)
        if refusal:
            raise SecureConversionRefusal(refusal)
        # 出力リスト
        output_list = []
        # 初期番号生成
        initial_seed = util.create_seed(initial_number)

        # count分生成して output_list に格納
        for i in range(count):
            if(mode == "fixed"):
                output_list.append(initial_seed)
            elif(mode == "increment"):
                output_list.append(initial_seed + i)
            elif(mode == "decrement"):
                output_list.append(initial_seed - i)
            elif(mode == "randomize"):
                output_list.append(util.create_seed(-1))

        output_xy = "\n".join(str(x) for x in output_list)

        return io.NodeOutput(output_xy, output_list, output_list)

class D2_XYListToPlot(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="D2 XY List To Plot",
            display_name="D2 XY List To Plot",
            category="D2/XY Plot",
            inputs=[
                io.Custom("LIST").Input("LIST"),
            ],
            outputs=[
                io.String.Output(display_name="x / y_list"),
            ],
        )

    @classmethod
    async def execute(cls, LIST) -> io.NodeOutput:
        LIST = await data_input(LIST, 'D2 XY List To Plot')
        output = util.list_to_text(LIST, util.LINE_BREAK)
        return io.NodeOutput(output)

class D2_XYStringToPlot(io.ComfyNode):
    SDK_REFS = True


    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="D2 XY String To Plot",
            display_name="D2 XY String To Plot",
            category="D2/XY Plot",
            inputs=[
                io.Int.Input("string_count", default=3, min=1, max=50, step=1),
            ],
            outputs=[
                io.String.Output(display_name="x / y_list"),
            ],
            # JS が string_1..N を addInput で動的追加するため **kwargs で受ける
            accept_all_inputs=True,
        )

    @classmethod
    def execute(cls, string_count, **kwargs) -> io.NodeOutput:

        string_list = []

        for i in range(1, string_count + 1):
            string = kwargs.get(f"string_{i}")
            if string is not None:
                string_list.append(string)

        if len(string_list) > 0:
            # xy_plot は改行でアイテムを区切っているので、各アイテムの改行を消す
            cleaned = [s.replace('\n', '') for s in string_list]
            result = '\n'.join(cleaned)

            return io.NodeOutput(result)

        return io.NodeOutput(None)

class D2_XYFolderImages(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 XY Folder Images', display_name='D2 XY Folder Images', category='D2/XY Plot', inputs=[io.String.Input('folder', default=''), io.String.Input('extension', default='*.*'), io.Boolean.Input('include_subfolders', default=False), io.Combo.Input('sort_by', options=['Name', 'Date', 'Random'], default='Name'), io.Combo.Input('order_by', options=['A-Z', 'Z-A'], default='A-Z'), io.Custom('D2_SIMPLE_TEXT').Input('image_count', optional=True), io.Custom('D2_SEED').Input('queue_seed', optional=True), io.Custom('D2_BUTTON').Input('refresh_btn', optional=True)], outputs=[io.String.Output(display_name='x / y_list'), io.Custom('LIST').Output(display_name='LIST'), io.Int.Output(display_name='image_count')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 XY Folder Images is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 XY Folder Images is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_XYUploadImage(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 XY Upload Image', display_name='D2 XY Upload Image', category='D2/XY Plot', inputs=[io.String.Input('image_list', multiline=True, default=''), io.Custom('D2_SIMPLE_TEXT').Input('image_count', optional=True), io.Custom('D2_SIMPLE_TEXT').Input('status', optional=True)], outputs=[io.Custom('LIST').Output(display_name='LIST'), io.String.Output(display_name='x / y_list'), io.Int.Output(display_name='image_count')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 XY Upload Image is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 XY Upload Image is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_XYListCollector(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 XY List Collector', display_name='D2 XY List Collector', category='D2/XY Plot', inputs=[io.AnyType.Input('data'), io.Boolean.Input('skip_empty', default=True), io.String.Input('xy_status', force_input=True, optional=True), io.Custom('D2_TGridPipe').Input('grid_pipe', optional=True)], outputs=[io.AnyType.Output(display_name='output')], hidden=[io.Hidden.unique_id])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 XY List Collector is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 XY List Collector is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


NODE_CLASS_MAPPINGS = {
    "D2 XY Plot": D2_XYPlot,
    "D2 XY Plot Easy": D2_XYPlotEasy,
    "D2 XY Plot Easy Mini": D2_XYPlotEasyMini,
    "D2 XY Grid Image": D2_XYGridImage,
    "D2 XY Model List": D2_XYModelList,
    "D2 XY Prompt SR": D2_XYPromptSR,
    "D2 XY Prompt SR2": D2_XYPromptSR2,
    "D2 XY List To Plot": D2_XYListToPlot,
    "D2 XY String To Plot": D2_XYStringToPlot,
    "D2 XY Folder Images": D2_XYFolderImages,
    "D2 XY Upload Image": D2_XYUploadImage,
    "D2 XY List Collector": D2_XYListCollector,
    "D2 XY Seed": D2_XYSeed,
    "D2 XY Seed2": D2_XYSeed2,
    "D2 XY Annotation": D2_XYAnnotation,
}
