class PixaromaMonitor:
    """Monitor Pixaroma - a live readout of what the computer is doing.

    A frontend-only node like Run Timer Pixaroma and Run Log Pixaroma: it never
    runs in Python, so it is skipped on every Run, has no inputs and no outputs,
    and never enters the prompt. All of the behaviour lives in js/monitor/, which
    polls GET /pixaroma/api/monitor/stats and paints the bars.

    Settings (which readouts to show, the layout, the update rate) live on
    node.properties.monitorState and are restored from the workflow on load. The
    live numbers are deliberately NOT persisted: a node that wrote a value into
    the workflow every second would mark it modified constantly and fill the undo
    history with nothing.
    """

    DESCRIPTION = (
        "Monitor Pixaroma - a small dashboard that shows how hard your computer "
        "is working while you generate: video memory, system memory, GPU load, "
        "processor load, temperature and power draw, updated live.\n\n"
        "The most useful number is the peak: the pale mark on the video memory "
        "bar is the highest point reached during the last run, so you can see at "
        "a glance how close a workflow came to filling your card, and whether a "
        "bigger model would still fit.\n\n"
        "The Free VRAM button unloads the models ComfyUI is holding, the same as "
        "the Free model and node cache item in ComfyUI's own menu. Useful before "
        "loading a big model, or when another program needs the card.\n\n"
        "Right-click the node, or use the gear on the node toolbar, to choose "
        "which readouts to show, switch between the full bars and a one-line "
        "strip, and set how often it updates. Drag the corner to make it bigger. "
        "It does not need to be wired to anything: just drop it on the canvas."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ()
    FUNCTION = "noop"
    # OUTPUT_NODE intentionally NOT set: ComfyUI skips this node on Run, so it
    # never appears in the prompt and draws no timing badge. It is a pure
    # frontend control - all of the work happens in js/monitor/.
    CATEGORY = "👑 Pixaroma/🔀 Logic & Flow"

    def noop(self):
        return ()


NODE_CLASS_MAPPINGS = {
    "PixaromaMonitor": PixaromaMonitor,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PixaromaMonitor": "Monitor Pixaroma",
}
