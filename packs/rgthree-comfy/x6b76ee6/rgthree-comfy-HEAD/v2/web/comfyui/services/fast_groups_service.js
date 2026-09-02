import { comfy } from '/comfy/api/v2.js';

// The shared scheduler behind Fast Groups Muter / Bypasser: it tells every fast
// group node to rebuild its rows on a throttle, because nothing announces a group
// being drawn, retitled, recoloured, or dragged over a different set of nodes.
//
// The original also recomputed membership itself, cached node boundings, and wrote
// `group._children` / `group.nodes` / `group.rgthree_hasAnyActiveNode` back onto the
// group. None of that survives: `group.nodes()` recomputes on every call, so the
// list is read where it is used and never stored.
//
// A group inside a subgraph gets a row again: `subgraph.groups()` is the
// `graph.subgraphs.values()` walk the original did, and group ids are allocated from
// the root graph's counter, so one id names one group across the whole document.
//
// The rescan was suppressed while `canvas.isDragging` or `canvas.selected_group_moving`
// was set, so it did not fight a drag in progress. Those are two readings of one
// question — is the editor already mid-gesture — and `comfy.isInteracting()` is that
// question published; which gestures exist is the editor's business, which is why there
// is no per-gesture flag to translate one-for-one.
const MS_THRESHOLD = 400;
class FastGroupsService {
    constructor() {
        this.fastGroupNodes = [];
        this.runScheduledForMs = null;
        this.runScheduleTimeout = null;
        this.runScheduleAnimation = null;
    }
    addFastGroupNode(refreshWidgets) {
        this.fastGroupNodes.push(refreshWidgets);
        this.scheduleRun(8);
    }
    removeFastGroupNode(refreshWidgets) {
        const index = this.fastGroupNodes.indexOf(refreshWidgets);
        if (index > -1) {
            this.fastGroupNodes.splice(index, 1);
        }
        if (!this.fastGroupNodes.length) {
            this.clearScheduledRun();
        }
    }
    run() {
        if (!this.runScheduledForMs) {
            return;
        }
        // Stand down while the editor is mid-gesture and come back on the next tick,
        // exactly as the `canvas.isDragging` / `selected_group_moving` guard did.
        if (comfy.isInteracting()) {
            this.clearScheduledRun();
            this.scheduleRun(8);
            return;
        }
        for (const refreshWidgets of [...this.fastGroupNodes]) {
            refreshWidgets();
        }
        this.clearScheduledRun();
        this.scheduleRun();
    }
    scheduleRun(ms = 500) {
        if (this.runScheduledForMs && ms < this.runScheduledForMs) {
            this.clearScheduledRun();
        }
        if (!this.runScheduledForMs && this.fastGroupNodes.length) {
            this.runScheduledForMs = ms;
            this.runScheduleTimeout = setTimeout(() => {
                this.runScheduleAnimation = requestAnimationFrame(() => this.run());
            }, ms);
        }
    }
    clearScheduledRun() {
        this.runScheduleTimeout && clearTimeout(this.runScheduleTimeout);
        this.runScheduleAnimation && cancelAnimationFrame(this.runScheduleAnimation);
        this.runScheduleTimeout = null;
        this.runScheduleAnimation = null;
        this.runScheduledForMs = null;
    }
    // Sorted per call rather than cached: `comfy.graph.groups()` is a read of the
    // group list, and a cache is what would make a group dragged to a new position
    // sort against a stale one.
    getGroups(sort) {
        const groups = [
            ...comfy.graph.groups(),
            ...comfy.graph.subgraphs().flatMap((subgraph) => subgraph.groups()),
        ];
        if (sort === "alphanumeric") {
            return groups.sort((a, b) => a.getTitle().localeCompare(b.getTitle()));
        }
        if (sort === "position") {
            return groups.sort((a, b) => {
                const aBounds = a.getBounds();
                const bBounds = b.getBounds();
                const aY = Math.floor(aBounds.y / 30);
                const bY = Math.floor(bBounds.y / 30);
                if (aY == bY) {
                    return Math.floor(aBounds.x / 30) - Math.floor(bBounds.x / 30);
                }
                return aY - bY;
            });
        }
        return groups;
    }
}
export const SERVICE = new FastGroupsService();
// A newly opened workflow has an entirely different set of groups, and the throttle
// would otherwise leave the previous workflow's rows up for MS_THRESHOLD.
comfy.onWorkflowLoaded(() => SERVICE.scheduleRun(MS_THRESHOLD));
