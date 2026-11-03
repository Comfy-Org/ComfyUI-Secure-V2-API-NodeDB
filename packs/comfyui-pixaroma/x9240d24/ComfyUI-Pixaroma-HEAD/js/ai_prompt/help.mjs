// AI Prompt Pixaroma - help. Convention #16: registering this is what makes
// the orange ? appear in the node selection toolbar and gives the node a page
// in the Help browser. Written for an artist, not a programmer.
//
// It deliberately covers the two questions that are impossible to answer by
// looking at the node - what a duplicate carries, and whether two nodes load
// the model twice - because getting either wrong wastes real time and memory.

export const AI_PROMPT_HELP = {
  title: "AI Prompt Pixaroma",
  tagline: "Run a language model on your own machine with an instruction you save on the node.",
  sections: [
    {
      heading: "What it does",
      body:
        "You give this node a model and an instruction, wire in whatever you have, "
        + "and it hands back text.\n\n"
        + "The instruction is called the formula. You write it once in the settings "
        + "and it stays on the node, so the node becomes a step that always does the "
        + "same job: describe a photo, rewrite a prompt in another style, turn a rough "
        + "note into a finished one.\n\n"
        + "Everything runs on your own machine using a model in your ComfyUI "
        + "models/text_encoders folder. No account, no key, nothing sent anywhere.\n\n"
        + "It is the general-purpose sister of Video Prompt Pixaroma. That one knows "
        + "about MiniMax H3 and gives you durations and a frame count. This one knows "
        + "about nothing in particular, which is what lets you point it at any job.",
    },
    {
      heading: "The one rule worth learning",
      body:
        "Everything the model is asked is one piece of text: the formula, then your "
        + "idea, then anything wired into the text input.\n\n"
        + "A node with no model chosen does not fail. It passes its text straight "
        + "through, unchanged, and the banner says so. That is deliberate: you can "
        + "drop one into a graph that is already working and set it up afterwards "
        + "without breaking anything downstream.\n\n"
        + "A node with no formula still runs. The model just gets your idea by "
        + "itself, which is exactly what you want for a quick \"make this more "
        + "cinematic\".",
      table: {
        headers: ["Model", "Formula", "Idea or wired text", "What happens"],
        rows: [
          ["none", "anything", "anything", "Passes the text through unchanged"],
          ["chosen", "empty", "empty", "Passes it through: there is nothing to ask"],
          ["chosen", "empty", "present", "Runs, with your idea alone"],
          ["chosen", "written", "empty", "Runs on the formula alone, useful with a picture"],
          ["chosen", "written", "present", "Runs. The normal case"],
        ],
      },
    },
    {
      heading: "The buttons on the node",
      defs: [
        ["The gear", "Opens the settings: the model, the formula, and how wired text is joined. It sits in the empty space beside the input dots so it costs the node no height."],
        ["The seed, and F or R", "F is Fixed: the same seed every Run, so an unchanged node is cached and Run is instant. R is Random: a new seed each Run, so it writes something different every time. Click the number to type one."],
        ["Tags", "Opens your tag library, the same one Prompt Pixaroma uses. Anything you save there can be used in either node."],
        ["Idea first, Wired first", "Only appears when something is wired into the text input. It decides which of the two comes first. The starting choice is in the settings."],
        ["Expand", "Opens your idea in a full-screen box, for when it is long."],
        ["The bar between the two boxes", "Drag it to give more room to whichever box you are using. Double-click resets it."],
        ["Re-roll", "Rolls a new seed and runs again, so you get a different answer without changing anything you wrote."],
        ["Copy", "Copies the text it wrote."],
        ["Free VRAM", "Unloads the model as soon as the text is written, so a video model later in the workflow gets the memory back. Read the memory section below before turning it on in a chain."],
        ["Generate", "Runs the workflow."],
      ],
    },
    {
      heading: "Tags in your idea",
      body:
        "Your idea box understands the same @tags as Prompt Pixaroma, out of the "
        + "same library, so a phrase you saved once can be used in both nodes. Press "
        + "Tags to open it.\n\n"
        + "They are swapped for their real words before the model is asked anything, "
        + "so the model reads finished English and never sees an @ sign.",
      defs: [
        ["@name", "Your saved snippet, exactly as you wrote it."],
        ["*Category", "One random tag out of that category, rolled fresh on every Run."],
        ["#name", "One random line out of that tag, rolled fresh on every Run."],
      ],
    },
    {
      heading: "Reading the colours as you type",
      body:
        "The colour tells you what a word will become, so you can see at a glance "
        + "whether a tag is real before you Run anything.",
      defs: [
        ["Orange", "An @tag that exists."],
        ["Green", "A *category that exists and has something in it."],
        ["Violet", "A #list that exists and has lines in it."],
        ["A red wavy underline", "That name is not in your library, so it will be sent to the model as the literal text you typed. Every name looks like this while you are still typing it, and it takes its real colour the moment it matches."],
      ],
    },
    {
      heading: "Seeing what a slot actually picked",
      body:
        "There is no preview box on this node, on purpose: the face is already two "
        + "text boxes deep and a third one left nothing readable.\n\n"
        + "You rarely need one. The colours above tell you a tag is real before you "
        + "Run, and the prompt the model writes is right there underneath, built "
        + "from whatever the slot picked. If you want to see the swapped words "
        + "themselves, put a Prompt Pixaroma node in front of this one: it has the "
        + "expanded view, and its output wires straight into the text input here.",
    },
    {
      heading: "Chaining several of them",
      body:
        "The output is plain text and the text input takes plain text, so these "
        + "stack with no glue in between. Each one does a different job because each "
        + "one carries its own formula.\n\n"
        + "A worked example: a Load Image goes into one node whose formula is "
        + "\"describe this photo as a short video prompt\". Its text goes into a "
        + "second node whose formula is \"rewrite this in the style of a 90s anime "
        + "cel\". Meanwhile a Load Audio goes into a third whose formula is \"name "
        + "the mood of this music in five words\", and that text also joins the "
        + "second node. Four wires, no other nodes.\n\n"
        + "That third one needs a model that can HEAR, and in ComfyUI that means "
        + "Gemma 4 (`gemma4_e4b_it_fp8_scaled.safetensors`). No Qwen3-VL can hear, "
        + "however good it is with pictures: it takes the audio, ignores it and "
        + "writes something confident anyway. The Sound preset is set up for this.\n\n"
        + "Rename each node to what its formula does and the graph reads as a "
        + "sentence. Double-click the title to rename it.",
    },
    {
      heading: "More than one picture",
      body:
        "Wire a picture into image and an image_2 slot appears below the others; "
        + "wire that and image_3 appears, up to 8 pictures. The model sees each one "
        + "separately and at its own size, so a wide picture and a tall one both "
        + "arrive whole. Unplug the last one and its empty slot goes away again.\n\n"
        + "A batch in the image input also works, but a batch makes every picture "
        + "the size of the first one, cutting the edges off the others. The extra "
        + "slots avoid that.\n\n"
        + "Qwen3-VL and Qwen3.5 get the pictures one by one. Gemma 4 takes them as "
        + "one batch, the first picture's size. On a node from before this update "
        + "that already has a picture wired, unplug and re-plug that wire once and "
        + "the image_2 slot appears.",
    },
    {
      heading: "What happens when you duplicate one",
      body:
        "A duplicate carries everything: the model, all the sampling settings, the "
        + "seed and its mode, and the formula. They all live on the node, so a copy "
        + "is a complete independent one.\n\n"
        + "That matters most for the formula. Editing it on the copy afterwards does "
        + "NOT change the original, which is what makes a chain of three possible. "
        + "It also means a workflow you share carries its instructions with it, so "
        + "whoever opens it sees the same wording you used.\n\n"
        + "This is the one real difference from Video Prompt Pixaroma, whose "
        + "formulas are shared files: change one there and every copy changes.",
    },
    {
      heading: "Two nodes, one model: does it load twice?",
      body:
        "No. The model is shared by every AI Prompt node in the workflow.\n\n"
        + "Two nodes naming the same file means one load and one copy in memory. "
        + "The second node finds it already there and starts writing straight away.\n\n"
        + "Two nodes naming DIFFERENT models take turns. Only one is kept, so the "
        + "second unloads the first and puts itself there instead, and they swap back "
        + "and forth on each run. That is deliberate: holding two ten-gigabyte models "
        + "at once is worse than loading one twice, especially on a 12 GB card. If "
        + "you are mixing models in a chain, expect the first run to be slow.\n\n"
        + "The best trick for a chain is Fixed seeds. With the seed on F and nothing "
        + "changed, ComfyUI serves the whole node from its cache on the second Run, "
        + "so nothing loads at all and the run goes straight to your image or video.",
    },
    {
      heading: "Free VRAM in a chain: the one trap",
      body:
        "Free VRAM unloads the model the moment THAT node finishes. So if an early "
        + "node in a chain has it on and a later node wants the same model, the "
        + "later one has to load it all over again in the same run.\n\n"
        + "The rule is simple: turn Free VRAM on only for the LAST node that uses "
        + "that model, usually the one feeding your image or video. Leave it off on "
        + "the ones before it.\n\n"
        + "It is skipped entirely when a model comes in on the clip wire, because "
        + "that model belongs to the node feeding it and may be shared with the rest "
        + "of your workflow. The button dims to show it is doing nothing.",
    },
    {
      heading: "Presets: a formula and the settings that make it work",
      body:
        "A formula on its own is only half a recipe. The Krea 2 idea formula "
        + "that ships with this node writes beautifully at temperature 0.3 and "
        + "rambles, invents objects and sometimes refuses at 0.7, using the very "
        + "same words on the very same model. So a preset carries the wording "
        + "AND the settings it was measured at.\n\n"
        + "It also remembers which model it was written for. If you have that "
        + "model it is chosen for you; if you do not, the line under the picker "
        + "says so in amber and your own model is left alone, so a preset from "
        + "somebody else's machine can never point this node at something that "
        + "is not there.\n\n"
        + "Everything below is in the settings, under Presets.",
      defs: [
        ["Pick one from the list", "Fills in the formula, the temperature and the sampling values in one go. Turn off \"Bring its settings too\" first if you want the wording only."],
        ["The orange and grey dots", "An orange dot means the preset ships with Pixaroma. A grey one means you saved it yourself. The picker row at the top wears the same dot, so it says which kind is loaded without being opened."],
        ["Type to filter", "The box at the top of the list narrows it as you type. Every word you type has to appear in the name but the order does not matter, so \"krea image\" finds the image one. When one name is left, Enter loads it."],
        ["All, Pixaroma, Mine", "The three buttons under the filter show everything, only the ones that ship with Pixaroma, or only your own, with a count on each. Mine stays greyed out until you have saved one."],
        ["Hover a name", "Shows which model it was written for, whether you have that model, and its temperature. All before you load it."],
        ["Save current", "Keeps whatever this node has right now under a name you choose, so your own recipes sit in the same list. After changing one of your own presets, its name is already filled in: press Enter to update it, or type a new name to keep both."],
        ["Deleting one", "Hover a name in the list and a ✕ appears at the end of the row. It works on your own presets and asks first, because they are files on disk. On the ones that ship with Pixaroma it is greyed out: those come back with every update, so they cannot be deleted."],
        ["Reset", "On the Advanced sampling line. Puts the sampling values back to the defaults and leaves your formula and model alone. It covers everything a preset can carry, so the Behaviour switches at the bottom go back too, except Faster writing (MTP), which is about your graphics card and is never reset. It wakes up only when something has really changed, and its tooltip names what."],
      ],
    },
    {
      heading: "Sending a recipe to somebody else",
      body:
        "Export and Import sit beside the formula in the settings, and they "
        + "carry the whole recipe: the wording, the sampling settings, and the "
        + "model it was written for. Sending only the words would send something "
        + "that looks broken, because the temperature is half of why it works.\n\n"
        + "Each one offers a file or the clipboard. Pick whichever suits.",
      defs: [
        ["Export, then Save as a file", "Writes a .txt you can keep, back up, or send to somebody."],
        ["Export, then Copy to clipboard", "Puts the same thing on the clipboard, ready to paste straight into a Discord message."],
        ["Import, then Open a file", "Loads a .txt somebody sent you."],
        ["Import, then Paste from clipboard", "Loads one you have just copied out of a message."],
      ],
    },
    {
      heading: "Where your presets are kept",
      body:
        "The list holds two kinds, and a dot on each name says which: orange for "
        + "the ones that ship with Pixaroma, grey for your own. The buttons under "
        + "the filter can show just one kind or the other.\n\n"
        + "The ones that ship with Pixaroma are on every machine that installs "
        + "it, so a formula like Krea 2 is already there for everybody and you "
        + "never need to send it to anyone. New ones arrive with a Pixaroma "
        + "update.\n\n"
        + "Your own are kept together in one file:\n"
        + "`ComfyUI/user/pixaroma/ai_prompt_presets.json`\n"
        + "That sits outside the plugin folder, so updating or reinstalling "
        + "Pixaroma cannot wipe them, and it is the one file to copy when you "
        + "move to another machine.\n\n"
        + "A recipe you import that arrives with a name is added to that list by "
        + "itself, so it is there next time too. The file it came from is "
        + "ordinary readable text: you can open it in Notepad and change the "
        + "temperature by hand. And a plain .txt with no header still loads as "
        + "the formula on its own, exactly as it always did, so older exports "
        + "and any prompt you already had lying around still work.",
      defs: [
        ["The name in brackets", "Every preset ends with the model it was written and measured on, so you can see that before you load it. They are not fussy: a formula tuned on one Qwen3-VL build behaves the same on the others. Only the Gemma 4 one genuinely needs its model, because nothing else here can hear."],
        ["Video - prompt from a video (Gemma 4 E4B)", "Watches a clip and writes the video prompt that would make one like it: the medium, what HAPPENS from beginning to end, and what the camera does. Wire Load Video Pixaroma into the video input. Frames are read as 24fps and sampled one per second, so load a few seconds rather than a whole clip."],
        ["Transcribe - the words only (Gemma 4 E4B)", "Writes out what is said and nothing else: no summary, no description of the sounds, no speaker labels or timestamps, and an unclear word comes back as [inaudible]. Use this one when you want the words themselves; use Sound when you want the mood."],
        ["Sound - describe what you hear (Gemma 4 E4B)", "Wire a Load Audio in and it says what kind of sound it is, quotes any words spoken or sung, names the instruments and gives the mood. Gemma 4 is the ONLY text encoder ComfyUI can feed audio to, so a Qwen3-VL will take the audio, ignore it and answer anyway. Send its text into a second AI Prompt node to turn it into an image prompt."],
        ["FLUX 3 - prompt from an idea", "BFL's own prompt upsampler for FLUX 3 Image Klein, with their system prompt, their settings and Send the formula as a system message on, so it asks exactly what their Text Generate template asks. It turns a short idea into the long caption FLUX 3 was trained on. Best on short real-world ideas: a fantasy label like \"magical forest\" makes it pile on glowing extras. Top_k is 40, because the template's 1 writes the same caption whatever the seed. Use it before a Flux3 Layout Prompt node, never after, because it removes the box tags."],
        ["Krea 2 - prompt from an idea", "Turns a rough idea into a full Krea 2 prompt. Built from Krea's own published prompt-expansion instructions, then tightened by watching where it went wrong. Measured on Qwen3-VL 4B and 8B."],
        ["Krea 2 - prompt from an image", "Wire a Load Image into the image input and it writes the prompt that would make a similar picture, naming the medium, the framing and the light. Leave Your idea empty for this one. Needs a vision model. Photographs come back cleanest."],
        ["Ming Image - prompt from an idea", "Turns a short idea into the structured JSON layout Ming Image 0.1 Design reads best, built on Ming's own published rewriter: every part of the design with its position and colours, and every word you put in quotes kept exactly. Wire a line like Canvas: 832 x 1248 px into the text input (a core Format Text node fed by your width and height) so the layout fits the shape of your picture. Two versions: Qwen3.8 27B, the writer Ming's makers name, and the smaller Qwen3.5 9B. Ming's own text encoder cannot write, so it needs one of these."],
        ["MOSS-Image - prompt from an idea", "Turns a short idea into the detailed caption MOSS-Image likes, with the prompt enhancer from ComfyUI's own MOSS-Image workflow (a short form of OpenMOSS's own), sent as a system message with that workflow's settings. It keeps everything you asked for, fills the gaps with concrete visual choices, and quotes every word that should appear in the picture. MOSS's text encoder can write, so wire the workflow's Load CLIP into the clip input and the model already loaded does it."],
        ["MOSS-Image - prompt from an image", "Wire a Load Image into the image input and it writes the MOSS-Image caption that would make the picture again: the medium first, every person's hair, age and clothes, and any text in quotes. Leave Your idea empty, or type a change there (like: at night) to get the caption with that change. MOSS's text encoder can see, so wire the workflow's Load CLIP into the clip input."],
        ["Qwen Image 2.1 - prompt from an idea", "Turns a short idea into the long, detailed prompt Qwen Image 2.1 likes, built from Qwen's own published prompt enhancer: the style and the medium first, then everything placed in the frame. Put any words you want written in the picture in quotes in your idea, and it keeps them exactly. Qwen Image 2.1's text encoder is Qwen3-VL 8B, so wire the workflow's Load CLIP into the clip input and one model does both jobs."],
        ["Qwen Image 2.1 - transparent picture from an idea", "For a subject on a transparent background. It wraps your idea in the exact words Qwen Image 2.1 needs to make a real transparency channel and describes only the subject. In testing a plain idea gave a solid background every time, and this preset made most of the picture transparent. Save the result as a PNG."],
        ["Qwen Image 2.1 - prompt from an image", "Wire a Load Image into the image input and it writes the Qwen Image 2.1 prompt that would make a picture like it, naming the style as well as the medium, so a cartoon stays a cartoon. Leave Your idea empty for this one."],
        ["Qwen Image 2.1 - edit from an instruction", "For Qwen Image 2.1's image edit. Wire your picture into the image input and a second one into image_2 (it appears once the first is wired), type the change in Your idea, and it writes a clear edit instruction that leads with the change and keeps everything else. Qwen Image 2.1 already follows short edits well, so this helps most with vague requests, style changes and two-picture edits."],
        ["Z-Image - prompt from an idea", "The same job as the Krea one, written for Z-Image Turbo, which wants a much longer and more detailed prompt. Built from the makers' own guidance, so its Max len is set high to leave room for one. Leave Thinking off, which is the default: Z-Image's encoder is a reasoning model, and thinking costs about three times the wait for no better prompt."],
      ],
    },
    {
      heading: "Sharing a workflow's model instead of loading a second one",
      body:
        "Some image models use a language model as their text encoder. Krea 2 "
        + "and Qwen Image 2.1 both use Qwen3-VL, which is exactly the kind of "
        + "model this node wants. "
        + "When that is true you can wire the workflow's own CLIP loader "
        + "straight into this node's clip input and write your prompts with the "
        + "model that is already in memory. Nothing extra loads, and a whole "
        + "text-to-image run takes seconds.\n\n"
        + "Not every text encoder can write, though. Ming Image's only reads: "
        + "wired in here it stops with \"not a language model\". For a model like "
        + "that, pick a writer of its own in the gear instead.\n\n"
        + "The banner changes to Model on wire and Free VRAM dims, because a "
        + "model that arrived on a wire belongs to the node feeding it.\n\n"
        + "One thing to watch: a small model needs a lower temperature than a "
        + "big one. A 4B at 0.7 will echo your formula back at you or invent "
        + "things you never asked for. At 0.3 it behaves. If a formula seems to "
        + "be ignored, lower the temperature before you blame the wording.",
    },
    {
      heading: "Send the formula as a system message",
      body:
        "A chat model reads two kinds of text: a system message that sets its job, "
        + "and the user's turn that asks. By default this node puts the formula inside "
        + "the prompt, above your idea, and the presets were written for that.\n\n"
        + "Some models were trained with their instructions in the system message, "
        + "like BFL's FLUX 3 prompt upsampler. For those, open the settings and turn on "
        + "Send the formula as a system message, under Behaviour. The formula then "
        + "goes to the model as its system message, and only your idea, plus any wired "
        + "text, is the prompt. That is exactly how ComfyUI's own Text Generate node "
        + "sends its system prompt: tested with the FLUX 3 upsampler, the same seed "
        + "gave the same caption word for word and the same picture.\n\n"
        + "It needs ComfyUI 0.38 or newer, a model that has a system message (Qwen3.5, "
        + "Qwen3-VL, Z-Image's Qwen3 and Gemma 4 do), and Use the model's own template "
        + "on. When one of those is missing, the formula goes inside the prompt as "
        + "before and the line under the answer says so in amber. Nothing is dropped "
        + "without telling you.",
    },
    {
      heading: "Writing a good formula",
      bullets: [
        "Say what you want back, not what you want it to think about. \"Write one paragraph describing this photo as a video prompt\" beats \"analyse this photo\".",
        "Say how long. Models write far more than you expect unless you tell them a length.",
        "Say what NOT to include. \"Do not write a title, a preamble, or any explanation, only the prompt itself\" saves a lot of tidying up.",
        "Give it one example of a good answer if the shape matters. A small model copies the example far more reliably than it follows the rules.",
        "Leave the changeable part out of the formula and type it into Your idea instead. That way one node handles every picture you throw at it.",
      ],
    },
    // NO "what you can wire in" section here on purpose. The Help browser
    // GENERATES that reference from this node's own Python tooltips
    // (help-browser.md #7), so writing one as well prints the same thing
    // twice and the two copies drift apart the first time an input changes.
    {
      heading: "What you need installed",
      body:
        "One language model in ComfyUI/models/text_encoders. For anything that has "
        + "to look at a picture it must be a vision model.\n\n"
        + "A good all-round choice is "
        + "`qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors`, about 10 GB, for cards "
        + "with 12 GB or more. Take it from the comfyui folder of that repository, "
        + "not the root: the root holds the raw model, which ComfyUI cannot load as a "
        + "text encoder. For an 8 GB card use the 4B build instead.\n\n"
        + "The shipped formulas were written and measured on Qwen3-VL 4B builds, "
        + "which is why each preset names one. They are not fussy: the same wording "
        + "was checked on the 8B and on both 4B builds and behaves the same. So when "
        + "a preset says the model it was written for is one you do not have, that "
        + "line is telling you what it was tuned on, not that anything is wrong.\n\n"
        + "The picker marks any file that does not look like a vision model. It does "
        + "not block them, because a text-only model is the right choice for a step "
        + "that only rewrites text, and it is a lot smaller and quicker.",
    },
    {
      heading: "If something looks wrong",
      defs: [
        ["It hands back my own words unchanged", "No model is chosen, or there is nothing to send. The banner says which."],
        ["It describes a picture it cannot have seen", "The model is text-only. It accepts the picture and ignores it, silently. Pick one the list does NOT mark with \"(no vision)\". That mark is a guess from the filename, since ComfyUI only knows a model's abilities from inside the file, so treat it as a hint rather than a verdict."],
        ["It answers about audio or video but describes the wrong thing", "The model cannot hear or watch. Only Gemma 4 can, and the list marks it \"(sees + hears)\". Every other model takes the audio or the frames, ignores them and answers anyway. A Qwen3-VL can see a still picture, which is a different thing from watching a clip."],
        ["ComfyUI stops responding while reading a video", "Load fewer frames. Set Max frames on Load Video to a few seconds' worth, since the frames are sampled one per second anyway and more of them buy nothing. Loading the same clip repeatedly in quick succession has been seen to lock the server, which needs a restart."],
        ["Run does nothing and the text never changes", "The seed is Fixed and nothing else changed, so ComfyUI is serving the cached answer. That is the point of Fixed. Press Re-roll, or switch the seed to R."],
        ["It writes far too much", "Say a length in the formula, and lower Max len in the settings so it cannot run on."],
        ["It repeats my formula back at me, or ignores it", "The temperature is too high for the model. Try 0.3. Small models especially need it, and this single setting is the difference between a formula working and looking broken."],
        ["It hands back nothing at all", "Usually the formula is too short for that model to get going. A one-line instruction can produce an empty answer where a proper formula produces a good paragraph. Load a preset and try again before you blame the model."],
        ["It refuses, or says it cannot see my idea", "Same cause: lower the temperature to 0.3."],
        ["Every run reloads the model", "Two nodes in the workflow are using different models. Give them the same one if you can."],
        ["It got the words in the picture wrong", "The model reads one large piece of text reliably, and guesses at several smaller ones: a menu reading PLAY, SETTINGS, EXIT came back as PAY, SHEETS, EAT. It never says it is unsure, so a wrong word looks like a right one. A bigger model does not help, and nor does asking it to read carefully; both were tried. If the words matter, read them in the prompt before you Run, and to correct them press Copy, paste into a Text Pixaroma node, fix the words there and wire that into your text encoder."],
        ["I typed in Your idea with the image preset and it changed nothing", "That preset's strongest rule is to describe only what is really in the picture, so it overrules you, which is what stops it inventing things. A change of medium does land, so \"as a watercolour painting\" works. To change what is IN the picture, leave the idea empty and send this node's text into a second AI Prompt node whose formula is the change you want."],
        ["A workflow somebody sent me says the model is not in my text_encoders folder", "A workflow carries the model's NAME, not the model itself. Either download that file, or open the settings and pick one you already have. Everything else, the formula and all the settings, came with the workflow and is already there."],
        ["The line under the answer says the formula went in the prompt", "Send the formula as a system message is on, but this run could not use one: the model has no system message, Use the model's own template is off, or there was nothing to send besides the formula. The run still worked, with the formula inside the prompt as usual. The amber line says which."],
        ["A run stops with a CUDA error such as \"illegal memory access\"", "Open the settings and turn off Faster writing (MTP), under Behaviour. Some models (several Qwen3.5 files) carry an extra MTP part that writes a few words ahead, and on some cards and model files that crashes. Off writes a little slower and gives the same kind of answer. It is the same as setting mtp to off on ComfyUI's Generate Text node, and presets never turn it back on."],
        ["The settings panel will not close", "Click the gear again, press Escape, or click the canvas."],
      ],
    },
  ],
};
