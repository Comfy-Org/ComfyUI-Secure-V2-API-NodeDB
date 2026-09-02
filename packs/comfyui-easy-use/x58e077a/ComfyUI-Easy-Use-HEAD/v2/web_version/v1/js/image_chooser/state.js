import { comfy } from '/comfy/api/v2.js';

// The HUD class is gone. It was a change detector over app.runningNodeId, and
// the only thing that drove it was chooser.js overriding LGraphCanvas.draw to
// poll it every frame. comfy.onExecutingNodeChanged reports that same change as
// an event, so neither the detector nor the draw override has anything to do.

class FlowState {
    constructor(){}
    static idle() {
        return (!comfy.executingNode());
    }
    static paused() {
        return true;
    }
    static paused_here(node_id) {
        return (FlowState.paused() && FlowState.here(node_id))
    }
    static running() {
        return (!FlowState.idle());
    }
    static here(node_id) {
        // Loose, as before: a handle's id is a string and callers pass whatever
        // they were given.
        return (comfy.executingNode()?.id == node_id);
    }
    static state() {
        if (FlowState.paused()) return "Paused";
        if (FlowState.running()) return "Running";
        return "Idle";
    }
    static cancelling = false;
}

export { FlowState }
