from __future__ import annotations
from comfy_api.latest import io as _remaining_zz_io

class MiniMaxChunkFeedForwardSecure(_remaining_zz_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zz_io.Schema:
        return _remaining_zz_io.Schema(node_id='MiniMaxChunkFeedForwardSecure', display_name='MiniMax H3 Chunk FeedForward (Secure V2)', category='KJNodes/experimental', description='Chunks the MiniMax H3 feedforward over the packed token dimension to reduce peak VRAM without changing its math.', is_experimental=True, inputs=[_remaining_zz_io.Model.Input('model'), _remaining_zz_io.Int.Input('chunks', default=2, min=1, max=64, step=1, tooltip='Number of token chunks. More chunks reduce peak VRAM with some overhead.'), _remaining_zz_io.Int.Input('seq_threshold', default=4096, min=256, max=262144, step=256, tooltip='Only chunk packed sequences longer than this.')], outputs=[_remaining_zz_io.Model.Output(display_name='model')])

    @classmethod
    async def execute(cls, model, chunks, seq_threshold) -> _remaining_zz_io.NodeOutput:
        if chunks == 1:
            return _remaining_zz_io.NodeOutput(model)
        return _remaining_zz_io.NodeOutput(await model.patch('minimax_chunk_feed_forward', chunks=int(chunks), seq_threshold=int(seq_threshold)))

class MiniMaxLowVRAMAttentionSecure(_remaining_zz_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zz_io.Schema:
        return _remaining_zz_io.Schema(node_id='MiniMaxLowVRAMAttentionSecure', display_name='MiniMax H3 Low VRAM Attention (Secure V2)', category='KJNodes/experimental', description='Reduces MiniMax H3 attention peak VRAM by releasing intermediates early and evaluating independent head groups.', is_experimental=True, inputs=[_remaining_zz_io.Model.Input('model'), _remaining_zz_io.Int.Input('head_chunks', default=4, min=1, max=56, step=1, tooltip='Number of independent attention head groups.')], outputs=[_remaining_zz_io.Model.Output(display_name='model')])

    @classmethod
    async def execute(cls, model, head_chunks) -> _remaining_zz_io.NodeOutput:
        return _remaining_zz_io.NodeOutput(await model.patch('minimax_low_vram_attention', head_chunks=int(head_chunks)))

class MiniMaxH3TokenCounterSecure(_remaining_zz_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zz_io.Schema:
        return _remaining_zz_io.Schema(node_id='MiniMaxH3TokenCounterSecure', display_name='MiniMax H3 Token Counter (Secure V2)', category='KJNodes/misc', description='Counts the packed MiniMax H3 text, reference, audio, and video sequence without sampling.', inputs=[_remaining_zz_io.Latent.Input('samples'), _remaining_zz_io.Conditioning.Input('conditioning')], outputs=[_remaining_zz_io.Latent.Output('samples', display_name='samples'), _remaining_zz_io.Conditioning.Output('conditioning', display_name='conditioning'), _remaining_zz_io.Int.Output('tokens', display_name='tokens'), _remaining_zz_io.String.Output('breakdown', display_name='breakdown')], hidden=[_remaining_zz_io.Hidden.unique_id])

    @classmethod
    async def execute(cls, samples, conditioning) -> _remaining_zz_io.NodeOutput:
        result = await samples.minimax_h3_token_count(conditioning)
        breakdown = result['breakdown']
        return _remaining_zz_io.NodeOutput(samples, conditioning, result['tokens'], breakdown, ui={'text': [breakdown]})

NODE_CLASS_MAPPINGS = {
    'MiniMaxChunkFeedForwardSecure': MiniMaxChunkFeedForwardSecure,
    'MiniMaxLowVRAMAttentionSecure': MiniMaxLowVRAMAttentionSecure,
    'MiniMaxH3TokenCounterSecure': MiniMaxH3TokenCounterSecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'MiniMaxChunkFeedForwardSecure': 'MiniMax H3 Chunk FeedForward (Secure V2)',
    'MiniMaxLowVRAMAttentionSecure': 'MiniMax H3 Low VRAM Attention (Secure V2)',
    'MiniMaxH3TokenCounterSecure': 'MiniMax H3 Token Counter (Secure V2)',
}
