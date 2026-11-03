from comfy_api.latest import io, sdk
from ._secure_boundary import SecureConversionRefusal, data_input
import re
from .modules import util, text_util, nai_prompt_util
from .modules.util import delete_comment
from .modules.template_util import replace_template


class D2_RegexSwitcher(io.ComfyNode):
    SDK_REFS = True


    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="D2 Regex Switcher",
            display_name="D2 Regex Switcher",
            category="D2/Text",
            inputs=[
                io.String.Input("text", force_input=True, multiline=True, default=""),
                io.String.Input("regex_and_output", multiline=True, default="pony\n--\nscore_9,\n--\n--\nhighres, high quality,"),
                io.Combo.Input("pre_delim", options=["Comma", "Line break", "None"]),
                io.Combo.Input("suf_delim", options=["Comma", "Line break", "None"]),
                io.Combo.Input("show_text", options=["False", "True"]),
                io.String.Input("text_check", multiline=True),
                io.String.Input("prefix", force_input=True, multiline=True, default="", optional=True),
                io.String.Input("suffix", force_input=True, multiline=True, default="", optional=True),
            ],
            outputs=[
                io.String.Output(display_name="combined_text"),
                io.String.Output(display_name="prefix"),
                io.String.Output(display_name="suffix"),
                io.Int.Output(display_name="index"),
            ],
        )

    @classmethod
    def execute(cls, text, regex_and_output, pre_delim, suf_delim, show_text="True", text_check="", prefix="", suffix="") -> io.NodeOutput:
        """
        正規表現に基づいてテキストをマッチングし、結果を結合して返す関数。

        Args:
            text (str): マッチング対象のテキスト
            regex_and_output (str): 正規表現とその出力のペアを "--" で区切った文字列
            prefix (str): 結果の前に付加するテキスト
            suffix (str): 結果の後に付加するテキスト

        Returns:
            dict: UI用のテキストと結果のタプルを含む辞書
        """
        # optional 未接続時は V1 同様 空文字列として扱う（出力が None にならないように）
        if prefix is None:
            prefix = ""
        if suffix is None:
            suffix = ""

        regex_output_list, default_output = D2_RegexSwitcher.get_regex_list(regex_and_output)
        match_text, match_index = D2_RegexSwitcher.get_mach_text(regex_output_list, default_output, text)

        # 文字列を結合
        parts = []
        if prefix:
            parts.append(prefix)
            parts.append(util.get_separator_str(pre_delim))
        parts.append(match_text)
        if suffix:
            parts.append(util.get_separator_str(suf_delim))
            parts.append(suffix)

        combined_text = "".join(parts)

        return io.NodeOutput(
            combined_text, prefix, suffix, match_index,
            ui={"text": (text,)},
        )

    """
    該当文字列と該当indexを取得
    """
    @staticmethod
    def get_mach_text(regex_output_list, default_output, text):
        # 各正規表現をチェックし、マッチしたら対応する出力を返す
        for index, item in enumerate(regex_output_list):
            # match_text = re.sub(item["regex"], item["output"], text, flags=re.IGNORECASE)
            # if match_text != text:
            if re.search(item["regex"], text, re.IGNORECASE):
                return item["output"], index

        # マッチしなかった場合はデフォルト出力を返す
        return default_output, -1

    """
    regex_and_output を -- で分割し、ペアにする
    """
    @staticmethod
    def get_regex_list(text:str):
        pairs = text.split('--')
        regex_output_list = []
        default_output = None

        # ペアをリストに整理する
        for i in range(0, len(pairs), 2):
            if i + 1 < len(pairs):
                regex = pairs[i].strip()
                output = pairs[i+1].strip()
                if regex:
                    regex_output_list.append({
                        'regex': regex,
                        'output': output
                    })
                else:
                    default_output = output

        return regex_output_list, default_output

class D2_RegexReplace(io.ComfyNode):
    SDK_REFS = True


    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="D2 Regex Replace",
            display_name="D2 Regex Replace",
            category="D2/Text",
            inputs=[
                io.String.Input("text", force_input=True, multiline=True, default=""),
                io.Combo.Input("mode", options=["Tag", "Advanced"]),
                io.String.Input("regex_replace", multiline=True, default=""),
            ],
            outputs=[
                io.String.Output(display_name="text"),
            ],
        )

    @classmethod
    def execute(cls, text, mode="Tag", regex_replace="") -> io.NodeOutput:
        if not text or not regex_replace:
            return io.NodeOutput(text)

        replace_pairs = D2_RegexReplace._parse_regex_replace(regex_replace)

        if mode == "Tag":
            result_text = D2_RegexReplace._repalace_tag(text, replace_pairs)
        else:
            result_text = D2_RegexReplace._repalace_advanced(text, replace_pairs)

        return io.NodeOutput(result_text)


    @classmethod
    def _repalace_tag(cls, result_text, replace_pairs):
        """
        result_text をカンマまたは改行で分割し、分割した要素に対して置換を行う
        置換後に空（または空白文字のみ）の要素は除外する
        """
        try:
            # カンマまたは改行で分割して、各要素をトリム
            tags = [tag.strip() for tag in re.split('[,\n]', result_text)]
            # 空の要素を削除
            tags = [tag for tag in tags if tag]

            # 各タグに対して正規表現による置換を適用
            new_tags = []
            for tag in tags:
                new_tag = tag
                for search_pattern, replace_pattern in replace_pairs:
                    try:
                        new_tag = re.sub(search_pattern, replace_pattern, new_tag)
                    except re.error as e:
                        return f"Regex error in tag '{tag}': {str(e)}"

                # 置換後のタグが空でない場合のみ追加
                if new_tag.strip():
                    new_tags.append(new_tag)

            # カンマ区切りで結合して返す
            return ', '.join(new_tags)

        except Exception as e:
            return f"Error during tag replacement: {str(e)}"


    @classmethod
    def _repalace_advanced(cls, result_text, replace_pairs):
        """
        result_text 全体を正規表現で置換する
        """
        for search_pattern, replace_pattern in replace_pairs:
            try:
                result_text = re.sub(search_pattern, replace_pattern, result_text, flags=re.DOTALL | re.MULTILINE)
            except re.error as e:
                return {"result": (f"Regex error: {str(e)}",)}
            except Exception as e:
                return {"result": (f"Error during replacement: {str(e)}",)}

        return result_text


    @classmethod
    def _parse_regex_replace(cls, regex_replace):
        """
        検索条件と置換文字のペアを作成
        """
        if not regex_replace.strip():
            return []

        parts = [p.strip("\n\t") for p in regex_replace.split('--')]
        pairs = []

        for i in range(0, len(parts), 2):
            search = parts[i]
            if search:  # 検索文字があれば
                replace = parts[i + 1] if i + 1 < len(parts) else ""
                pairs.append((search, replace))

        return pairs

class D2_MultiOutput(io.ComfyNode):
    SDK_REFS = True


    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="D2 Multi Output",
            display_name="D2 Multi Output",
            category="D2/Text",
            inputs=[
                # 入力タイプ
                io.Combo.Input("type", options=["FLOAT", "INT", "STRING", "SEED"]),
                # プロンプト
                io.String.Input("parameter", multiline=True),
                # seed 生成ボタン（JS の D2_BUTTON ウィジェット。値は使わない）
                io.Custom("D2_BUTTON").Input("create_seed", optional=True),
            ],
            outputs=[
                io.Custom("LIST").Output(display_name="LIST"),
                io.String.Output(display_name="x / y_list"),
            ],
        )

    @classmethod
    def execute(cls, type, parameter, create_seed=None) -> io.NodeOutput:

        # 入力文字列を改行で分割
        param_options = parameter.strip().split('\n')

        # 出力リスト
        output_list = []

        # 文字列を検索して置換
        for option in param_options:
            if type == "INT" or type == "SEED":
                output_list.append(int(option))
            elif type == "FLOAT":
                output_list.append(float(option))
            else:
                output_list.append(option)

        return io.NodeOutput(output_list, parameter)

class D2_TokenCounter(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Token Counter', display_name='D2 Token Counter', category='D2/Text', inputs=[io.String.Input('text', multiline=True), io.Combo.Input('clip_name', options=['ViT-L/14', 'ViT-B/32', 'ViT-B/16'], default='ViT-L/14')], outputs=[io.Int.Output(display_name='token_count'), io.String.Output(display_name='tokenized_result')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Token Counter is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Token Counter is not yet converted to Secure Nodes V2: The source constructs three CLIP tokenizers using unpinned from_pretrained downloads; tokenizer assets must be independently pinned and declared before execution.')


class D2_Prompt(io.ComfyNode):
    SDK_REFS = True


    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Prompt', display_name='D2 Prompt', category='D2/Text', inputs=[io.String.Input('prompt', multiline=True), io.Combo.Input('comment_type', options=['# + // + /**/', '# only', '// only', '/* */ only', 'None']), io.Combo.Input('insert_lora', options=['CHOOSE'], remote=io.RemoteOptions(route='/models/loras', refresh_button=True)), io.Boolean.Input('token_count', default=False)], outputs=[io.String.Output(display_name='text')])

    @classmethod
    def execute(cls, prompt, comment_type, insert_lora="", token_count=False) -> io.NodeOutput:
        new_prompt = delete_comment(prompt, comment_type)
        return io.NodeOutput(new_prompt)

    @classmethod
    def validate_inputs(cls, insert_lora):
        # The remote catalogue is logical data. This UI-only selection is not read by execute.
        return True if isinstance(insert_lora, str) else "D2 Prompt: insert_lora must be a string"

class D2_ListToString(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 List To String', display_name='D2 List To String', category='D2/Text', inputs=[io.Custom('LIST').Input('LIST'), io.Combo.Input('separator', options=['Comma + Space', 'Comma', 'Line break', 'Semicolon', 'Space', 'None'], default='Line break')], outputs=[io.String.Output(display_name='STRING')])

    @classmethod
    async def execute(cls, LIST, separator) -> io.NodeOutput:
        LIST = await data_input(LIST, 'D2 List To String')
        output = util.list_to_text(LIST, separator)
        return io.NodeOutput(output)

class D2_TextConcat(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Text Concat', display_name='D2 Text Concat', category='D2/Text', inputs=[io.Int.Input('text_count', default=3, min=1, max=50, step=1), io.Combo.Input('separator', options=['Comma + Space', 'Comma', 'Line break', 'Semicolon', 'Space', 'None'], default='Comma + Space'), io.Boolean.Input('skip_empty', default=True)], outputs=[io.String.Output(display_name='text')], accept_all_inputs=True)

    @classmethod
    def execute(cls, text_count, separator="Comma + Space", skip_empty=True, **kwargs) -> io.NodeOutput:
        texts = []
        for i in range(1, text_count + 1):
            text = kwargs.get(f"text_{i}")
            if text is None:
                continue
            if skip_empty:
                # 前後の空白・改行を除去し、空になったものはスキップ
                text = text.strip()
                if text == "":
                    continue
            texts.append(text)

        output = util.get_separator_str(separator).join(texts)
        return io.NodeOutput(output)

class D2_FilenameTemplate(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "graph.metadata")

    @classmethod
    def define_schema(cls) -> io.Schema:
        tooltip = "Datetime -- %date:{yyyy/MM/dd/hh/mm/ss}%\n" \
                  "Node param -- %node:{id}.{key}%\n" \
                  "arg_1-3 -- %arg_1%\n" \
                  "Delete .safetensors -- %arg_1:ckpt_name"

        return io.Schema(
            node_id="D2 Filename Template",
            display_name="D2 Filename Template",
            category="D2/Text",
            inputs=[
                io.String.Input("format", tooltip=tooltip),
                io.Int.Input("arg_count", default=3, min=1, max=50, step=1),
                io.Boolean.Input("normalization", default=True),
                io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff),
            ],
            outputs=[
                io.String.Output(display_name="STRING"),
            ],
            hidden=[io.Hidden.prompt],
            # arg_1..arg_N は JS が動的に追加する未宣言入力。V1 の **kwargs と同様に
            # 受け取るため accept_all_inputs を有効化する。
            accept_all_inputs=True,
        )

    @classmethod
    async def execute(cls, format, arg_count, normalization, seed, **kwargs) -> io.NodeOutput:

        kwargs = {key: await data_input(value, cls.define_schema().node_id) for key, value in kwargs.items()}
        args = {}

        for i in range(1, arg_count + 1):
            key = f"arg_{i}"
            arg = kwargs.get(key)
            if arg is not None:
                args[key] = arg

        metadata = await sdk.current_context().graph.execution_metadata()
        text = replace_template(format, args, metadata["prompt"], normalization)
        return io.NodeOutput(text)

class D2_FilenameTemplate2(D2_FilenameTemplate):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "graph.metadata")

    @classmethod
    def define_schema(cls) -> io.Schema:
        tooltip = "Datetime -- %date:{yyyy/MM/dd/hh/mm/ss}%\n" \
                  "Node param -- %node:{id}.{key}%\n" \
                  "arg_1-3 -- %arg_1%\n" \
                  "Delete .safetensors -- %arg_1:ckpt_name"

        return io.Schema(
            node_id="D2 Filename Template2",
            display_name="D2 Filename Template2",
            category="D2/Text",
            inputs=[
                io.String.Input("format", tooltip=tooltip, multiline=True),
                io.Int.Input("arg_count", default=3, min=1, max=50, step=1),
                io.Boolean.Input("normalization", default=True),
                io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff),
            ],
            outputs=[
                io.String.Output(display_name="STRING"),
            ],
            hidden=[io.Hidden.prompt],
            accept_all_inputs=True,
        )

class D2_PromptSanitizer(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Prompt Sanitizer', display_name='D2 Prompt Sanitizer', category='D2/Text', inputs=[io.String.Input('prompt', force_input=True), io.Boolean.Input('underscore_to_space', default=True), io.Boolean.Input('space_after_comma', default=True), io.Boolean.Input('remove_extra_comma', default=True), io.Boolean.Input('protect_lora', default=True), io.Boolean.Input('protect_score', default=True), io.Combo.Input('newline_mode', options=['keep', 'add_comma', 'to_comma', 'to_space', 'remove'], default='keep'), io.Boolean.Input('remove_duplicate_tags', default=False), io.Boolean.Input('strip_trailing_comma', default=False), io.Combo.Input('comment_type', options=['# + // + /**/', '# only', '// only', '/* */ only', 'None'], default='None')], outputs=[io.String.Output(display_name='prompt')])

    @classmethod
    def execute(cls, prompt, underscore_to_space=True, space_after_comma=True, remove_extra_comma=True, protect_lora=True, protect_score=True, newline_mode="keep", remove_duplicate_tags=False, strip_trailing_comma=False, comment_type=util.COMMENT_TYPE_NONE) -> io.NodeOutput:
        # 改行変換で行頭の # や // が行頭でなくなる前に消す
        prompt = delete_comment(prompt, comment_type)
        text = text_util.sanitize_prompt(
            prompt,
            underscore_to_space=underscore_to_space,
            space_after_comma=space_after_comma,
            remove_extra_comma=remove_extra_comma,
            protect_lora=protect_lora,
            protect_score=protect_score,
            newline_mode=newline_mode,
            remove_duplicate_tags=remove_duplicate_tags,
            strip_trailing_comma=strip_trailing_comma,
        )
        return io.NodeOutput(text)

class D2_ConvertNaiPrompt(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Convert NAI Prompt', display_name='D2 Convert NAI Prompt', category='D2/Text', inputs=[io.String.Input('prompt', force_input=True), io.Combo.Input('convert', options=['sd_to_nai', 'nai_to_sd'], default='sd_to_nai'), io.Combo.Input('mode', options=['number', 'brace'], default='number'), io.Boolean.Input('remove_negative', default=True)], outputs=[io.String.Output(display_name='prompt')])

    @classmethod
    def execute(cls, prompt, convert="sd_to_nai", mode="number", remove_negative=True) -> io.NodeOutput:
        if convert == "sd_to_nai":
            text = nai_prompt_util.convert_to_nai(prompt, mode)
        else:
            text = nai_prompt_util.convert_to_sd(prompt, mode, remove_negative)
        return io.NodeOutput(text)

class D2_LoadText(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Load Text', display_name='D2 Load Text', category='D2/Text', inputs=[io.String.Input('file_path', default=''), io.Boolean.Input('encode_to_utf8', default=False)], outputs=[io.String.Output(display_name='text'), io.String.Output(display_name='file_path')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Load Text is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Load Text is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_LoadCSV(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Load CSV', display_name='D2 Load CSV', category='D2/Text', inputs=[io.String.Input('file_path', default=''), io.Combo.Input('file_type', options=['csv', 'tsv'], default='csv'), io.Boolean.Input('encode_to_utf8', default=False), io.Combo.Input('output_mode', options=['list', 'csv'], default='csv'), io.String.Input('row_index', default=''), io.String.Input('column_index', default=''), io.Boolean.Input('use_doublequote', default=False)], outputs=[io.AnyType.Output(display_name='output'), io.Int.Output(display_name='lines_count'), io.String.Output(display_name='file_path')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Load CSV is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Load CSV is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_SaveCaption(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Save Caption', display_name='D2 Save Caption', category='D2/Text', inputs=[io.String.Input('base_filename', default=''), io.String.Input('text', force_input=True, multiline=True, default=''), io.String.Input('extension', default='txt'), io.String.Input('exclude_tags', multiline=True, default=''), io.String.Input('prepend_tags', default=''), io.Combo.Input('word_separator', options=['underscore', 'space', 'none'], default='underscore'), io.Boolean.Input('remove_escape', default=True), io.Boolean.Input('trailing_comma', default=False), io.Boolean.Input('ignore_case', default=True), io.Boolean.Input('backup', default=True), io.Boolean.Input('dry_run', default=False)], outputs=[io.String.Output(display_name='text'), io.String.Output(display_name='file_path')], is_output_node=True)

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Save Caption is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Save Caption is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_TagReport(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Tag Report', display_name='D2 Tag Report', category='D2/Text', inputs=[io.String.Input('folder', default=''), io.Boolean.Input('include_subfolders', default=False), io.String.Input('extension', default='txt'), io.Combo.Input('order_by', options=['count_9-0', 'count_0-9', 'tag_a-z', 'tag_z-a'], default='count_9-0'), io.Boolean.Input('without_count', default=False), io.String.Input('exclude_tags', default=''), io.Combo.Input('output_type', options=['remove_comment', 'output_comment'], default='remove_comment'), io.Combo.Input('separator', options=['Line break', 'Comma + Space'], default='Line break'), io.Custom('D2_BUTTON').Input('get_tags', optional=True), io.String.Input('text', multiline=True, default='')], outputs=[io.String.Output(display_name='text')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Tag Report is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Tag Report is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_MossItem(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Moss Item', display_name='D2 Moss Item', category='D2/Text', inputs=[io.Mask.Input('mask'), io.Combo.Input('label', options=['object', 'text'], default='object'), io.String.Input('caption', default='', multiline=True), io.String.Input('text', default='')], outputs=[io.Custom('D2_MOSS_ITEM').Output(display_name='moss_item')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Moss Item is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Moss Item is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_MossPrompt(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Moss Prompt', display_name='D2 Moss Prompt', category='D2/Text', inputs=[io.String.Input('meta', default=''), io.String.Input('canvas_type', default='single'), io.String.Input('summary_caption', default='', multiline=True), io.Int.Input('item_count', default=2, min=1, max=50, step=1)], outputs=[io.String.Output(display_name='prompt')], accept_all_inputs=True)

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Moss Prompt is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Moss Prompt is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


NODE_CLASS_MAPPINGS = {
    "D2 Regex Switcher": D2_RegexSwitcher,
    "D2 Regex Replace": D2_RegexReplace,
    "D2 Token Counter": D2_TokenCounter,
    "D2 Multi Output": D2_MultiOutput,
    "D2 List To String": D2_ListToString,
    "D2 Text Concat": D2_TextConcat,
    "D2 Filename Template": D2_FilenameTemplate,
    "D2 Filename Template2": D2_FilenameTemplate2,
    "D2 Prompt": D2_Prompt,
    "D2 Prompt Sanitizer": D2_PromptSanitizer,
    "D2 Convert NAI Prompt": D2_ConvertNaiPrompt,
    "D2 Load Text": D2_LoadText,
    "D2 Load CSV": D2_LoadCSV,
    "D2 Save Caption": D2_SaveCaption,
    "D2 Tag Report": D2_TagReport,
    "D2 Moss Item": D2_MossItem,
    "D2 Moss Prompt": D2_MossPrompt,
}
