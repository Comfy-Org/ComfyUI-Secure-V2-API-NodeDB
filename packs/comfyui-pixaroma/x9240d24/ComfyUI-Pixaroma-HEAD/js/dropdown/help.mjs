// Dropdown Pixaroma - the help page.
//
// Kept beside the node rather than in the central help_defs.mjs map, the way
// Compare / Text / XY Plot / Find and Replace do, because it is written against
// this node's own behaviour and should move with it.
//
// Written for someone making pictures, not for someone reading the code: what it
// does, how to use it, and what actually comes out. No em dashes (house rule).

export const DROPDOWN_HELP = {
  title: "Dropdown Pixaroma",
  tagline: "A dropdown you fill in yourself: pick a short name, send a long value.",
  sections: [
    {
      heading: "What it is for",
      body:
        "Some values are long and you retype them constantly. A LoRA might want a whole "
        + "sentence as its trigger. A look you like might be a paragraph of prompt.\n\n"
        + "Put them in this node once, give each one a short name, and after that you just "
        + "pick the name. The node sends the long value on your behalf.",
    },
    {
      heading: "Setting it up",
      bullets: [
        "Press the gear on the node, or right click it, to open the settings.",
        "An empty list offers `Add your first entry`. Fill in a short name and the value it stands for.",
        "The value box grows as you type, so a long sentence or several lines are fine.",
        "The `+` on a row adds another one below it, the `✕` removes that row, and the `⋮⋮` grip drags it up or down.",
        "`Clear list` at the bottom empties the whole list in one go, after asking. Export first if you might want it back.",
        "Close the settings. Your list is saved inside the workflow.",
      ],
    },
    {
      heading: "Choosing on the canvas",
      body:
        "The node itself is one row, plus one read-only row per output when you use more than one. Click it to open your list, or use the `◀` and `▶` "
        + "arrows to step through without opening anything.\n\n"
        + "The list shows just your names, sized so they fit, and its text follows your zoom "
        + "so it stays in step with the node. Hold the mouse over an entry to peek at its "
        + "value, or open the settings to see everything.",
    },
    {
      heading: "What comes out",
      body:
        "Pick one of four in the settings, and the node's output says which one is active:",
      table: {
        headers: ["Setting", "Sends", "Good for"],
        rows: [
          ["Text", "`text`", "Trigger words, prompt fragments, file names"],
          ["Whole number", "`int`", "Sizes, steps, frame counts"],
          ["Decimal", "`float`", "Strengths, cfg, denoise"],
          ["On / off", "`on/off`", "Any true or false setting"],
        ],
      },
    },
    {
      heading: "One pick, several values",
      body:
        "An entry can carry up to four values at once. In the settings, set how many outputs you "
        + "want, give each one a name, and every entry then holds one value per output. Picking "
        + "an entry sets all of them together, and the node shows what it resolved to before you "
        + "run anything.\n\n"
        + "This is what makes settings that belong together stay together. A sampler and its "
        + "scheduler are the clearest case: some pairings work and some ruin the picture, so "
        + "holding them as one named choice means you cannot accidentally mix a good sampler "
        + "with the wrong scheduler.",
      table: {
        headers: ["Entry name", "sampler", "scheduler"],
        rows: [
          ["Safe", "`euler`", "`simple`"],
          ["Alternative look", "`euler`", "`beta`"],
          ["Avoid", "`res_multistep`", "`ddim_uniform`"],
        ],
      },
      bullets: [
        "Each output has its own type, so you can mix text with numbers and on/off.",
        "Leave it on one output and the node behaves exactly as it always has.",
        "Turning the count down keeps the values you typed, in case you turn it back up.",
      ],
    },
    {
      heading: "Changing entry on its own each run",
      body:
        "The small letter on the node says which entry it will send when you press Run, and you "
        + "can click it to change: `F`, then `I`, then `R`, then back again. The same three "
        + "buttons are in the settings under `EACH TIME YOU RUN`.",
      defs: [
        ["`F`  Fixed", "Always the entry you picked. This is the default, and the node stays completely predictable."],
        ["`I`  In order", "The next entry down the list on each run, going back to the top after the last one. Good for working through a list of looks without touching anything."],
        ["`R`  Random", "Any entry each run, never the same one twice in a row."],
      ],
      bullets: [
        "`F` is drawn quietly since it is the normal way to work. `I` and `R` are filled in, because those change the value on you, and the name on the node then updates to whatever just ran.",
        "On `I`, picking an entry by hand takes over: the next run starts from what you chose and carries on from there. On `R` it only means that entry will not be the next one, since random is random.",
        "Exporting or saving your workflow does not move an in-order list along. Only a real run does.",
        "The position starts again from your chosen entry when you reload the page, which is also why running a workflow never marks it as changed.",
      ],
    },
    {
      heading: "It ignores what it is plugged into",
      body:
        "The list and the type belong to this node. Wiring it somewhere else never changes "
        + "them.\n\n"
        + "That is the difference from Control Panel Pixaroma, whose controls copy the type of "
        + "whatever they are wired to. Use Control Panel when you want a dial for one specific "
        + "input. Use this when you want your own named list that you can plug in anywhere.",
    },
    {
      heading: "Changing the type later",
      body:
        "Nothing is ever deleted. If you switch a list of sentences to Whole number, your "
        + "sentences stay exactly as you typed them, and the rows that are not numbers get a "
        + "small warning mark. Those rows send 0 until you change them, and switching back to "
        + "Text brings everything straight back.\n\n"
        + "Anything plugged into the output that no longer fits is unplugged, and the node "
        + "tells you how many wires that was.",
    },
    {
      heading: "Comparing every entry at once",
      body:
        "XY Plot Pixaroma can drive this node. Pick your Dropdown as an axis and tick the "
        + "entries you want, and you get one square per entry with the names written along "
        + "the edge.\n\n"
        + "That is the quick way to see four LoRA triggers side by side without wiring "
        + "anything four times.",
    },
    {
      heading: "Sharing a list",
      bullets: [
        "The list saves inside the workflow, so sending someone the workflow sends the entries with it.",
        "`Export` writes the list to a file. `Import` loads one back and replaces what is there.",
        "Copying the node copies its list too.",
      ],
    },
  ],
  footer: "Find it under 👑 Pixaroma / 🔢 Values, or search for dropdown, list, options, preset, combination, pair or trigger.",
};
