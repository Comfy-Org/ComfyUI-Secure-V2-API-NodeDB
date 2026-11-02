"""Prompt parsing used by defs/formatters.py, for a guest that cannot import ``comfy``.

parse_parentheses, token_weights, escape_important and unescape_important are copied
verbatim from ComfyUI core 6257422b, comfy/sd1_clip.py:320-375 (GPL-3.0, as this pack).

The original also inspected the live CLIP object: it took ``tokenizer.clip_l`` (or
``clip_h``) when the tokenizer was an SD1, SD2, SDXL, SD3 or Flux tokenizer, and read
that tokenizer's ``embedding_identifier`` and ``embedding_directory``. A guest sees a CLIP
input only as an opaque reference. Every one of those tokenizers uses the identifier
"embedding:" (comfy/sd1_clip.py:537) and the embedding directories the loader passed in
(the embeddings folders), so a present CLIP input is treated as such a tokenizer and its
embeddings are looked up in the embeddings catalogue (utils/embedding.py).
"""


def parse_parentheses(string):
    result = []
    current_item = ""
    nesting_level = 0
    for char in string:
        if char == "(":
            if nesting_level == 0:
                if current_item:
                    result.append(current_item)
                    current_item = "("
                else:
                    current_item = "("
            else:
                current_item += char
            nesting_level += 1
        elif char == ")":
            nesting_level -= 1
            if nesting_level == 0:
                result.append(current_item + ")")
                current_item = ""
            else:
                current_item += char
        else:
            current_item += char
    if current_item:
        result.append(current_item)
    return result

def token_weights(string, current_weight):
    a = parse_parentheses(string)
    out = []
    for x in a:
        weight = current_weight
        if len(x) >= 2 and x[-1] == ')' and x[0] == '(':
            x = x[1:-1]
            xx = x.rfind(":")
            weight *= 1.1
            if xx > 0:
                try:
                    weight = float(x[xx+1:])
                    x = x[:xx]
                except:
                    pass
            out += token_weights(x, weight)
        else:
            out += [(x, current_weight)]
    return out

def escape_important(text):
    text = text.replace("\\)", "\0\1")
    text = text.replace("\\(", "\0\2")
    return text

def unescape_important(text):
    text = text.replace("\0\1", ")")
    text = text.replace("\0\2", "(")
    return text


class CatalogueEmbeddingTokenizer:
    """What the capture code reads from an SD-family tokenizer: its embedding identifier
    and its embedding directories (here: the embeddings catalogue)."""

    embedding_identifier = "embedding:"
    embedding_directory = ("embeddings",)


def embedding_clip(clip_input):
    """The tokenizer view for a CLIP input, or None when there is no CLIP input."""
    if clip_input is None:
        return None
    return CatalogueEmbeddingTokenizer()
