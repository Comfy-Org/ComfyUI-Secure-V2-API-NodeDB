import hashlib
import os
from tokenizers import Tokenizer, AddedToken

# The vocabulary is a reviewed, vendored resource -- not a runtime download.
# Upstream read `tokenizer.json` out of whichever directory `snapshot_download`
# had just filled, so the bytes that decide what a token means were whatever
# the hub served that day.  Here they are a file inside the pack, covered by
# the pack manifest, and checked against the digest recorded below before use.
#
# One file serves every supported model.  That is a measured fact, not a
# convenience: across all fourteen Florence-2 repositories the BPE vocabulary
# (50265 entries) and merge table are identical, and the only difference is the
# 1024 Florence-2 special tokens which `_add_special_tokens` appends here in
# the same order, yielding the same ids 50265..51288 -- exactly the embedding
# table's 51289 rows.  Repository-specific extras are named in
# `_florence2_catalog.EXTRA_SPECIAL_TOKENS` and passed in.
VOCABULARY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokenizer.json")
VOCABULARY_SHA256 = "847bbeab6174d66a88898f729d52fa8d355fafe1bea101cf960dd404581df70e"
VOCABULARY_SOURCE = (
    "microsoft/Florence-2-base",
    "5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac",
    "tokenizer.json",
)


def _verified_vocabulary_path():
    """Return the vendored vocabulary path after checking its identity."""
    with open(VOCABULARY_FILE, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    if digest != VOCABULARY_SHA256:
        raise RuntimeError(
            "vendored Florence-2 tokenizer.json failed its SHA-256 check")
    return VOCABULARY_FILE


class Florence2Tokenizer:
    def __init__(self, extra_special_tokens=()):
        self.tokenizer = Tokenizer.from_file(_verified_vocabulary_path())
        self._add_special_tokens(extra_special_tokens)

        # Standard token IDs
        self.pad_token_id = 1
        self.bos_token_id = 0
        self.eos_token_id = 2

    def _add_special_tokens(self, extra_special_tokens=()):
        """Add Florence2-specific special tokens."""
        special_tokens = ['<od>', '</od>', '<ocr>', '</ocr>']
        special_tokens += [f'<loc_{x}>' for x in range(1000)]
        special_tokens += [
            '<cap>', '</cap>', '<ncap>', '</ncap>', '<dcap>', '</dcap>',
            '<grounding>', '</grounding>', '<seg>', '</seg>', '<sep>',
            '<region_cap>', '</region_cap>', '<region_to_desciption>',
            '</region_to_desciption>', '<proposal>', '</proposal>',
            '<poly>', '</poly>', '<and>'
        ]
        special_tokens += list(extra_special_tokens)
        added = [AddedToken(t, special=True) for t in special_tokens]
        self.tokenizer.add_special_tokens(added)

    def encode(self, text):
        """Encode text to token ids. Returns dict with 'input_ids' tensor."""
        import torch
        encoding = self.tokenizer.encode(text)
        return {"input_ids": torch.tensor([encoding.ids], dtype=torch.long)}

    def decode(self, token_ids, skip_special_tokens=False):
        """Decode token ids to text."""
        if hasattr(token_ids, 'tolist'):
            token_ids = token_ids.tolist()
        if isinstance(token_ids[0], list):
            token_ids = token_ids[0]
        return self.tokenizer.decode(token_ids, skip_special_tokens=skip_special_tokens)

    def batch_decode(self, token_ids_batch, skip_special_tokens=False):
        """Decode a batch of token id sequences."""
        results = []
        if hasattr(token_ids_batch, 'tolist'):
            token_ids_batch = token_ids_batch.tolist()
        for ids in token_ids_batch:
            results.append(self.tokenizer.decode(ids, skip_special_tokens=skip_special_tokens))
        return results

    @property
    def all_special_tokens(self):
        """Return set of all special token strings. Needed by post-processor."""
        added = self.tokenizer.get_added_tokens_decoder()
        tokens = set()
        for token_obj in added.values():
            tokens.add(str(token_obj))
        # Also add the built-in ones
        tokens.update({'<s>', '</s>', '<pad>', '<unk>', '<mask>'})
        return tokens

    @property
    def vocab_size(self):
        return self.tokenizer.get_vocab_size()
