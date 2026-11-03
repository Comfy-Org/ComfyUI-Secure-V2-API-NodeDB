"""AI Prompt Pixaroma - presets: a formula PLUS the settings that make it work.

A formula on its own is half a recipe. The Krea 2 formula was measured writing
gibberish at temperature 0.7 and doing the job cleanly at 0.3 on the same model
and the same words, so shipping the text without the number would have shipped
a formula that looks broken. A preset carries both.

WHERE THINGS LIVE, and why it is ONE file each rather than one file per preset:

    shipped   <plugin>/assets/ai_prompt_presets.json
    yours     <ComfyUI user dir>/pixaroma/ai_prompt_presets.json

A preset NAME is user text, and a name that becomes a FILENAME is the single
most common way a save feature turns into a path traversal (path-containment.md
#1: an absolute right-hand side silently discards the base). Keeping every user
preset inside one known JSON file means no path is ever built from user input at
all - there is nothing to contain, rather than something contained carefully.

Yours live outside the plugin folder for the same reason the Civitai key does:
the plugin folder is a git working tree, and a Manager reinstall would wipe it.

Nothing here is read at RUN time. Loading a preset copies its values onto the
node, so Python only ever sees the node's own state - which is why a preset can
never affect a render, only what the browser puts on the node.
"""
import json
from ._ai_prompt_helpers import bytes_or_none
import os
import threading

MAX_NAME = 80
MAX_FORMULA = 200_000
MAX_NOTE = 400
MAX_PRESETS = 200

# Exactly the settings a preset may carry. The idea, the seed, the join order
# and the separator are deliberately NOT here: those belong to the workflow and
# the wiring, not to the recipe. release_model is a per-workflow memory choice,
# and mtp is about the user's graphics card (ai-prompt.md #34).
SETTING_KEYS = (
    "temperature", "max_length", "top_k", "top_p", "min_p",
    "repetition_penalty", "presence_penalty", "do_sample", "thinking",
    "use_default_template", "system_formula",
)

_ASSET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "assets", "ai_prompt_presets.json")


def user_store_path():
    """<ComfyUI user dir>/pixaroma/ai_prompt_presets.json, or None if unknown."""
    try:
        import folder_paths
        base = folder_paths.get_user_directory()
    except Exception:
        return None
    if not base:
        return None
    return os.path.join(base, "pixaroma", "ai_prompt_presets.json")


def _clean_text(value, cap):
    if not isinstance(value, str):
        return ""
    return value[:cap]


def normalise(raw):
    """One preset dict with every field present and bounded, or None if unusable.

    A preset with no name or no formula is dropped rather than repaired: a
    nameless entry cannot be picked and a formula-less one does nothing.
    """
    if not isinstance(raw, dict):
        return None
    name = _clean_text(raw.get("name"), MAX_NAME).strip()
    formula = _clean_text(raw.get("formula"), MAX_FORMULA)
    if not name or not formula.strip():
        return None
    settings = {}
    src = raw.get("settings")
    if isinstance(src, dict):
        for key in SETTING_KEYS:
            if key in src:
                settings[key] = src[key]
    return {
        "name": name,
        "note": _clean_text(raw.get("note"), MAX_NOTE).strip(),
        "model_hint": _clean_text(raw.get("model_hint"), 200).strip(),
        # Recorded so a row can show a size even when that model is not on disk
        # - which is when you most want it, deciding whether to download. Older
        # stored presets simply have None and show nothing.
        "model_bytes": bytes_or_none(raw.get("model_bytes")),
        "formula": formula,
        "settings": settings,
    }


def _read_checked(path, normalise_fn=None):
    """(presets, ok).

    ok is False ONLY when the file exists and could not be understood. That
    distinction is load-bearing: "you have no presets" and "your presets could
    not be read" look identical to a caller that only gets a list, and the
    consequence was total, silent data loss. A corrupt file read as [] means
    the next save writes ONE preset over everything the user ever kept, with
    no message at any point (reference_lazy_store_write_back_destroys_data).
    So an unreadable file returns ok False, and the write path refuses.

    utf-8-sig because a hand-edited file saved by a Windows editor carries a
    BOM, which plain utf-8 rejects at byte one - this pack has been bitten by
    exactly that before. It reads BOM-less UTF-8 identically.
    """
    # `normalise_fn` exists ONLY so Music Prompt can share this guard. Its sets
    # carry `caption` and `lyrics` where a preset carries `formula`, so with this
    # module's own normalise every entry was dropped and the "not one usable
    # entry" branch below correctly reported a freshly-written file as
    # unreadable. Defaulting to normalise keeps every existing call identical.
    normalise_fn = normalise if normalise_fn is None else normalise_fn
    if not path or not os.path.isfile(path):
        return [], True
    try:
        # An EMPTY file holds nothing to protect, and refusing to write over it
        # would lock the user out of their own library forever with no way back
        # but deleting it by hand. Before this module distinguished the two
        # cases it self-healed on the next save; keep that.
        if os.path.getsize(path) == 0:
            return [], True
    except OSError:
        pass
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except Exception:
        # A corrupt or hand-edited file must not take the picker down with it.
        return [], False
    items = data.get("presets") if isinstance(data, dict) else data
    if not isinstance(items, list):
        # A shape we do not understand is NOT an empty library. It could be a
        # future schema, so say so rather than offering to overwrite it.
        return [], False
    out = []
    for item in items[:MAX_PRESETS]:
        one = normalise_fn(item)
        if one:
            out.append(one)
    if items and not out:
        # The container looked right but NOT ONE entry was usable. That is the
        # shape a schema bump actually takes - same "presets" key, renamed item
        # fields - and it slips past the top-level check above, so reading it
        # as an empty library is how the next save would destroy it. The
        # "items and" half is load-bearing: deleting your last preset writes a
        # genuinely empty list, and that file must stay readable.
        return [], False
    return out, True


def _read(path):
    return _read_checked(path)[0]


def load_shipped():
    return _read(_ASSET)


def load_user():
    return _read(user_store_path())


def user_readable():
    """False when the user's file exists but could not be understood, so the
    picker can say that instead of showing an empty library."""
    return _read_checked(user_store_path())[1]


def _write_user(items):
    path = user_store_path()
    if not path:
        return False
    # The temp name carries pid AND thread id: a bare ".tmp" is shared by every
    # writer, so two ComfyUI instances pointed at one user directory can have
    # each truncate the other's half-written file and then both replace, which
    # lands exactly in the corrupt-file case above
    # (reference_shared_temp_name_needs_thread_id).
    tmp = "%s.%d.%d.tmp" % (path, os.getpid(), threading.get_ident())
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"version": 1, "presets": items}, fh,
                      indent=2, ensure_ascii=False)
        os.replace(tmp, path)   # atomic, so a crashed PROCESS cannot truncate it
        return True
    except Exception:
        return False
    finally:
        # A failure mid-dump (a lone surrogate in a name will do it) otherwise
        # leaves the temp on disk forever. os.replace has already consumed it
        # on the happy path, so this only ever fires after a failure.
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


# Refusing to write beats writing: the user can move one file aside, but they
# cannot get back a library that was silently replaced by a single entry.
_UNREADABLE = ("Your presets file could not be read, so nothing was saved "
               "rather than overwrite what is inside it. Move this file "
               "somewhere safe and try again:\n%s")


def save_user(raw):
    """Add or replace one of the user's own presets. Returns (ok, message)."""
    one = normalise(raw)
    if not one:
        return False, "A preset needs a name and a formula."
    items, readable = _read_checked(user_store_path())
    if not readable:
        return False, _UNREADABLE % (user_store_path() or "the presets file")
    # Replace by name, case-insensitively, so saving twice under the same name
    # updates rather than quietly making a second entry that looks identical.
    lowered = one["name"].lower()
    items = [p for p in items if p["name"].lower() != lowered]
    if len(items) >= MAX_PRESETS:
        return False, "That is as many presets as this can hold."
    items.append(one)
    items.sort(key=lambda p: p["name"].lower())
    if not _write_user(items):
        return False, "Could not write the presets file."
    return True, "Saved."


def delete_user(name):
    """Remove one of the user's own presets. Shipped ones cannot be deleted."""
    if not isinstance(name, str) or not name.strip():
        return False, "No name given."
    lowered = name.strip().lower()
    items, readable = _read_checked(user_store_path())
    if not readable:
        return False, _UNREADABLE % (user_store_path() or "the presets file")
    kept = [p for p in items if p["name"].lower() != lowered]
    if len(kept) == len(items):
        return False, "There is no preset saved under that name."
    if not _write_user(kept):
        return False, "Could not write the presets file."
    return True, "Deleted."
