class PixaromaInfo:
    """Info Pixaroma - a button on the canvas that opens a note to read.

    Pure frontend node (js/info/): the face is a title-less button, a click
    opens the note in a reading window, and Edit opens the same rich-text
    editor as Note Pixaroma. Never runs: no outputs, not an output node.
    """

    DESCRIPTION = (
        "Info Pixaroma - a small button on the canvas that opens a note in a "
        "reading window. Use it for the information a workflow carries: what it "
        "does and how to use it, the models to download, what each node does, "
        "the best settings, prompt tips, run times and links.\n\n"
        "Click the button to read the note. Edit it from the reading window or "
        "by right-clicking the button: the editor is the same one Note Pixaroma "
        "uses, with a strip on top for the button's title, icon and colour. When "
        "you add the node you can pick a starter (Read me, Models, Nodes, "
        "Settings, Prompt tips, Run times, Tips, Attention, Links or Blank) that "
        "fills in the title, icon, colour and the empty headings.\n\n"
        "Drag the corner to make the button bigger or smaller. Pure annotation: "
        "nothing to wire, nothing to process, and it never runs."
    )

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "note_json": (
                    "STRING",
                    {
                        # Same shape as Note Pixaroma's note_json (its editor is
                        # reused), plus an "info" block for the button itself.
                        # Keep in sync with DEFAULT_CFG in js/info/core.mjs.
                        "default": '{"version":1,"content":"","buttonColor":"#f66744","lineColor":"#f66744","info":{"title":"Info","icon":"info","color":"#f66744"}}',
                        "multiline": True,
                        # No input SOCKET: on a title-less button the socket sat
                        # under the top-left corner, where a press dragged a wire
                        # out of it (reproduced). The frontend creates no socket
                        # for a socketless widget; the value saves as before.
                        "socketless": True,
                        # Our own widget constructor (js/info/index.js
                        # getCustomWidgets): the frontend's STRING constructor
                        # does not carry "socketless" into the widget, ours does.
                        # A frontend without widgetType support falls back to the
                        # plain STRING widget, and the JS hides its socket.
                        "widgetType": "PIXAROMA_INFO_STATE",
                        # No tooltip on purpose: Classic shows a widget's tooltip
                        # while the mouse is over it, and this hidden widget sits
                        # under the whole button.
                    },
                ),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "noop"
    # OUTPUT_NODE intentionally not set: ComfyUI skips the node on Run, so it
    # does no work and draws no timing badge (same as Note and Label).
    CATEGORY = "👑 Pixaroma/📝 Notes & Overlay"

    def noop(self, note_json):
        return {}


NODE_CLASS_MAPPINGS = {
    "PixaromaInfo": PixaromaInfo,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PixaromaInfo": "Info Pixaroma",
}
