import math
import torch
from collections import namedtuple
from . import emphasis, prompt_parser


PromptChunkFix = namedtuple('PromptChunkFix', ['offset', 'embedding'])
last_extra_generation_params = {}


def _rows_key(tokens):
    """A hashable identity for one batch of token rows, tensor or list."""
    return tuple(tuple(int(value) for value in row) for row in tokens)

def populate_self_variables(self, from_):
    attrs_from = vars(from_)
    attrs_self = vars(self)
    attrs_self.update(attrs_from)

class PromptChunk:
    def __init__(self):
        self.tokens = []
        self.multipliers = []
        self.fixes = []


class _NoEmbeddings:
    """The weighted bridge has no embedding vectors to register.

    ``ComponentBridge`` rejects ``embedding:`` before tokenization. Keeping a
    tiny empty lookup here preserves the upstream chunker without shipping the
    filesystem/PIL/safetensors loader that can never be reached safely.
    """

    def __init__(self):
        self.fixes = None

    @staticmethod
    def find_embedding_at_position(_tokens, _offset):
        return None, 0


class ClassicTextProcessingEngine:
    def __init__(
            self, bridge, chunk_length=75,
            embedding_dir=None, embedding_key='clip_l', embedding_expected_shape=768, emphasis_name="Original",
            text_projection=False, minimal_clip_skip=1, clip_skip=1, return_pooled=True, final_layer_norm=True
    ):
        super().__init__()
        # Upstream took the live `tokenizer` and `text_encoder` submodules and
        # copied every attribute off the tokenizer onto itself. The bridge
        # answers the same questions over closed ops; see _clipbridge.py.
        self.bridge = bridge
        self.embedding_key = embedding_key

        # `find_embedding_at_position` reads only `ids_lookup`, which stays
        # empty because registering an embedding needs the vectors themselves.
        # The bridge refuses an `embedding:` fragment before we get here, so
        # this database is consulted and correctly finds nothing.
        self.embeddings = _NoEmbeddings()

        self.emphasis = emphasis.get_current_option(emphasis_name)()

        self.text_projection = text_projection
        self.minimal_clip_skip = minimal_clip_skip
        self.clip_skip = clip_skip
        self.return_pooled = return_pooled
        self.final_layer_norm = final_layer_norm

        self.chunk_length = bridge.chunk_length

        self.id_start = bridge.id_start
        self.id_end = bridge.id_end
        self.id_pad = bridge.id_pad

        # Upstream wrapped `text_model.embeddings.token_embedding` here so a
        # textual-inversion vector could be spliced into the input embedding
        # layer mid-forward. A guest never holds the transformer, and the
        # closed ops take token ids only, so that wrapper has no analogue.

        # `token_mults` came from a full `tokenizer.get_vocab()` sweep and is
        # read only by the `use_old_emphasis_implementation` path. No op
        # publishes a vocabulary, so that option raises in the node rather
        # than silently producing different emphasis here.
        self.token_mults = {}

        self.comma_token = bridge.comma_token

        # Memos filled by `prepare()` and read by the synchronous pipeline.
        # Per-engine, per-dispatch: nothing survives `execute` returning.
        self._fragments = {}
        self._encoded = {}

    async def prepare(self, texts):
        """Ask the host everything this batch of texts will need.

        `prompt_parser.get_learned_conditioning` is synchronous and calls the
        model exactly once per prompt with the full list of scheduled texts.
        The SDK ops are async. Rather than thread async through upstream's
        parser -- which would fork a file we want to keep byte-identical --
        the two host questions are answered up front, in dependency order:

            1. every attention fragment of every text -> token ids
            2. every token row those fragments chunk into -> embeddings

        Step 2 needs step 1's answers, and nothing after step 2 touches the
        host, so two awaited passes are sufficient and the pipeline below runs
        exactly as upstream wrote it.
        """
        fragments = []
        for text in texts:
            for fragment, _weight in prompt_parser.parse_prompt_attention(
                text, self.opts.prompt_attention
            ):
                if fragment not in self._fragments and fragment not in fragments:
                    fragments.append(fragment)
        if fragments:
            for fragment, ids in zip(
                fragments, await self.bridge.tokenize(fragments)
            ):
                self._fragments[fragment] = ids

        for tokens, _multipliers in self.tokenize_with_weights(texts):
            rows = self.token_tensor(tokens)
            key = _rows_key(rows)
            if key in self._encoded:
                continue
            self._encoded[key] = await self.bridge.encode_rows(rows.tolist())

    async def prepare_token_pairs(self, chunks):
        """Pre-resolve the token rows supplied by core's Comfy tokenizer."""
        for chunk in chunks:
            row = [int(entry[0]) for entry in chunk]
            key = _rows_key([row])
            if key not in self._encoded:
                self._encoded[key] = await self.bridge.encode_rows([row])

    def unhook(self):
        # Nothing was hooked: no bound method was replaced and no module was
        # wrapped, so there is nothing to restore. Kept so the call site in
        # smZNodes.py stays upstream's.
        pass

    def empty_chunk(self):
        chunk = PromptChunk()
        chunk.tokens = [self.id_start] + [self.id_end] * (self.chunk_length + 1)
        chunk.multipliers = [1.0] * (self.chunk_length + 2)
        return chunk

    def get_target_prompt_token_count(self, token_count):
        return math.ceil(max(token_count, 1) / self.chunk_length) * self.chunk_length

    def tokenize(self, texts):
        # Upstream called the live HF tokenizer here. `prepare()` has already
        # asked the host for every fragment this line can produce, so the
        # lookup below is the same answer, resolved one dispatch earlier.
        missing = [text for text in texts if text not in self._fragments]
        if missing:
            raise RuntimeError(
                f"fragment(s) {missing!r} were not tokenized by prepare()"
            )
        return [self._fragments[text] for text in texts]

    def tokenize_with_weights(self, texts, return_word_ids=False):
        # `parse_and_register_embeddings` walked an embeddings directory and
        # loaded vectors off disk. The node rejects `embedding:` for the
        # weighted parsers instead of silently rewriting it to a bare word,
        # which is what this call would do with no directory to search.
        texts = list(texts)
        if self.opts.use_old_emphasis_implementation:
            return self.process_texts_past(texts)
        batch_chunks, token_count = self.process_texts(texts)

        used_embeddings = {}
        chunk_count = max([len(x) for x in batch_chunks])

        zs = []
        for i in range(chunk_count):
            batch_chunk = [chunks[i] if i < len(chunks) else self.empty_chunk() for chunks in batch_chunks]

            tokens = [x.tokens for x in batch_chunk]
            multipliers = [x.multipliers for x in batch_chunk]
            self.embeddings.fixes = [x.fixes for x in batch_chunk]

            for fixes in self.embeddings.fixes:
                for _position, embedding in fixes:
                    used_embeddings[embedding.name] = embedding

            z = (tokens, multipliers)
            zs.append(z)

        return zs

    def encode_token_weights(self, token_weight_pairs):
        if isinstance(token_weight_pairs[0], str):
            token_weight_pairs = self.tokenize_with_weights(token_weight_pairs)
        elif isinstance(token_weight_pairs[0], list):
            token_weight_pairs = list(map(lambda x: ([list(map(lambda y: y[0], x))], [list(map(lambda y: y[1], x))]), token_weight_pairs))

        # Upstream moved the result to `text_encoder_offload_device()`. The
        # closed op already returns detached CPU tensors and a guest has no
        # device placement to honour, so there is nothing left to move.
        zs = []
        for tokens, multipliers in token_weight_pairs:
            z = self.process_tokens(tokens, multipliers)
            zs.append(z)
        if self.return_pooled:
            return torch.hstack(zs), zs[0].pooled if zs[0].pooled is not None else None
        else:
            return torch.hstack(zs)

    def encode_with_transformers(self, tokens):
        # Upstream called the live text encoder. `prepare()` has already asked
        # the host for exactly these rows over `encode_token_weights_component`.
        key = _rows_key(tokens)
        if key not in self._encoded:
            raise RuntimeError("token rows were not encoded by prepare()")
        z, pooled = self._encoded[key]
        z = z.clone()
        z.pooled = pooled
        return z

    def tokenize_line(self, line):
        parsed = prompt_parser.parse_prompt_attention(
            line, self.opts.prompt_attention
        )

        tokenized = self.tokenize([text for text, _ in parsed])

        chunks = []
        chunk = PromptChunk()
        token_count = 0
        last_comma = -1

        def next_chunk(is_last=False):
            nonlocal token_count
            nonlocal last_comma
            nonlocal chunk

            if is_last:
                token_count += len(chunk.tokens)
            else:
                token_count += self.chunk_length

            to_add = self.chunk_length - len(chunk.tokens)
            if to_add > 0:
                chunk.tokens += [self.id_end] * to_add
                chunk.multipliers += [1.0] * to_add

            chunk.tokens = [self.id_start] + chunk.tokens + [self.id_end]
            chunk.multipliers = [1.0] + chunk.multipliers + [1.0]

            last_comma = -1
            chunks.append(chunk)
            chunk = PromptChunk()

        for tokens, (text, weight) in zip(tokenized, parsed):
            if text == 'BREAK' and weight == -1:
                next_chunk()
                continue

            position = 0
            while position < len(tokens):
                token = tokens[position]

                comma_padding_backtrack = 20

                if token == self.comma_token:
                    last_comma = len(chunk.tokens)

                elif comma_padding_backtrack != 0 and len(chunk.tokens) == self.chunk_length and last_comma != -1 and len(chunk.tokens) - last_comma <= comma_padding_backtrack:
                    break_location = last_comma + 1

                    reloc_tokens = chunk.tokens[break_location:]
                    reloc_mults = chunk.multipliers[break_location:]

                    chunk.tokens = chunk.tokens[:break_location]
                    chunk.multipliers = chunk.multipliers[:break_location]

                    next_chunk()
                    chunk.tokens = reloc_tokens
                    chunk.multipliers = reloc_mults

                if len(chunk.tokens) == self.chunk_length:
                    next_chunk()

                embedding, embedding_length_in_tokens = self.embeddings.find_embedding_at_position(tokens, position)
                if embedding is None:
                    chunk.tokens.append(token)
                    chunk.multipliers.append(weight)
                    position += 1
                    continue

                emb_len = int(embedding.vectors)
                if len(chunk.tokens) + emb_len > self.chunk_length:
                    next_chunk()

                chunk.fixes.append(PromptChunkFix(len(chunk.tokens), embedding))

                chunk.tokens += [0] * emb_len
                chunk.multipliers += [weight] * emb_len
                position += embedding_length_in_tokens

        if chunk.tokens or not chunks:
            next_chunk(is_last=True)

        return chunks, token_count

    def process_texts(self, texts):
        token_count = 0

        cache = {}
        batch_chunks = []
        for line in texts:
            if line in cache:
                chunks = cache[line]
            else:
                chunks, current_token_count = self.tokenize_line(line)
                token_count = max(current_token_count, token_count)

                cache[line] = chunks

            batch_chunks.append(chunks)

        return batch_chunks, token_count

    def __call__(self, texts):
        tokens = self.tokenize_with_weights(texts)
        return self.encode_token_weights(tokens)

    def token_tensor(self, remade_batch_tokens):
        """Upstream's in-place pad fixup, lifted so `prepare()` can reuse it.

        Both the pre-resolve pass and `process_tokens` must ask the host about
        byte-identical rows or the memo lookup misses, so this cannot be
        duplicated at the two call sites.
        """
        tokens = torch.asarray(remade_batch_tokens)
        if self.id_end != self.id_pad:
            for batch_pos in range(len(remade_batch_tokens)):
                index = remade_batch_tokens[batch_pos].index(self.id_end)
                tokens[batch_pos, index + 1:tokens.shape[1]] = self.id_pad
        return tokens

    def process_tokens(self, remade_batch_tokens, batch_multipliers, *args, **kwargs):
        # Upstream's `except ValueError` branch caught a token list holding
        # textual-inversion tensors. Those cannot reach here: the node rejects
        # `embedding:` for the weighted parsers, so every row is plain ints.
        z = self.encode_with_transformers(self.token_tensor(remade_batch_tokens))

        pooled = getattr(z, 'pooled', None)

        self.emphasis.tokens = remade_batch_tokens
        self.emphasis.multipliers = torch.asarray(batch_multipliers).to(z)
        self.emphasis.z = z
        self.emphasis.after_transformers()
        z = self.emphasis.z

        if pooled is not None:
            z.pooled = pooled

        return z
