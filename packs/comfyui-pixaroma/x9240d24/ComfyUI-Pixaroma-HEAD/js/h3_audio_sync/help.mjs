// H3 Audio Sync Pixaroma - the help page.

export const H3_SYNC_HELP = {
  title: "H3 Audio Sync Pixaroma",
  tagline: "Make a MiniMax H3 video sing your track instead of one it made up.",
  sections: [
    {
      heading: "Why this is needed",
      body:
        "MiniMax H3 is unusual: it creates the picture and the sound at the same time, as one "
        + "joined thing. Left to itself it invents its own audio, so a character appears to sing "
        + "but the mouth is following a song that does not exist anywhere.\n\n"
        + "That is why you cannot simply mute what it made and lay your own song on top "
        + "afterwards. The mouth was never moving to your song in the first place.\n\n"
        + "This node puts your real recording into the sound half and holds it still, so the only "
        + "thing left for the model to decide is the picture. The only picture that fits a fixed "
        + "soundtrack is one whose mouth matches it.",
    },
    {
      heading: "Where it goes",
      body:
        "Between your H3 latent and your sampler. Wire the model through it as well, so it sits "
        + "in the chain rather than being wired around.\n\n"
        + "It works out how long the clip is on its own, straight from the latent, so you never "
        + "type a duration and the sound can never come out a different length from the picture.",
    },
    {
      heading: "Getting your track ready",
      body:
        "Load Audio Pixaroma is the easy way: it draws the file, you drag a window over the part "
        + "you want, and it hands the piece straight to this node. Wire Duration Pixaroma into it "
        + "as well and the window is automatically the same length as the clip.\n\n"
        + "Any other source of audio works too. If what arrives is longer than the clip this node "
        + "takes it from the beginning, and if it is shorter the node fills the rest with silence "
        + "or loops it, whichever you chose in the settings.",
    },
    {
      heading: "The fifteen second wall",
      body:
        "MiniMax H3 was only trained on clips up to about fifteen seconds, and past that it "
        + "usually falls apart. This node checks before the render rather than after: by default "
        + "it prints a warning, and you can set it to stop the run instead so nothing is wasted.\n\n"
        + "For a longer video, 30 seconds or a minute, put H3 Long Video Pixaroma on the model wire BEFORE "
        + "this node. It makes the clip in overlapping windows of about 10 seconds, so the wall no longer "
        + "applies, and this node then skips the warning (and never stops the run for it).\n\n"
        + "Note that H3 cannot make round durations at all. Its frame count has to land on a fixed "
        + "pattern, so the lengths you can actually have are 5.17s, 5.88s, 6.58s and so on up to "
        + "15.08s. Only 8.00s is a whole number. Duration Pixaroma works this out for you.",
    },
    {
      heading: "What you wire in",
      defs: [
        ["model", "Your H3 model. It passes through untouched."],
        ["latent", "The joined picture-and-sound latent from an H3 node."],
        ["audio_vae", "H3's audio VAE, the same one the H3 conditioning node uses."],
        ["track", "The real recording you want performed."],
      ],
    },
    {
      heading: "What comes out",
      defs: [
        ["model", "Your model, unchanged."],
        ["latent", "The latent with your track locked into its sound half. Into the sampler."],
        ["audio", "Your track cut to exactly the clip length, for the save node, so the finished "
          + "file has picture and sound the same length."],
      ],
    },
  ],
  footer: "This node only works with MiniMax H3. Other models do not have a joined "
    + "picture-and-sound latent for it to reach into.",
};
