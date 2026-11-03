"""Prompt templates and the prompt builder for H3 Timeline Pixaroma. Pure text, no torch.

Each scene of the timeline is a SHORT line the user writes ("sways and dances in place, arms open wide"). It goes
into one of the tested EP41 prompts (Sing / Talk) in place of the sentence that described the movement, so the long
prompt H3 needs stays the same and only the action changes per scene. "Act" is the same shape with no audio track:
H3 makes the sound itself.

A scene picture is either a NEW LOOK (the same shot with a change: it becomes <Picture 1> from that scene on) or an
ADDED PERSON (any photo: it becomes <Picture 2>, <Picture 3>... and gets its own <Subject N> line). Both carry on
into the later scenes until another picture replaces the look. Measured 2026-10-22 (research_long_video_2.md,
"TIMELINE TEST").
"""
from __future__ import annotations

MODES = ("Sing", "Talk", "Act")
SCENE_SLOT = "{scene}"
PEOPLE_SLOT = "{people}"

_PIC1 = ("<Picture 1> is the first frame and composition anchor for [Shot 1], defining the complete visible image exactly "
         "as supplied, including the framing, camera viewpoint, subject placement, subject scale, crop, "
         "foreground-to-background relationship, whatever forms the area behind and around the subject, lighting, "
         "shadows, colors, gradients, depth cues, and overall scene composition. Its rendering style, whether "
         "photographic, illustrated, stylised, or three-dimensional, is part of what is preserved.")
_SUBJ1 = ("<Subject 1> is the main visible {role} figure defined by <Picture 1>, preserved exactly as it appears there. "
          "Whatever <Subject 1> already is remains unchanged: its form, proportions, head shape, facial structure, "
          "surface, colors, markings, and every visible garment, covering, accessory, and detail. Nothing is added "
          "that is not already visible in <Picture 1>, and nothing visible is removed, replaced, simplified, or "
          "reinterpreted.")
_SUBJ2 = ("<Subject 2> is the complete visible area behind, beneath, beside, and around <Subject 1> as defined by "
          "<Picture 1>, preserving its exact colors, surfaces, objects if any are present, spatial layout, lighting, "
          "shadows, gradients, and depth. Whatever that area looks like in <Picture 1> is exactly what it looks like in "
          "the target video, including its overall tone and brightness, and it is never exchanged for a different kind "
          "of surrounding. If objects are present, exactly those objects remain, and no further ones appear.")
_RET = ("<Picture 1> ([Shot 1] first frame): fully_preserved - the supplied image remains the composition anchor, "
        "retaining its viewpoint, framing, crop, subject placement, subject scale, complete surroundings, lighting, and "
        "rendering style.\n"
        "<Subject 1> (appears in [Shot 1]): fully_preserved - the appearance shown in the reference remains intact in "
        "every visible respect, with only {motion} permitted.\n"
        "<Subject 2> (appears in [Shot 1]): fully_preserved - the referenced surroundings remain visually identical, "
        "with nothing substituted, added, or removed.")
_SHOT = ("The target video develops directly from the complete supplied image in <Picture 1>, preserving its rendering "
         "style, color treatment, lighting, composition, and full visible scene. <Picture 1> is the actual starting "
         "frame, not merely an appearance reference for the foreground.\n"
         "[Shot 1] The shot begins from <Picture 1> and the camera holds completely still for the entire clip, keeping "
         "the exact viewpoint, framing, crop, subject scale, and placement of the reference image. <Subject 1> keeps "
         "the exact appearance established in <Picture 1> in every visible respect, and no feature, marking, covering, "
         "or accessory is introduced that is not already present there. <Subject 2> keeps the complete visible area "
         "exactly as referenced, including its {surfaces}tonal transitions, gradients, shadows, lighting direction, and "
         "depth. <Subject 1> is never lifted out of the supplied scene and placed into a newly generated one, and the "
         "surroundings are never exchanged for a different setting. The tone and brightness of the area around "
         "<Subject 1> match <Picture 1> exactly, neither darker nor lighter. The camera remains fixed, with no zoom, "
         "push in, pull out, pan, truck, tilt, arc, tracking movement, reframing, or composition drift.")

SING = (
    "subject_definitions:\n" + _PIC1 + "\n" + _SUBJ1.format(role="performing") + "\n" + _SUBJ2 + "\n" + PEOPLE_SLOT +
    "<Audio 1> is the complete supplied song reused as the audio for [Shot 1], containing both sung passages and "
    "passages with no voice in them, preserving its original timing, phrasing, rhythm, and character.\n\n"
    "summary:\n[keyframe completion + audio reuse] The target video begins from <Picture 1> and animates <Subject 1> "
    "singing along to the vocal line of <Audio 1> in one continuous fixed-camera shot, moving lightly in place to the "
    "music while preserving the supplied framing, the exact appearance of <Subject 1>, and the complete visible area "
    "represented by <Subject 2>.\n\n"
    "retention_analysis:\n" + _RET.format(motion="natural singing and light rhythmic motion") + "\n"
    "<Audio 1>: fully_copy - the supplied song is reused directly with its original timing, phrasing, rhythm, and "
    "character.\n\n"
    "detailed_description:\n" + _SHOT.format(surfaces="surfaces, ") + " <Subject 1> (S1) sings along to <Audio 1>. "
    "The mouth opens and shapes words only while a voice is actually audible in <Audio 1>, matching the sung "
    "syllables, the phrasing, and the held notes. Whenever <Audio 1> has no voice in it, during an introduction, an "
    "instrumental passage, a break between verses, or the ending, the mouth closes and rests in a natural non-singing "
    "expression, and <Subject 1> simply listens and moves gently rather than mouthing the instruments. Between sung "
    "phrases the mouth relaxes briefly before the next line begins. " + SCENE_SLOT + " <Subject 1> stays in the same "
    "spot within the frame, does not step, walk, spin, jump, lean out of frame, or change the composition, and the feet "
    "remain planted. Flexible details such as clothing, hair, ears, or other loose elements show only slight natural "
    "secondary motion in response to the movement. <Subject 2> remains stable throughout, with no transformation, "
    "replacement, recoloring, expansion, or change of location. When <Audio 1> ends, <Subject 1> closes the mouth, "
    "settles out of the movement, and returns to a relaxed still pose while the original framing and complete "
    "referenced scene remain recognizable.\n\n"
    "overall_soundscape:\n<Audio 1> remains the directly reused primary audible layer. No additional environmental or "
    "physical-action sounds are added over the reused recording.\n\n"
    "non_diegetic_music:\n<Audio 1> is itself the music and is reused directly. No additional music is generated.")

TALK = (
    "subject_definitions:\n" + _PIC1 + "\n" + _SUBJ1.format(role="speaking") + "\n" + _SUBJ2 + "\n" + PEOPLE_SLOT +
    "<Audio 1> is the complete supplied speech recording reused as the vocal performance for <Subject 1> (S1), "
    "preserving its original timing, pauses, cadence, delivery, and voice character.\n\n"
    "summary:\n[keyframe completion + audio reuse] The target video begins from <Picture 1> and animates <Subject 1> "
    "speaking in one continuous fixed-camera shot, preserving the supplied framing, the exact appearance of "
    "<Subject 1>, and the complete visible area represented by <Subject 2>, with <Audio 1> reused directly for "
    "synchronized speech.\n\n"
    "retention_analysis:\n" + _RET.format(motion="natural speech-related motion") + "\n"
    "<Audio 1>: fully_copy - the supplied recording is reused directly with its original timing, pauses, cadence, "
    "delivery, and voice character.\n\n"
    "detailed_description:\n" + _SHOT.format(surfaces="colors, surfaces, ") + " From the beginning of the reused vocal "
    "performance, <Subject 1> (S1) speaks using the directly reused <Audio 1> signal, and the mouth moves clearly "
    "through every audible syllable, staying synchronized with the original timing, pauses, rhythm, and cadence. "
    "During brief pauses the mouth relaxes naturally before resuming. " + SCENE_SLOT + " Flexible details such as "
    "clothing, hair, or other loose elements show only slight natural secondary motion. <Subject 2> remains stable "
    "throughout, with no transformation, replacement, recoloring, expansion, or change of location. When <Audio 1> "
    "ends, <Subject 1> closes the mouth, returns to a relaxed non-speaking expression, and settles naturally while the "
    "original framing and complete referenced scene remain recognizable.\n\n"
    "overall_soundscape:\n<Audio 1> remains the directly reused primary audible layer. No additional environmental or "
    "physical-action sounds are added over the reused recording.\n\n"
    "non_diegetic_music:\nN/A")

ACT = (
    "subject_definitions:\n" + _PIC1 + "\n" + _SUBJ1.format(role="") .replace("visible  figure", "visible figure") +
    "\n" + _SUBJ2 + "\n" + PEOPLE_SLOT + "\n"
    "summary:\n[keyframe completion] The target video begins from <Picture 1> and animates <Subject 1> in one "
    "continuous fixed-camera shot, preserving the supplied framing, the exact appearance of <Subject 1>, and the "
    "complete visible area represented by <Subject 2>, with quiet natural sound.\n\n"
    "retention_analysis:\n" + _RET.format(motion="the natural motion described below") + "\n\n"
    "detailed_description:\n" + _SHOT.format(surfaces="surfaces, ") + " " + SCENE_SLOT + " <Subject 1> stays in the "
    "same spot within the frame and does not change the composition. Flexible details such as clothing, hair, or other "
    "loose elements show only slight natural secondary motion in response to the movement. <Subject 2> remains stable "
    "throughout, with no transformation, replacement, recoloring, expansion, or change of location.\n\n"
    "overall_soundscape:\nOnly a very quiet, steady room tone, the same from the first frame to the last. No music, no "
    "speech, no singing, no sound effects.\n\n"
    "non_diegetic_music:\nNone. No music is generated.")

TEMPLATES = {"Sing": SING, "Talk": TALK, "Act": ACT}

ROLE_LOOK = "look"        # the same shot with a change: becomes <Picture 1> from this scene on
ROLE_PERSON = "person"    # any photo of someone (or something) who joins: <Picture 2>, <Picture 3>...


_PRONOUNS = ("she", "he")
_OTHER_LEADS = ("they", "a", "an", "the", "her", "his", "their", "someone", "somebody", "everyone", "another", "both",
                "two", "then", "now", "suddenly", "slowly", "meanwhile", "behind", "beside", "next", "in", "at", "on")


def scene_line(words) -> str:
    """The user's words for one scene as the sentence that replaces the template's movement sentence.

    MEASURED 2026-10-22: the words must read as what <Subject 1> does "throughout the clip" (each window sees its
    scene as the whole clip). A neutral "What happens in this part of the clip: smiles and waves" gave ONE short
    wave in 10 s; "Throughout the clip <Subject 1> smiles warmly and waves..." waved for the whole scene. So a line
    that starts with a verb gets <Subject 1> in front, "She / He" becomes <Subject 1>, and a line about someone else
    or several people ("A man walks in...", "They laugh") is kept as it is."""
    w = " ".join(str(words or "").split())
    if not w:
        return ("Throughout the clip <Subject 1> moves lightly and naturally in place, with small weight shifts and "
                "small head movements.")
    if w[-1] not in ".!?":
        w += "."
    first = w.split(" ", 1)[0].strip(",.;:!?").lower()
    if first in _PRONOUNS:
        return "Throughout the clip <Subject 1>" + w[len(w.split(" ", 1)[0]):]
    if first in _OTHER_LEADS or w[0] == "<":
        return "Throughout the clip, " + (w if w[0] == "<" else w[0].lower() + w[1:])
    return "Throughout the clip <Subject 1> " + w[0].lower() + w[1:]


def person_line(subject_n, picture_n) -> str:
    return ("<Subject {s}> is the person shown in <Picture {p}>, preserved exactly as they appear there: their face, "
            "hair, body, and clothing. They join <Subject 1> in the same scene as the description below says.\n"
            ).format(s=subject_n, p=picture_n)


def people_sentence(n_people, entering=(), arrived=()) -> str:
    """Said for the user after their scene words. MEASURED 2026-10-22: plain words ("A man walks in from the
    right...") with only the <Subject 3> definition brought him in as a sliver at the edge for one second; words
    that NAMED him ("<Subject 3>, the man from <Picture 2>, walks into the frame...") brought him in properly.
    `arrived` = people who came in earlier in this SAME scene: its later windows (a long scene is split) must not
    bring them in again (measured 10-22, t4_room: he faded out and walked in a second time at the split)."""
    out = []
    for k in range(max(0, int(n_people))):
        s, p = 3 + k, 2 + k
        if k in entering:
            out.append("<Subject {s}>, the person in <Picture {p}>, comes into the frame in this part and then stays "
                       "clearly visible in it.".format(s=s, p=p))
        elif k in arrived:
            out.append("<Subject {s}>, the person in <Picture {p}>, has already come into the frame: from the first "
                       "frame of this part they stand where they arrived, clearly visible for the whole clip."
                       .format(s=s, p=p))
        else:
            out.append("<Subject {s}>, the person in <Picture {p}>, is still in the frame for the whole clip, clearly "
                       "visible, in the same place as at the start of this part.".format(s=s, p=p))
    return (" " + " ".join(out)) if out else ""


# Scenes after the first are a LATER moment of the same shot. Measured 2026-10-22: with "<Picture 1> is the actual
# starting frame" in every scene, a man who had just walked in was gone again in the next scene (its windows start
# again from the start picture, where she is alone), with a 1.6 s and with a 3 s overlap alike.
CONTINUE = (
    ("<Picture 1> is the first frame and composition anchor for [Shot 1]",
     "<Picture 1> is the appearance and composition reference for [Shot 1]"),
    ("The target video begins from <Picture 1> and animates",
     "The target video continues the same unbroken shot of <Picture 1> and animates"),
    ("<Picture 1> ([Shot 1] first frame): fully_preserved - the supplied image remains the composition anchor",
     "<Picture 1> ([Shot 1] appearance reference): fully_preserved - the supplied image remains the composition "
     "reference"),
    ("The target video develops directly from the complete supplied image in <Picture 1>, preserving",
     "The target video keeps the complete supplied scene of <Picture 1>, preserving"),
    ("<Picture 1> is the actual starting frame, not merely an appearance reference for the foreground.",
     "This clip is a later moment of the same continuous shot: it picks up exactly where the moment before it left "
     "off, with the same pose, the same people and the same positions, while <Picture 1> sets the look, the framing "
     "and the scene."),
    ("[Shot 1] The shot begins from <Picture 1> and the camera holds", "[Shot 1] The camera holds"),
)


def build_prompt(mode, words, n_people, entering=(), later=False, arrived=()) -> str:
    """The full prompt for one scene: the template, the scene sentence (+ who is in the frame), a <Subject N> line
    per added person. `entering` = the indexes (0 = the first added person) of people who first appear in this
    scene; `later` = any scene after the first (worded as a later moment of the same shot, CONTINUE); `arrived` =
    for a later window of a split scene, the people who came in earlier in that scene (people_sentence)."""
    tpl = TEMPLATES.get(mode, SING)
    if later:
        for a, b in CONTINUE:
            tpl = tpl.replace(a, b)
    people = "".join(person_line(3 + k, 2 + k) for k in range(max(0, int(n_people))))
    return tpl.replace(PEOPLE_SLOT, people).replace(
        SCENE_SLOT, scene_line(words) + people_sentence(n_people, entering, arrived))
