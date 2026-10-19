"""
Unit tests for SentenceFilterNode
Run with: python -m pytest tests/ -v
"""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sentence_filter_node import SentenceFilterNode, _process_text, _parse_words


def node():
    return SentenceFilterNode()


# ---------------------------------------------------------------------------
# _parse_words
# ---------------------------------------------------------------------------

class TestParseWords:

    def test_single_word(self):
        assert _parse_words("Watermark") == ["Watermark"]

    def test_multiple_words(self):
        assert _parse_words("blonde, straight, young") == ["blonde", "straight", "young"]

    def test_empty_string(self):
        assert _parse_words("") == []

    def test_strips_whitespace(self):
        assert _parse_words("  hello ,  world  ") == ["hello", "world"]


# ---------------------------------------------------------------------------
# Delete: single trigger word
# ---------------------------------------------------------------------------

class TestDeleteSingleWord:

    def test_removes_sentence_with_trigger(self):
        text = "Beautiful landscape. This image has a Watermark. Enjoy."
        out, deleted, _ = _process_text(text, ["Watermark"], [], "", False)
        assert deleted == 1
        assert "Watermark" not in out
        assert "Beautiful landscape" in out
        assert "Enjoy" in out

    def test_no_match_unchanged(self):
        text = "Hello world. Everything is fine."
        out, deleted, _ = _process_text(text, ["Watermark"], [], "", False)
        assert deleted == 0
        assert out.strip() == text.strip()

    def test_case_insensitive_default(self):
        text = "Normal. watermark lowercase. Done."
        out, deleted, _ = _process_text(text, ["watermark"], [], "", False)
        assert deleted == 1

    def test_case_sensitive_no_match(self):
        text = "Normal. watermark lowercase. Done."
        out, deleted, _ = _process_text(text, ["Watermark"], [], "", True)
        assert deleted == 0

    def test_url_in_trigger_sentence(self):
        text = (
            "A beautiful photo. "
            'The watermark "www.femjoy.com" is in the corner. '
            "She stands in a field."
        )
        out, deleted, _ = _process_text(text, ["watermark"], [], "", False)
        assert deleted == 1
        assert "femjoy" not in out
        assert "beautiful photo" in out
        assert "stands in a field" in out


# ---------------------------------------------------------------------------
# Delete: multiple trigger words (AND logic)
# ---------------------------------------------------------------------------

class TestDeleteMultipleWords:

    def test_all_words_present_deletes(self):
        text = "Nice day. A young woman with straight hair of blonde color. The end."
        out, deleted, _ = _process_text(
            text, ["blonde", "straight", "young"], [], "", False
        )
        assert deleted == 1
        assert "blonde" not in out
        assert "Nice day" in out
        assert "The end" in out

    def test_partial_match_does_not_delete(self):
        """Sentence has only 'blonde' and 'young' but not 'straight' → kept."""
        text = "Nice day. A young blonde woman. The end."
        out, deleted, _ = _process_text(
            text, ["blonde", "straight", "young"], [], "", False
        )
        assert deleted == 0
        assert "young blonde" in out

    def test_multiple_sentences_deleted(self):
        text = (
            "Intro. "
            "A young straight blonde model. "
            "Middle part. "
            "Another young straight blonde photo. "
            "Outro."
        )
        out, deleted, _ = _process_text(
            text, ["young", "straight", "blonde"], [], "", False
        )
        assert deleted == 2
        assert "Intro" in out
        assert "Middle part" in out
        assert "Outro" in out


# ---------------------------------------------------------------------------
# Replace
# ---------------------------------------------------------------------------

class TestReplace:

    def test_replaces_matching_sentence(self):
        text = "Intro. A young woman with straight hair of blonde color. Outro."
        replacement = "A mature woman with brown curly hair"
        out, _, replaced = _process_text(
            text, [], ["blonde", "straight", "young"], replacement, False
        )
        assert replaced == 1
        assert "mature woman" in out
        assert "blonde" not in out
        assert "Intro" in out
        assert "Outro" in out

    def test_no_replace_when_no_match(self):
        text = "Hello. Just a sentence. Done."
        out, _, replaced = _process_text(
            text, [], ["blonde"], "Replacement.", False
        )
        assert replaced == 0
        assert "Just a sentence" in out

    def test_replacement_ends_with_period(self):
        """Replacement sentence should always end with a period."""
        text = "Intro. Young straight blonde. Outro."
        out, _, replaced = _process_text(
            text, [], ["young", "straight", "blonde"],
            "A mature woman with curly hair", False
        )
        assert replaced == 1
        assert "mature woman with curly hair." in out


# ---------------------------------------------------------------------------
# Delete takes priority over replace
# ---------------------------------------------------------------------------

class TestPriority:

    def test_delete_wins_over_replace(self):
        """If a sentence matches both delete and replace words, it is deleted."""
        text = "Intro. A young blonde with watermark. Outro."
        out, deleted, replaced = _process_text(
            text,
            delete_words=["watermark"],
            replace_words=["young", "blonde"],
            replacement_sentence="Replacement.",
            case_sensitive=False,
        )
        assert deleted == 1
        assert replaced == 0
        assert "watermark" not in out
        assert "Replacement" not in out


# ---------------------------------------------------------------------------
# Node integration
# ---------------------------------------------------------------------------

class TestNodeIntegration:

    def test_empty_text_returns_empty(self):
        n = node()
        out, deleted, replaced = n.filter_text("")
        assert out == ""
        assert deleted == 0
        assert replaced == 0

    def test_full_workflow_delete_and_replace(self):
        n = node()
        text = (
            "A beautiful landscape photo. "
            "The watermark www.example.com is visible. "
            "A young woman with straight blonde hair. "
            "Sunset in the background."
        )
        out, deleted, replaced = n.filter_text(
            text=text,
            delete_words="watermark",
            replace_words="young, straight, blonde",
            replacement_sentence="A mature woman with brown curly hair",
            case_sensitive=False,
        )
        assert deleted == 1
        assert replaced == 1
        assert "watermark" not in out.lower()
        assert "example.com" not in out
        assert "mature woman" in out
        assert "beautiful landscape" in out
        assert "Sunset" in out
