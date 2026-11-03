// Longest Side Pixaroma - help. Kept beside the node rather than in the central
// help_defs map so the writing and the behaviour move together.

import { registerNodeHelp } from "../shared/help.mjs";

registerNodeHelp("PixaromaLongestSide", {
  title: "Longest Side Pixaroma",
  tagline: "Make a picture's longest side the size you want, and crop it to a shape while you are there.",
  sections: [
    {
      heading: "What it is for",
      body:
        "Most of the time resizing comes down to one sentence: make this picture "
        + "1216 on its longest side. This node is that sentence and nothing else.\n\n"
        + "It never asks you for a width AND a height, which is what keeps it small. "
        + "The size tabs say how big, the shape chips say what shape. If you need "
        + "the fuller set of options (fit inside a box, pad a border, match a ratio "
        + "without cropping), reach for Image Resize Pixaroma instead.",
    },
    {
      heading: "The size tabs",
      body:
        "Click a size and the longer edge of your picture becomes exactly that "
        + "number. The other edge follows along so nothing is squashed or "
        + "stretched.\n\n"
        + "It does not matter whether your picture is tall or wide: the LONGER side "
        + "is the one that gets the number, so you never have to work out whether "
        + "you meant width or height. A wide 1920 by 1080 photo at 1216 becomes "
        + "1216 by 684. A tall one becomes 684 by 1216.\n\n"
        + "The five sizes on the row are yours to change in the settings: type "
        + "any number you like, and each one is rounded to match the step.",
    },
    {
      heading: "The shape chips",
      body:
        "The little rectangle on each chip shows you the shape you will get. "
        + "The one on keep is just a neutral box, because keep leaves your "
        + "picture's own shape alone.",
      defs: [
        ["keep", "Leave the picture's own shape alone and just scale it. This is the usual choice, and it is always on the row so there is always a way back from a crop."],
        ["1:1", "A square."],
        ["16:9", "Wide, like a TV screen."],
        ["9:16", "Tall, like a phone screen."],
        ["2:3", "The classic photo shape, standing up."],
        ["Changing the row", "The settings hold every shape on offer. Click one to put it on the row or take it off. Five fit, and keep is always one of them, so four of the five are yours to choose."],
      ],
    },
    {
      heading: "How the cropping works",
      body:
        "Picking a shape takes the biggest piece of that shape out of your "
        + "picture, so nothing ever stretches and you never get empty bars down "
        + "the sides. Something has to go, though: cropping a wide photo to a tall "
        + "shape throws away the left and right of it.\n\n"
        + "By default the piece is taken from the middle. If the part you care "
        + "about is off to one side, the settings have a nine square grid for "
        + "choosing where to take it from.",
    },
    {
      heading: "The buttons on the node",
      defs: [
        ["The small button", "Steps through Off, 8, 16, 32 and 64. Most models want sizes in steps like these, so this rounds BOTH sides to the nearest step. Each node remembers its own, and the same choice is in the settings."],
        ["The gear", "Opens the settings: the step, the sizes on the row (type any number you like), which shapes appear, where a crop is taken from, whether small pictures may grow, the resample quality, and the node's colour."],
        ["The orange size", "What this node will send. It reads the picture coming in, so it shows the exact numbers straight away, with no need to run anything first. When it cannot see the picture the text goes dim: a squiggle in front of a rough guess if you have picked a shape, or just the long side on its own, because the other side depends on the picture."],
      ],
    },
    {
      heading: "Worth knowing",
      bullets: [
        "Rounding to a step moves the shape by a hair. 9:16 at 1216 is 684 by 1216, and with the step on 32 it becomes 672 by 1216. That is normal and every node that rounds does it.",
        "Turning off 'let small pictures grow' in the settings stops a small picture being blown up past its real size. It still gets cropped to the shape you picked.",
        "The width and height outputs are the finished numbers, already rounded, so you can wire them straight into a sampler.",
      ],
    },
  ],
  footer: "The gear on the node, the gear in the toolbar above a selected node, "
    + "and right-clicking the node all open the same settings.",
});
