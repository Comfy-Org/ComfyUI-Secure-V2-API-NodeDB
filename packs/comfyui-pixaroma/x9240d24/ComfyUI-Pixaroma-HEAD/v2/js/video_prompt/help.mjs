// Video Prompt Pixaroma - help. Convention #16: registering this is what
// makes the orange ? appear in the node selection toolbar and gives the node a
// page in the Help browser. Written for an artist, not a programmer.

export const VIDEO_PROMPT_HELP = {
  title: "Video Prompt Pixaroma",
  tagline: "Write a MiniMax H3 video prompt on your own machine, in one node.",
  sections: [
    {
      heading: "What it does",
      body:
        "MiniMax H3 wants its prompts written in a particular shape, with named " +
        "sections, a soundscape, music, and a strict way of writing anything a " +
        "person says out loud. Getting that right by hand is fiddly, and getting it " +
        "wrong quietly spoils the clip.\n\n" +
        "This node does it for you. You type your idea in plain words, choose how " +
        "long the video should be, and press Generate. It hands back a finished H3 " +
        "prompt, plus the frame count to render it at.\n\n" +
        "It runs entirely on your own machine, using a vision language model that " +
        "sits in your ComfyUI models folder. No account, no key, nothing sent " +
        "anywhere. You download that model once and it is about 5 to 10 GB, so if " +
        "you have never installed one, start with What you need installed below.\n\n" +
        "It comes ready for MiniMax H3, and the wording it follows is yours to " +
        "change. You can rewrite any of it, or switch our length instructions off " +
        "entirely and use your own, for any video model you like.",
    },
    {
      heading: "It changes what it writes based on what you wire in",
      body:
        "You do not pick a mode. The node works it out from the pictures you give " +
        "it, and the banner at the top always says which one it is using.\n\n" +
        "One thing worth knowing: it reads the WIRES, not whether the picture " +
        "actually arrived. If you mute or bypass the loader feeding it, the node " +
        "falls back to text to video. The line above the prompt always reports " +
        "which mode really ran, so if the banner and that line disagree, the line " +
        "is the one telling the truth.",
      defs: [
        ["Nothing wired", "Text to video. It invents the whole scene from your idea."],
        ["A first frame wired", "It looks at that picture, describes what is really in it, and animates it."],
        ["A first and a last frame wired", "It writes the journey from one picture to the other. It joins the two pictures together for you, so they can never end up the wrong way round."],
        ["Only a last frame wired", "Treated the same as a first frame: it describes that picture and animates from it. A wire that quietly did nothing would be worse."],
      ],
    },
    {
      heading: "Writing a good idea",
      bullets: [
        "Plain words are enough. \"a blacksmith hammers glowing steel in a dark forge\" is a complete idea.",
        "If someone speaks, put the spoken words at the END of your idea. Anything written after them tends to be delivered instead of the line itself.",
        "Do not describe the camera in words like drone or close-up unless you mean it. The node knows how to turn those into real camera moves.",
        "Longer clips need a fuller idea. One short sentence does not contain fifteen seconds of things happening.",
      ],
    },
    {
      heading: "Making the idea box bigger",
      body:
        "Three ways, and they all remember what you chose:\n\n" +
        "Drag the node's own corner. The idea box and the prompt box share the "
        + "height, so a taller node gives you more of both.\n\n" +
        "Drag the small bar under the idea box to move the line between the two. "
        + "Pull it down for a long idea, up when you would rather see more of the "
        + "finished prompt. Double-click that bar to put it back where it started.\n\n" +
        "Press Expand for a full-screen box. That is the one for a long idea, or "
        + "for reading something you pasted in. Save keeps it, Cancel or Escape "
        + "throws the edit away.",
    },
    {
      heading: "Length",
      body:
        "The length buttons do far more than set a number. Each one carries its own " +
        "instructions about how much to write and how many things should happen, and " +
        "that is the single setting that changes the result most.\n\n" +
        "One thing worth knowing: 5 seconds is the tightest fit for a speaking idea. " +
        "It writes the spoken line most of the time now, where it used to drop it " +
        "every time, but 8 seconds and 10 seconds are still the surest. The node " +
        "marks the 5 second button when it notices speech in your idea, as a nudge " +
        "rather than a warning, and never stops you picking it. If a line does come " +
        "back missing, Re-roll is usually enough.",
    },
    {
      heading: "The buttons on the node",
      defs: [
        ["Generate", "Runs the workflow and writes the prompt."],
        ["Re-roll", "Generates again with a new seed. This is what to press when a result comes out flat. In Random mode every run already rolls a seed, so there it is simply another Generate."],
        ["Copy", "Puts the finished prompt on the clipboard."],
        ["Expand", "Opens your idea in a full-screen box, for when it is longer than the space on the node. Save keeps what you typed, Cancel and Escape throw it away."],
        ["Free VRAM", "A switch, not a button. Off while you are only writing prompts, so generating again is instant. Turn it on when this node sits in the same workflow as your video model: the language model is unloaded as soon as the prompt is written, handing the memory over to the video. Your prompt is already finished by then, so nothing is lost. On one machine this freed about 17 GB. It greys out and does nothing when a Load CLIP node is wired in, because that model belongs to the loader and may be shared."],
        ["The seed chip", "Click F or R to switch between Fixed, which gives the same prompt every time, and Random, which gives a fresh one on every run. In Fixed you can click the number and type a seed of your own. In Random the number just shows what the last run happened to use."],
        ["The gear", "Opens the settings, where the formulas and the length instructions live."],
      ],
      body:
        "Generate and Re-roll queue the WHOLE workflow, exactly like pressing Run. " +
        "If this node sits in front of your video model, that renders a video every " +
        "time, so mute the video part while you are writing prompts.\n\n" +
        "The line above the prompt reports what the run actually did: the mode, the " +
        "duration, the frame count, the word count and how long it took. If you " +
        "then change the idea it says so, so you never paste the previous one by " +
        "accident.",
    },
    {
      heading: "Reading it back later",
      body:
        "Prompt Reader Pixaroma can pull your IDEA back out of a picture made with " +
        "this node.\n\n" +
        "It cannot give you the finished prompt, and nothing can: ComfyUI saves the " +
        "workflow as it was submitted, and at that moment the model had not written " +
        "anything yet. The idea is the part worth keeping anyway, since it is what " +
        "you would type again. If you want the finished prompt stored with the " +
        "render, wire the text output into a Save Image or Save Video node.",
    },
    {
      heading: "What comes out",
      defs: [
        ["text", "The finished prompt. Wire it into your H3 node."],
        ["frames", "How long to render, already adjusted to the pattern H3 accepts. Wire this into your H3 node's length input so the video is exactly as long as the prompt was written for. Getting those two out of step is the easiest way to spoil a clip."],
        ["seconds", "The true length in seconds, for anything that has to line up with the video, such as an audio track."],
      ],
    },
    {
      heading: "Settings",
      body:
        "An edit takes effect on the very next Run. There is nothing to reload and " +
        "no restart. Because the node cannot know in advance which formula a run " +
        "will use, editing any of them makes every one of these nodes write a fresh " +
        "prompt next time rather than reusing the last one.\n\n" +
        "Your edits are kept outside the plugin folder, so updating Pixaroma never " +
        "overwrites them, and Reset always brings the shipped version back.",
      defs: [
        ["Model", "Which vision model to use. Leave it alone and the node finds one for you. Files that cannot see a picture are greyed out in the list."],
        ["Temperature and Max length", "0.3 is what these formulas were measured at. Higher makes the model start copying the example wording out of the formula itself."],
        ["Formulas", "One for each of the three cases. The pencil edits it, the arrow puts the shipped one back. The number is its length in characters, which is worth watching: these get worse past about 12,000."],
        ["Duration tiers", "The length instructions, per mode. Pick which mode you are editing at the top of that section."],
        ["Video model", "What the frames output has to satisfy. MiniMax H3, Wan, Hunyuan, LTX, or no snapping at all, with the numbers editable underneath for anything not listed."],
        ["Add the length instructions", "On by default. Turn it off to use your own wording without our length guidance being appended. The durations still set the frames and seconds outputs either way. In first and last frame mode the alignment line is kept even with this off, because the formula tells the model to copy it and it has to name your chosen duration."],
        ["Hint when 5s meets a speaking idea", "Turns the 5 second nudge off if you find it in the way. 8 and 10 seconds are still the surest for talking."],
        ["Faster writing (MTP)", "On by default. A model that ships MTP weights (Qwen3.5 files) writes a few words ahead, which is faster; other models ignore it. Turn it off if a run stops with a CUDA error such as \"illegal memory access\": the same as the mtp setting on ComfyUI's Generate Text node."],
        ["Export, Import, Reset all", "Export writes every formula and tier to one file. Import reads one back, which is how you move your wording to another machine or take somebody else's. Reset all puts every shipped formula and tier back."],
      ],
    },
    {
      heading: "What you need installed",
      body:
        "One vision language model, in your ComfyUI/models/text_encoders folder. " +
        "It has to be a VISION model, because the first-frame modes need to " +
        "actually see the picture. A text-only model will load and then quietly " +
        "ignore your images.\n\n" +
        "You do not have to choose one. If the model named in the settings is not " +
        "on your machine, the node picks the best vision model it can find and " +
        "tells you in the console which one it used.",
      defs: [
        ["The one everything was measured against",
         "`qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors`, 10 GB. Every formula and every duration in this node was written and tested against it. Best choice for a 12 GB card or better. Take it from the `comfyui` folder of that repo, not the root: the root holds the raw model, which ComfyUI cannot load as a text encoder."],
        ["For an 8 GB card",
         "`qwen3-vl-4b-heretic_fp8_e4m3fn.safetensors`, 4.8 GB, at the root of the 4B repo. It works, and it follows the formulas less closely, so expect to trim its output or re-roll more often."],
        ["If you would rather not use an uncensored build",
         "Comfy-Org publishes plain Qwen3-VL text encoders. They follow the formulas fine; they just refuse more often on anything spicy."],
        ["Where the file goes",
         "`ComfyUI/models/text_encoders`. Then pick it from the gear on the node, or leave it and the node will find it by itself."],
      ],
      links: [
        ["Qwen3-VL 8B Heretic, ComfyUI files (the tested one)", "https://huggingface.co/DreamFast/Qwen3-VL-8B-Heretic-1.3.0/tree/main/comfyui"],
        ["Qwen3-VL 4B Heretic for ComfyUI", "https://huggingface.co/DreamFast/Qwen3-VL-4b-Heretic-ComfyUI/tree/main"],
        ["Qwen3-VL text encoders from Comfy-Org", "https://huggingface.co/Comfy-Org/Qwen3-VL/tree/main/text_encoders"],
      ],
    },
    {
      heading: "Using a Load CLIP node instead",
      body:
        "The clip input is optional. Wire a Load CLIP node into it and that model " +
        "is used instead of the one in the settings, which is handy when several " +
        "of these nodes should share one loaded model.\n\n" +
        "When a wire is present the settings show \"using the wired CLIP\" and the " +
        "picker is greyed out, so the panel can never claim one model while " +
        "another is doing the work. Load CLIP's own type dropdown does not matter " +
        "here; what matters is that the file is a vision model.\n\n" +
        "One thing to know: with a wire in place the Free VRAM switch does nothing. " +
        "That model belongs to your Load CLIP node and may be shared, so it is not " +
        "this node's to unload.",
    },
  ],
};

const _UNUSED_KEYWORDS = [
  "h3", "minimax", "minimax h3", "prompt", "prompt writer", "llm", "qwen",
  "text to video", "first frame", "last frame", "fflf", "video prompt",
  "write prompt", "prompt generator", "local llm", "vision model",
];
