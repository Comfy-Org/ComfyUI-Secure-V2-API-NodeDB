// Music Prompt Pixaroma - the help page.
//
// Registered here rather than centrally because it is long enough to want to
// live beside the node it describes (Image Compare, Text, XY Plot and Find and
// Replace do the same). The comfyClass key MUST match NODE_CLASS_MAPPINGS.

import { registerNodeHelp } from "../shared/help.mjs";
import { CLASS } from "./core.mjs";

registerNodeHelp(CLASS, {
  title: "Music Prompt Pixaroma",
  tagline: "One idea in, a caption and lyrics out for MiniMax Music 3.",
  sections: [
    {
      heading: "What it does",
      body:
        "A music model needs two different pieces of writing. The caption "
        + "describes how the song should SOUND: the genre, the tempo, the key, "
        + "what the voice is like and which instruments play. The lyrics are the "
        + "words that actually get sung.\n\n"
        + "This node writes both from one idea. It runs a language model you "
        + "already have, on your own machine, twice on a single load: once for "
        + "the caption and once for the lyrics. Nothing is sent anywhere.\n\n"
        + "Wire `caption` and `lyrics` straight into MiniMax Music 3 Text Encode, and "
        + "`duration` into its `max_duration`. That last wire means you set the length "
        + "ONCE, here, where the words are written for it.",
    },
    {
      heading: "Getting started",
      bullets: [
        "Put a language model in your ComfyUI/models/text_encoders folder. This "
        + "node only reads and writes words, so it does NOT need a vision model.",
        "Press the gear on the node and pick it. Both formulas were measured on "
        + "qwen3.5_4b_int8_convrot.",
        "Type your idea in plain words, like a slow acoustic song about coming "
        + "home in the rain.",
        "Set the length, then press Generate.",
      ],
    },
    {
      heading: "Length, and the duration wire",
      body:
        "The music model treats length as a CEILING. It can end a song early, "
        + "but anything past the limit is simply cut off part way through. So a "
        + "lyric written for three minutes against a thirty second setting gets "
        + "chopped.\n\n"
        + "Wire the `duration` output into the music node's `max_duration` and the two "
        + "can never disagree. The highest it accepts is 360 seconds.\n\n"
        + "A song can still come out shorter than you asked. That is the music model "
        + "stopping when the words run out, not a fault: it only sings what it was "
        + "given. Measured over ten songs, nine used the whole length and one stopped "
        + "at three quarters, because that seed happened to write half as many lines.\n\n"
        + "If a song comes out short, press Re-roll. How many lines get written varies "
        + "from one seed to the next, and a fresh seed usually fills the time.",
    },
    {
      heading: "Verses are a request, not a promise",
      body:
        "Left on Auto, the length alone decides the shape, and that is the most "
        + "reliable way to run it. Under forty seconds you get a verse and a "
        + "chorus. Around a minute adds a second verse. Around two minutes adds "
        + "a bridge and a final chorus.\n\n"
        + "Up to about a minute and a half, Auto states that shape outright "
        + "rather than leaving the model to work it out, because that is where it "
        + "was measured to get it wrong in both directions: minute-long songs kept "
        + "coming back with the single verse of a thirty second one, and thirty "
        + "second songs kept opening with an instrumental section they had no room "
        + "for. Saying it plainly took the first from three runs in five to five "
        + "in five, and the second from one in four to four in four.\n\n"
        + "Longer than that, Auto says nothing, because there it already gets it "
        + "right and naming a number made it worse.\n\n"
        + "Ask for a number instead and the model usually obeys, but not always. "
        + "One and two come back exactly as asked. Three sometimes comes back as "
        + "two. That is why the chips stop at three: asking for more does not "
        + "get you more.\n\n"
        + "Asking for verses also OVERRIDES the length shape, so three verses at "
        + "three minutes gives a shorter song than three minutes on Auto would.",
      defs: [
        ["Auto", "The length decides everything. The most dependable setting."],
        ["1 to 3", "Ask for that many verses, each with a chorus."],
        ["Bridge", "Ask for a bridge: one different section, usually near the end."],
        ["Break", "Ask for one instrumental break inside the song, where the "
          + "band plays and nobody sings. It uses up singing time. Do not use "
          + "it on a 30 second song: in testing the chorus was never sung at "
          + "all. It was called Instr. before, and was renamed because it sat "
          + "next to the Instrumental setting and the two mean different "
          + "things."],
        ["Voice / Instrumental", "Voice writes a song with singing. "
          + "Instrumental writes a piece with no singing at all, which runs the "
          + "model once instead of twice and is about two and a half times "
          + "faster."],
      ],
    },
    {
      heading: "Using a different model",
      body:
        "Everything this node writes comes from a FORMULA SET: the two "
        + "instructions, plus the sampling that makes them work, under a name "
        + "saying what they are for. The one that ships is `MiniMax Music 3 "
        + "(Qwen3.5 4B int8)`, which names the music model it writes for and the "
        + "language model it was measured on.\n\n"
        + "On a different language model the wording may need changing. Press the "
        + "gear and you will find it all there, nothing hidden.\n\n"
        + "A set also remembers which language model it was measured on. If you "
        + "have that model it is chosen for you; if you do not, the line under "
        + "the picker says so in amber and your own model is left alone, so a "
        + "set from somebody else's machine can never point this node at "
        + "something that is not there. A model on the clip wire always wins.",
      defs: [
        ["The set picker", "Every set you have. An orange dot ships with "
          + "Pixaroma, a grey one is yours. Picking one copies its wording, its "
          + "numbers AND its model onto the node, so this is also how you go "
          + "back after changing something."],
        ["Edit", "Opens that instruction in a full screen box. It starts from "
          + "whatever the node is using now, so you can change a line rather "
          + "than write from nothing. Save it back unchanged and the node keeps "
          + "following the built-in one."],
        ["Save as", "Keeps the current wording and numbers under a name of your "
          + "own. It suggests `(mine)` on the end when you started from the "
          + "shipped set. After changing one of your own sets, its name is "
          + "already filled in: press Enter to update it, or type a new name to "
          + "keep both. Typing the name of another set of yours asks before "
          + "replacing it. Your sets live in one file in your ComfyUI user "
          + "folder, so a reinstall of the node does not touch them."],
        ["Delete", "Removes one of yours. The set that ships with Pixaroma "
          + "cannot be deleted or overwritten, so there is always a way back."],
        ["temp", "How much the model improvises. The caption wants a low number "
          + "so it states facts; the lyrics want a high one or every song rhymes "
          + "the same way."],
        ["max len", "How much it may write before stopping. Raise it a lot for a "
          + "model that thinks out loud before answering, or it spends the whole "
          + "budget thinking and writes nothing."],
        ["Faster writing (MTP)", "Qwen3.5 files, like the one the shipped set "
          + "was measured on, carry an extra MTP part that writes a few words "
          + "ahead. On some cards and model files that crashes with a CUDA error "
          + "such as \"illegal memory access\": turn it off and the run goes "
          + "through, a little slower. The same as mtp = off on ComfyUI's Generate "
          + "Text node. A set never changes it, because it is about your graphics "
          + "card, not the recipe."],
      ],
    },
    {
      heading: "Writing your own instruction",
      body:
        "The two instructions do different jobs and each has a few things it "
        + "must keep saying, whatever else you change.\n\n"
        + "THE CAPTION describes the SOUND and never the words. It has to come "
        + "back as three labelled parts, in this order: Global Metadata (genre, "
        + "a tempo in BPM, a key, the mood, how the recording should sound), "
        + "Vocal Details (whose voice, what it is like, any harmonies), and "
        + "Arrangement (which instruments carry it, what the bass and drums do). "
        + "It must never write lyrics, section tags or quoted words, because "
        + "those go in the other field.\n\n"
        + "THE LYRICS are sung out loud, every single line of them. Anything in "
        + "brackets gets sung too, so a stage direction like a slow piano begins "
        + "will be sung by a person. Lay it out with a section tag on its own "
        + "line before each part, from [Intro] [Verse] [Pre-Chorus] [Chorus] "
        + "[Post-Chorus] [Bridge] [Instrumental] [Solo] [Outro]. A tag can stand "
        + "alone with nothing under it, which means the band plays and nobody "
        + "sings, and that still uses up time.\n\n"
        + "Both instructions should say to write nothing else: no explanation, "
        + "no markdown, no repeating the idea back.",
      bullets: [
        "The node adds your length and shape to the end of the idea before it "
        + "asks, so your instruction does not need to mention either.",
        "Change one thing at a time and run the same idea on a couple of seeds. "
        + "Wording that reads better is not always wording that works better.",
        "If a result looks wrong, try the temperature before rewriting anything. "
        + "The shipped caption wording writes cleanly at 0.3 and rambles at 0.7 "
        + "with not a word changed.",
        "Do not put examples inside a rule. Naming a few instruments tends to "
        + "put those exact instruments into every song.",
        "Say what you DO want rather than what you do not. Telling this model "
        + "not to leave a section empty was measured making things worse, once "
        + "producing 26 sung lines for a thirty second song.",
      ],
    },
    {
      heading: "The buttons on the node",
      defs: [
        ["Caption / Lyrics", "Which of the two you are looking at. Both are "
          + "written every run, this only picks what the box shows."],
        ["Expand", "Write the idea in a full screen box."],
        ["The bar between the boxes", "Drag it to give the idea more or less "
          + "room. Double click puts it back."],
        ["The seed", "Click the number to type one. F keeps the same seed, so an "
          + "unchanged node is cached and Run is instant. R rolls a new one every "
          + "run, so every run is a different song."],
        ["Tags", "Opens your tag library, the same one Prompt Pixaroma and AI "
          + "Prompt use. Anything you save there can be used in all three."],
        ["Re-roll", "A new seed, then run again. The quickest way to try another "
          + "version of the same idea."],
        ["Copy", "Copies whichever of the two you are looking at."],
        ["Free VRAM", "Unloads the model when this node finishes. Turn it on when "
          + "a music model has to fit in the same card afterwards."],
        ["Generate", "Queues the whole workflow, the same as pressing Run."],
      ],
    },
    {
      heading: "Tags in your idea",
      body:
        "Your idea box understands the same @tags as Prompt Pixaroma and AI "
        + "Prompt, out of the same library, so a phrase you saved once can be "
        + "used in all three. Press Tags to open it.\n\n"
        + "They are swapped for their real words before the model is asked "
        + "anything, so it reads finished English and never sees an @ sign. Only "
        + "your IDEA is read for tags: the instructions in the settings are left "
        + "alone, because prose written for a model often contains things like "
        + "\"step #1\" that are not meant to be tags.",
      defs: [
        ["@name", "Your saved snippet, exactly as you wrote it."],
        ["*Category", "One random tag out of that category, rolled fresh on every Run."],
        ["#name", "One random line out of that tag, rolled fresh on every Run."],
      ],
    },
    {
      heading: "Reading the colours as you type",
      body:
        "The colour tells you what a word will become, so you can see at a "
        + "glance whether a tag is real before you Run anything.",
      defs: [
        ["Orange", "An @tag that exists."],
        ["Green", "A *category that exists and has something in it."],
        ["Violet", "A #list that exists and has lines in it."],
        ["A red wavy underline", "That name is not in your library, so it will "
          + "be sent to the model as the literal text you typed. Every name looks "
          + "like this while you are still typing it, and it takes its real "
          + "colour the moment it matches."],
      ],
    },
    {
      heading: "Voice or Instrumental",
      body: "The Music row switches between a song with singing and a piece of "
        + "instrumental music. On Instrumental the node runs the model ONCE "
        + "instead of twice, so it is about twice as fast: there are no words "
        + "to write, so it only writes the caption and sends [Instrumental] as "
        + "the lyrics.",
      bullets: [
        "The verses, Bridge and Break controls dim on Instrumental, because "
        + "there are no sections to ask for. They keep your settings and come "
        + "back when you switch to Voice.",
        "Do not confuse Instrumental with the Break button. Break adds one "
        + "instrumental section to a song that still has singing. Instrumental "
        + "means no singing anywhere in the piece.",
        "Usually there is no voice at all, but sometimes a stray sound gets "
        + "through: across four test renders in two very different styles, "
        + "three had no voice and one had a single “aah” near the end. "
        + "Re-roll the seed if you get one.",
        "It works because the caption never mentions voices at all. That is not "
        + "an oversight: a caption that said no singing, no humming, no vowel "
        + "sounds produced humming every time it was tried. Naming the thing "
        + "summons it. If you write your own caption for an instrumental, say "
        + "nothing about vocals rather than ruling them out.",
        "With no singer, something has to carry the tune, so the instrumental "
        + "caption names one instrument that states the theme, develops it and "
        + "returns to it at the end.",
      ],
    },
    {
      heading: "What the caption controls, and what the lyrics control",
      body: "These are two different jobs and mixing them makes songs worse. "
        + "The caption decides how the music SOUNDS. The lyrics decide the "
        + "words and the order of the sections, and nothing else.",
      bullets: [
        "Backing vocals, harmonies, instruments, tempo and production all go in "
        + "the CAPTION. MiniMax does not support the round brackets some other "
        + "music tools use for backing vocals: if you write (love) in the "
        + "lyrics, the singer sings the word love. Ask for harmonies in the "
        + "caption instead and you get them.",
        "Square brackets in the lyrics are SECTION TAGS and nothing else: "
        + "[Intro] [Verse] [Pre-Chorus] [Chorus] [Post-Chorus] [Bridge] "
        + "[Instrumental] [Solo] [Outro]. Writing a description inside them, "
        + "such as [soft piano plays alone], does not give you soft piano. "
        + "MiniMax's own guide warns that describing instruments inside the "
        + "lyrics confuses where the sections start and end.",
        "A section tag on its own with no words under it means the band plays "
        + "and nobody sings, which is how you get an intro or a break. It still "
        + "uses up time.",
        "Do NOT use the Break button on a 30 second song. Tested by ear: the "
        + "same song without it sang all four lines in 23 seconds, and with it "
        + "the chorus was never sung at all and the song cut off. The "
        + "instrumental time does not politely sit at the end either, it "
        + "spreads through the whole song, so a 15 second opening arrives "
        + "before the first word. There is more room at 60 seconds and above. "
        + "Also avoid asking for a bridge and an instrumental section together "
        + "at 60 seconds, because that is already five sections.",
        "The lyrics do not rhyme reliably, and that is the model rather than "
        + "the wording. Asking it to rhyme was measured across ninety runs, "
        + "along with a lower temperature and a worked example, and none of "
        + "them beat chance. It rhymes about four line pairs in ten whatever "
        + "you do, and one seed can give you a fully rhymed song where the next "
        + "gives you none. Re-roll until you get one you like.",
      ],
    },
    {
      heading: "Good to know",
      bullets: [
        "With no model chosen it passes your text straight through to both "
        + "outputs, so you can drop it into a working graph and set it up "
        + "afterwards without breaking anything. The banner always says which it "
        + "is about to do.",
        "Two runs on one load is why it takes about twice as long as a single "
        + "prompt node. The model is only loaded once.",
        "The lyrics are written knowing the caption, so the words match the mood "
        + "the caption just described.",
        "Wire a model into the clip input and it is used instead of the one in "
        + "the settings. Free VRAM is skipped then, because that model belongs to "
        + "the loader you placed.",
        "The wording of both instructions is built in and was measured rather "
        + "than guessed, so there is no formula to write. If you want to write "
        + "your own, AI Prompt Pixaroma is the node for that.",
      ],
    },
  ],
});
