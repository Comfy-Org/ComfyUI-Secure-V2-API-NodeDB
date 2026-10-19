"""
ComfyUI Node: Sentence Filter
Receives a text prompt from the workflow, removes or replaces sentences
based on user-defined trigger words, and passes the result to the next node.
"""

import re


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _protect_url_dots(text: str) -> tuple[str, str]:
    """
    Replace dots inside URLs (e.g. www.femjoy.com) with a placeholder
    so they are not mistaken for sentence terminators.
    Returns (protected_text, placeholder).
    """
    PLACEHOLDER = "\x00"
    url_dot = re.compile(r'(?<=[a-zA-Z0-9])\.(?=[a-zA-Z0-9])')
    return url_dot.sub(PLACEHOLDER, text), PLACEHOLDER


def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences on period + optional whitespace.
    URL dots must already be protected before calling this.
    """
    segments = re.split(r"(\.\s*)", text)
    sentences = []
    current = ""
    for segment in segments:
        current += segment
        if re.match(r"\.\s*$", segment):
            sentences.append(current)
            current = ""
    if current.strip():
        sentences.append(current)
    return sentences


def _parse_words(raw: str) -> list[str]:
    """Parse a comma-separated word list, stripping whitespace and empty entries."""
    return [w.strip() for w in raw.split(",") if w.strip()]


def _sentence_contains_all(sentence: str, words: list[str], flags: int) -> bool:
    """Return True if the sentence contains ALL words in the list."""
    return all(re.search(re.escape(w), sentence, flags) for w in words)


def _process_text(
    text: str,
    delete_words: list[str],
    replace_words: list[str],
    replacement_sentence: str,
    case_sensitive: bool,
) -> tuple[str, int, int]:
    """
    Core processing logic (shared by node and tests).

    Returns:
        (cleaned_text, sentences_deleted, sentences_replaced)
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    protected, placeholder = _protect_url_dots(text)
    sentences = _split_sentences(protected)

    deleted = 0
    replaced = 0
    result = []

    for sentence in sentences:
        # Priority 1: delete
        if delete_words and _sentence_contains_all(sentence, delete_words, flags):
            deleted += 1
            continue  # drop sentence entirely

        # Priority 2: replace
        if replace_words and _sentence_contains_all(sentence, replace_words, flags):
            # Preserve trailing whitespace of the original sentence
            trailing = re.search(r"\s+$", sentence)
            trailing_ws = trailing.group() if trailing else ""
            result.append(replacement_sentence.rstrip() + "." + trailing_ws)
            replaced += 1
            continue

        result.append(sentence)

    cleaned = "".join(result).replace(placeholder, ".")
    cleaned = re.sub(r"  +", " ", cleaned).strip()
    return cleaned, deleted, replaced


# ---------------------------------------------------------------------------
# Node class
# ---------------------------------------------------------------------------

class SentenceFilterNode:
    """
    A ComfyUI node that filters sentences from a text prompt.

    - Delete:  removes every sentence that contains ALL specified delete-words.
    - Replace: replaces every sentence that contains ALL specified replace-words
               with a custom replacement sentence.

    For both fields, enter a single word or multiple comma-separated words.
    A sentence is only affected if it contains EVERY word in the list.
    URL dots (e.g. www.example.com) are ignored during sentence splitting.
    """

    CATEGORY = "text/processing"
    FUNCTION = "filter_text"
    RETURN_TYPES = ("STRING", "INT", "INT")
    RETURN_NAMES = ("text", "sentences_deleted", "sentences_replaced")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "Input text from workflow",
                    },
                ),
            },
            "optional": {
                "delete_words": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "",
                        "placeholder": 'Words to delete sentence, e.g. "Watermark" or "blonde, straight, young"',
                    },
                ),
                "replace_words": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "",
                        "placeholder": 'Words to find sentence for replacement, e.g. "blonde, straight"',
                    },
                ),
                "replacement_sentence": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "Replacement sentence (used when replace_words match)",
                    },
                ),
                "case_sensitive": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Case Sensitive",
                        "label_off": "Case Insensitive",
                    },
                ),
            },
        }

    def filter_text(
        self,
        text: str,
        delete_words: str = "",
        replace_words: str = "",
        replacement_sentence: str = "",
        case_sensitive: bool = False,
    ) -> tuple[str, int, int]:
        """
        Main entry point called by ComfyUI.

        Args:
            text:                  Input text prompt from the workflow
            delete_words:          Comma-separated words; sentences containing
                                   ALL of them are deleted
            replace_words:         Comma-separated words; sentences containing
                                   ALL of them are replaced
            replacement_sentence:  The sentence that replaces matched sentences
            case_sensitive:        Whether word matching is case-sensitive

        Returns:
            (filtered_text, sentences_deleted_count, sentences_replaced_count)
        """
        if not text.strip():
            return ("", 0, 0)

        delete_list = _parse_words(delete_words)
        replace_list = _parse_words(replace_words)

        cleaned, deleted, replaced = _process_text(
            text=text,
            delete_words=delete_list,
            replace_words=replace_list,
            replacement_sentence=replacement_sentence,
            case_sensitive=case_sensitive,
        )

        print(
            f"[SentenceFilter] deleted={deleted}, replaced={replaced} | "
            f"delete_words={delete_list} | replace_words={replace_list}"
        )
        return (cleaned, deleted, replaced)


# ---------------------------------------------------------------------------
# ComfyUI node registration
# ---------------------------------------------------------------------------

NODE_CLASS_MAPPINGS = {
    "SentenceFilterNode": SentenceFilterNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SentenceFilterNode": "Sentence Filter ✂️",
}
