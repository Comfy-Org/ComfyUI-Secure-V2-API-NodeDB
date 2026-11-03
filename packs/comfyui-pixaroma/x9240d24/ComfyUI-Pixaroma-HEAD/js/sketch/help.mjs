// Sketch Pixaroma - the written help (the toolbar ? and the Help browser).
// Plain words for artists, no em dashes (house rule).

export const SKETCH_HELP = {
  title: "Sketch Pixaroma",
  tagline: "Mark what to change on a picture (a box, a circle, a loop, an arrow or a word) and write the change beside it. Made for edit models like Flux 2 Klein, Qwen Image Edit and Kontext.",
  sections: [
    {
      heading: "How to use it",
      bullets: [
        "Wire a picture into `image`. From a Load Image it shows on the node right away, also through a Switch. After a run the node shows exactly the picture that came in.",
        "Pick a tool and drag on the picture. The Box is the default and starts in red.",
        "Every mark gets a number, and the cursor jumps to its note: type what to change there, like `make the hat a red baseball cap`, and press Enter.",
        "Wire `image` into your edit model as the picture it edits, and `prompt` into the text encode. Run.",
      ],
    },
    {
      heading: "The tools",
      defs: [
        ["Box", "Drag a rectangle around what to change."],
        ["Circle", "Drag an oval around it."],
        ["Freehand", "Draw a loop around something, or sketch the rough shape of something to add. A loop you close counts as an area; an open stroke counts as a sketch."],
        ["Arrow", "Drag from anywhere to the thing you point at."],
        ["Text", "Click on the picture and type a word right onto it."],
      ],
    },
    {
      heading: "The prompt it writes",
      body: "One sentence for each mark that has a note: `Inside the red box: make the hat a red baseball cap.` Each new mark takes the next color (red, blue, green, purple), so every mark has its own name. Two marks of the same color and shape are told apart by where they are: the left red box and the right red box.\n\nThe switch beside the prompt adds a last sentence asking the model to remove the marks, because edit models often keep them otherwise. Leave every note empty if you would rather write the whole prompt yourself.",
    },
    {
      heading: "What comes out",
      defs: [
        ["image", "The picture with your marks drawn in, at its full size. Every pixel you did not mark is exactly the input."],
        ["prompt", "Your notes as one instruction. Empty when no mark has a note."],
        ["mask", "White inside every box, circle and closed loop, and along an open sketch. For inpaint workflows, when a model does not read drawn marks."],
      ],
    },
    {
      heading: "The buttons on the node",
      defs: [
        ["Undo and Redo", "Step back and forward through your marks. Ctrl+Z on the canvas also undoes a mark, like any change."],
        ["Clear", "Removes every mark. Undo brings them back."],
        ["Expand", "Opens a big view of the picture for careful marking. It edits the same marks, so there is nothing to save: Done, Esc or a click outside closes it."],
        ["Gear", "Settings: the button color, and whether each new mark takes the next color."],
        ["× on a row", "Deletes that one mark. Hover a row to see which mark it is."],
      ],
    },
    {
      heading: "Tips",
      bullets: [
        "Keep notes short and concrete: say what it should become, not what it is now.",
        "Mark only the part you mean. A loose loop around a small pouch can take the whole backpack with it.",
        "A word can stand for a thing: write `crown` where it should go and note `replace the word with a small golden crown`.",
        "On a big photo or a small detail, pick a thicker line (L or XL) so the model cannot miss the mark.",
        "Sketching something to add? Draw its rough outline with Freehand in XL and write what it is, like `turn this into a real hat`.",
        "If a model ignores drawn marks, wire `mask` into an inpaint workflow (Inpaint Crop) instead.",
        "Something between the Load Image and Sketch crops or turns the picture? Run once before marking, so you mark the picture that really arrives. The node warns you when the picture changed shape under your marks.",
      ],
    },
  ],
};
