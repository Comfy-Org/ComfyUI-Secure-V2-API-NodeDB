# Generates nodes/_music_prompt_formulas.py by LIFTING the two measured formulas
# out of the probe files that produced them. Never retype a measured formula: the
# shipped AI Prompt presets were built the same way, and the two are byte-identical
# (checked below), so the node cannot drift from what was measured.
#
# Re-run any time to prove no drift:
#   python gen_music_formulas.py --check
import ast
import io
import json
import os
import sys

REPO = (r"D:\ComfyTest\ComfyUI-Easy-Install\ComfyUI\custom_nodes\ComfyUI-Pixaroma")
TESTS = r"D:\Claude Tests"
OUT = os.path.join(REPO, "nodes", "_music_prompt_formulas.py")
PRESETS = os.path.join(REPO, "assets", "ai_prompt_presets.json")


def lift(path, name):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise SystemExit("not found: %s in %s" % (name, path))


caption = lift(os.path.join(TESTS, "_minimax_music3_formulas.py"), "CAPTION_FORMULA")
lyrics = lift(os.path.join(TESTS, "_minimax_music3_duration.py"), "LYRICS_FORMULA")

# Cross-check against the shipped presets while they still exist. Once those are
# retired this block simply skips, and the probes remain the source of truth.
if os.path.exists(PRESETS):
    data = json.load(io.open(PRESETS, encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("presets", data)
    by = {p.get("name"): p for p in items}
    for key, want in (
        ("MiniMax Music 3 - the caption (Qwen3.5 4B)", caption),
        ("MiniMax Music 3 - the lyrics (Qwen3.5 4B)", lyrics),
    ):
        if key in by and by[key]["formula"] != want:
            raise SystemExit("DRIFT: probe and shipped preset disagree for %r" % key)

BODY = '''"""Music Prompt Pixaroma - the two measured formulas, verbatim.

GENERATED. Do not hand-edit: it is written by
`scripts/gen_music_formulas.py`, which lifts each string out of the probe file
that measured it (`_minimax_music3_formulas.py` for the caption,
`_minimax_music3_duration.py` for the round-three lyrics) with
`ast.literal_eval`. Retyping a measured formula is how a node quietly stops
being the thing that was measured.

The caption scored 6/6 on every axis first time. The lyrics took three rounds;
what is here is round three, which is dependable at the short end (20 runs of a
thirty second song all gave 8 sung lines in 2 sections). Both were measured on
`qwen3.5_4b_int8_convrot.safetensors` - the caption at temperature 0.3 and the
lyrics at 0.8, which is why this node runs two generations with DIFFERENT
sampling rather than one pass with one setting.

Full account: `.claude/patterns/music-prompt.md`.
"""

CAPTION_FORMULA = {caption!r}

LYRICS_FORMULA = {lyrics!r}
'''

text = BODY.format(caption=caption, lyrics=lyrics)

if "--check" in sys.argv:
    have = io.open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    print("IN SYNC" if have == text else "OUT OF SYNC")
    sys.exit(0 if have == text else 1)

# utf-8 with NO BOM and LF endings. A PowerShell redirect writes a BOM here and
# the release preflight rejects it (CLAUDE.md, the v1.4.72 incident).
with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(text)
print("wrote %s (caption %d chars, lyrics %d chars)" % (OUT, len(caption), len(lyrics)))
