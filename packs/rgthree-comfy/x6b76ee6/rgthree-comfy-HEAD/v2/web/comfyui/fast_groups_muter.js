import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "./constants.js";
import { SERVICE as FAST_GROUPS_SERVICE } from "./services/fast_groups_service.js";
import { exposeActions, helpMenuItem } from "./base_node.js";

// Fast Groups Muter — an input-less node that lists every group in the workflow as
// a toggle row with a jump-to-group arrow, filtered by colour or title regex, sorted
// by position / alphanumeric / a custom alphabet, and mutes or unmutes every node in
// the group you toggle. Fast Groups Bypasser is the same node with mode `bypass`
// instead of `never`, and builds on `defineFastGroupsModeChanger` below.
//
// The rows were a hand-drawn canvas widget with their own hit testing, split by an x
// threshold against `node.size[0]`; mounted in the DOM they are two buttons and a
// label, and the geometry goes away. Membership is read through `group.nodes()` at
// the moment it is used — never stored — so a node dragged into or out of a group is
// picked up on the next rescan, with no event to listen for.
//
// LIMITATION: the jump arrow also zoomed out to fit the group
//   (`canvas.canvas.width / group._size[0]`, clamped against the current scale).
//   `group.centerOn()` pans to it and `comfy.graph.setZoom()` would set the scale, but
//   the viewport's pixel size is not published, so the fit cannot be computed and the
//   arrow centres at the zoom the user is already at. That is exactly what the original
//   did whenever the group already fitted; a group larger than the view is now centred
//   rather than framed.
// NO LONGER A GAP: the colour filter resolves named colours again. This read
//   `LGraphCanvas.node_colors[name].groupcolor` and was refused as "no node-colour
//   palette" — an absence, which is a gap wearing a refusal's label. The names are
//   the user's own vocabulary: they pick "red" from a menu and only the hex is
//   kept, so "mute every red group" cannot match what they chose without being
//   told which hex "red" meant. `comfy.defs.nodeColor(name)` publishes it.
// `exposedActions` / `handleAction` ("Mute all"/"Bypass all", "Enable all", "Toggle
// all") is rgthree's own convention, declared on the class and read by rgthree's own
// Fast Actions Button, so it never needed the host; it is `exposeActions` now (see
// base_node.js). `getHelp()` and the "🛟 Node Help" entry go the same way.
//
// COSMETIC: no property metadata. `BaseFastGroupsModeChanger["@sort"] = {type: "combo",
// values: [...]}` and its five siblings told the properties panel which control to edit
// each property with. They still save and still work; they are free-text fields now.
//
// `showAllGraphs` is live again: `subgraph.groups()` lists a subgraph's own groups
// (see services/fast_groups_service.js), and `comfy.graph.subgraphs()` reaches its
// nodes, so the mode change below is recursive.
//
// WIRE FORMAT: `serialize_widgets` is false, as it was, so no row reaches
// `widgets_values`. The node's whole configuration is in its properties.
const PROPERTY_SORT = "sort";
const PROPERTY_SORT_CUSTOM_ALPHA = "customSortAlphabet";
const PROPERTY_MATCH_COLORS = "matchColors";
const PROPERTY_MATCH_TITLE = "matchTitle";
const PROPERTY_SHOW_NAV = "showNav";
const PROPERTY_SHOW_ALL_GRAPHS = "showAllGraphs";
const PROPERTY_RESTRICTION = "toggleRestriction";
// Handles hold no arbitrary properties, so the rows and the scheduler registration
// live here, keyed by node id, and are dropped in onRemoved.
const rowsByNode = new Map();
const refreshByNode = new Map();
function rowsFor(nodeId) {
    let rows = rowsByNode.get(nodeId);
    if (!rows) {
        rowsByNode.set(nodeId, (rows = new Map()));
    }
    return rows;
}
function normalizeColor(color) {
    // A name the user picked from ComfyUI's palette resolves to the shade a
    // group of that colour is filled with; anything else is already a hex.
    const named = comfy.defs.nodeColor(color.trim().toLocaleLowerCase());
    let normalized = (named?.groupColor ?? color)
        .replace("#", "")
        .trim()
        .toLocaleLowerCase();
    if (normalized.length === 3) {
        normalized = normalized.replace(/(.)(.)(.)/, "$1$1$2$2$3$3");
    }
    return `#${normalized}`;
}
function customAlphabetFor(node) {
    if (node.getProperty(PROPERTY_SORT) !== "custom alphabet") {
        return null;
    }
    const customAlphaStr = String(node.getProperty(PROPERTY_SORT_CUSTOM_ALPHA) ?? "").replace(/\n/g, "");
    if (!customAlphaStr.trim()) {
        return null;
    }
    const alphabet = customAlphaStr.includes(",")
        ? customAlphaStr.toLocaleLowerCase().split(",")
        : customAlphaStr.toLocaleLowerCase().trim().split("");
    return alphabet.length ? alphabet : null;
}
function sortByCustomAlphabet(groups, customAlphabet) {
    return groups.sort((a, b) => {
        const aTitle = a.getTitle();
        const bTitle = b.getTitle();
        let aIndex = -1;
        let bIndex = -1;
        for (const [index, alpha] of customAlphabet.entries()) {
            aIndex = aIndex < 0 ? (aTitle.toLocaleLowerCase().startsWith(alpha) ? index : -1) : aIndex;
            bIndex = bIndex < 0 ? (bTitle.toLocaleLowerCase().startsWith(alpha) ? index : -1) : bIndex;
            if (aIndex > -1 && bIndex > -1) {
                break;
            }
        }
        if (aIndex > -1 && bIndex > -1) {
            const ret = aIndex - bIndex;
            return ret === 0 ? aTitle.localeCompare(bTitle) : ret;
        }
        if (aIndex > -1) {
            return -1;
        }
        if (bIndex > -1) {
            return 1;
        }
        return aTitle.localeCompare(bTitle);
    });
}
// A group dragged, retitled or recoloured changes this answer with nothing to
// announce it, so it is recomputed on every rescan rather than cached.
function matchingGroups(node) {
    const customAlphabet = customAlphabetFor(node);
    const sort = customAlphabet
        ? "alphanumeric"
        : (node.getProperty(PROPERTY_SORT) || "position");
    let groups = [...FAST_GROUPS_SERVICE.getGroups(sort)];
    if (customAlphabet) {
        groups = sortByCustomAlphabet(groups, customAlphabet);
    }
    const filterColors = String(node.getProperty(PROPERTY_MATCH_COLORS) ?? "")
        .split(",")
        .filter((c) => c.trim())
        .map(normalizeColor);
    const matchTitle = String(node.getProperty(PROPERTY_MATCH_TITLE) ?? "").trim();
    let titleRegex = null;
    if (matchTitle) {
        try {
            titleRegex = new RegExp(matchTitle, "i");
        }
        catch (e) {
            console.error(e);
            return [];
        }
    }
    // `group.graph !== canvas.getCurrentGraph()` in the original. Group ids come
    // from the root graph's counter, so the ids on screen identify the same set.
    const onScreen = node.getProperty(PROPERTY_SHOW_ALL_GRAPHS)
        ? null
        : new Set(comfy.graph.groups().map((group) => group.id));
    return groups.filter((group) => {
        if (filterColors.length) {
            const groupColor = group.getColor();
            if (!groupColor || !filterColors.includes(normalizeColor(groupColor))) {
                return false;
            }
        }
        if (titleRegex && !titleRegex.exec(group.getTitle())) {
            return false;
        }
        return !onScreen || onScreen.has(group.id);
    });
}
// `changeModeOfNodes` walked into a subgraph node's children as well as setting the
// node's own mode. A subgraph node's `type` is its definition's id, which is what
// `comfy.graph.subgraphs()` is keyed on, so the descent is expressible again.
function setModeDeep(nodes, mode) {
    const definitions = new Map(comfy.graph.subgraphs().map((s) => [s.id, s]));
    const stack = [...nodes];
    const entered = new Set();
    while (stack.length) {
        const node = stack.pop();
        node.setMode(mode);
        if (entered.has(node.type)) {
            continue;
        }
        const subgraph = definitions.get(node.type);
        if (subgraph) {
            entered.add(node.type);
            stack.push(...subgraph.nodes());
        }
    }
}
function getHelp(type, helpActions) {
    return `
      <p>The ${type.replace("(rgthree)", "")} is an input-less node that automatically collects all groups in your current
      workflow and allows you to quickly ${helpActions} all nodes within the group.</p>
      <ul>
        <li>
          <p>
            <strong>Properties.</strong> You can change the following properties (by right-clicking
            on the node, and select "Properties" or "Properties Panel" from the menu):
          </p>
          <ul>
            <li><p>
              <code>${PROPERTY_MATCH_COLORS}</code> - Only add groups that match the provided
              colors. Can be ComfyUI colors (red, pale_blue) or hex codes (#a4d399). Multiple can be
              added, comma delimited.
            </p></li>
            <li><p>
              <code>${PROPERTY_MATCH_TITLE}</code> - Filter the list of toggles by title match
              (string match, or regular expression).
            </p></li>
            <li><p>
              <code>${PROPERTY_SHOW_NAV}</code> - Add / remove a quick navigation arrow to take you
              to the group. <i>(default: true)</i>
            </p></li>
            <li><p>
              <code>${PROPERTY_SHOW_ALL_GRAPHS}</code> - Show groups from all [sub]graphs in the
              workflow. <i>(default: true)</i>
            </p></li>
            <li><p>
              <code>${PROPERTY_SORT}</code> - Sort the toggles' order by "alphanumeric", graph
              "position", or "custom alphabet". <i>(default: "position")</i>
            </p></li>
            <li>
              <p>
                <code>${PROPERTY_SORT_CUSTOM_ALPHA}</code> - When the
                <code>${PROPERTY_SORT}</code> property is "custom alphabet" you can define the
                alphabet to use here, which will match the <i>beginning</i> of each group name and
                sort against it. If group titles do not match any custom alphabet entry, then they
                will be put after groups that do, ordered alphanumerically.
              </p>
              <p>
                This can be a list of single characters, like "zyxw..." or comma delimited strings
                for more control, like "sdxl,pro,sd,n,p".
              </p>
              <p>
                Note, when two group title match the same custom alphabet entry, the <i>normal
                alphanumeric alphabet</i> breaks the tie. For instance, a custom alphabet of
                "e,s,d" will order groups names like "SDXL, SEGS, Detailer" eventhough the custom
                alphabet has an "e" before "d" (where one may expect "SE" to be before "SD").
              </p>
              <p>
                To have "SEGS" appear before "SDXL" you can use longer strings. For instance, the
                custom alphabet value of "se,s,f" would work here.
              </p>
            </li>
            <li><p>
              <code>${PROPERTY_RESTRICTION}</code> - Optionally, attempt to restrict the number of
              widgets that can be enabled to a maximum of one, or always one.
              </p>
              <p><em><strong>Note:</strong> If using "max one" or "always one" then this is only
              enforced when clicking a toggle on this node; if nodes within groups are changed
              outside of the initial toggle click, then these restriction will not be enforced, and
              could result in a state where more than one toggle is enabled. This could also happen
              if nodes are overlapped with multiple groups.
            </p></li>

          </ul>
        </li>
      </ul>`;
}
export function defineFastGroupsModeChanger({ type, modeOff, offAction, helpActions }) {
    const modeOn = "always";
    // Direct children only, as `rgthree_hasAnyActiveNode` was: a group's toggle
    // reports the group, not everything nested under it.
    function hasAnyActiveNode(group) {
        return group.nodes().some((n) => n.getMode() === modeOn);
    }
    function doModeChange(node, row, force, skipOtherNodeCheck) {
        const rows = rowsFor(node.id);
        let newValue = force != null ? force : !hasAnyActiveNode(row.group);
        if (skipOtherNodeCheck !== true) {
            const restriction = String(node.getProperty(PROPERTY_RESTRICTION) ?? "default");
            if (newValue && restriction.includes(" one")) {
                for (const other of rows.values()) {
                    doModeChange(node, other, false, true);
                }
            }
            else if (!newValue && restriction === "always one") {
                newValue = [...rows.values()].every((other) => !other.toggled || other === row);
            }
        }
        setModeDeep(row.group.nodes(), newValue ? modeOn : modeOff);
        row.setToggled(newValue);
    }
    function buildRow(node, group) {
        const row = {
            group,
            toggled: false,
            setToggled: () => { },
            setLabel: () => { },
            setNavVisible: () => { },
        };
        node.widgets.mount({
            name: group.id,
            height: 20,
            render(container) {
                container.style.display = "flex";
                container.style.alignItems = "center";
                container.style.gap = "6px";
                container.style.width = "100%";
                const label = document.createElement("span");
                label.style.flex = "1";
                label.style.overflow = "hidden";
                label.style.textOverflow = "ellipsis";
                label.style.whiteSpace = "nowrap";
                const toggle = document.createElement("button");
                // One click can flip several groups' worth of nodes under the
                // "max one" / "always one" restriction; `batch` makes the gesture
                // one undo step instead of one per node.
                toggle.addEventListener("click", () => comfy.graph.batch(() => doModeChange(node, row)));
                const nav = document.createElement("button");
                nav.textContent = "➡";
                nav.title = "Jump to group";
                nav.addEventListener("click", () => row.group.centerOn());
                container.append(label, toggle, nav);
                row.setLabel = (text) => {
                    label.textContent = text;
                };
                row.setToggled = (value) => {
                    row.toggled = value;
                    toggle.textContent = value ? "yes" : "no";
                };
                row.setNavVisible = (visible) => {
                    nav.style.display = visible ? "" : "none";
                };
                row.setToggled(row.toggled);
            },
        });
        return row;
    }
    function refreshWidgets(node) {
        if (node.isDeleted) {
            return;
        }
        const rows = rowsFor(node.id);
        const groups = matchingGroups(node);
        const wanted = new Set(groups.map((group) => group.id));
        for (const groupId of [...rows.keys()]) {
            if (!wanted.has(groupId)) {
                node.widgets.remove(groupId);
                rows.delete(groupId);
            }
        }
        const showNav = node.getProperty(PROPERTY_SHOW_NAV) !== false;
        for (const group of groups) {
            let row = rows.get(group.id);
            if (!row) {
                rows.set(group.id, (row = buildRow(node, group)));
            }
            // The handle is re-read every pass: a group's title, colour and contents
            // all move under it with nothing to announce the change.
            row.group = group;
            row.setLabel(`Enable ${group.getTitle()}`);
            row.setNavVisible(showNav);
            const active = hasAnyActiveNode(group);
            if (row.toggled !== active) {
                row.setToggled(active);
            }
        }
        const order = groups.map((group) => group.id);
        const names = node.widgets.names();
        if (names.length === order.length && names.some((name, i) => name !== order[i])) {
            node.widgets.reorder(order);
        }
    }
    // Rows are ordered here, so "index 0" and "the last one" — which the original read
    // off `this.widgets` — are the first and last of `rowsFor(node.id)`, whose insertion
    // order `refreshWidgets` keeps matching the displayed order.
    exposeActions(type, [offAction, "Enable all", "Toggle all"], (node, action) => {
        const rows = [...rowsFor(node.id).values()];
        const restriction = String(node.getProperty(PROPERTY_RESTRICTION) ?? "default");
        comfy.graph.batch(() => {
            if (action === offAction) {
                const alwaysOne = restriction === "always one";
                rows.forEach((row, index) => doModeChange(node, row, alwaysOne && !index, true));
                return;
            }
            const onlyOne = restriction.includes(" one");
            if (action === "Enable all") {
                rows.forEach((row, index) => doModeChange(node, row, !(onlyOne && index > 0), true));
                return;
            }
            let foundOne = false;
            for (const row of rows) {
                const newValue = onlyOne && foundOne ? false : !row.toggled;
                foundOne = foundOne || newValue;
                doModeChange(node, row, newValue, true);
            }
            if (!foundOne && restriction === "always one" && rows.length) {
                doModeChange(node, rows[rows.length - 1], true, true);
            }
        });
    });
    comfy.defs.extend(type, (b) => {
        b.addMenuItem(helpMenuItem(type, getHelp(type, helpActions)));
    });
    return comfy.defs.define({
        type,
        title: type,
        category: "rgthree",
        // The node drives other nodes' modes and must never reach graphToPrompt.
        execution: 'frontend',
        outputs: [{ name: "OPT_CONNECTION", type: "*" }],
        onCreated(node) {
            node.setSerializeWidgets(false);
            node.setSizeConstraints({ autoHeight: true });
            node.setProperty(PROPERTY_MATCH_COLORS, "");
            node.setProperty(PROPERTY_MATCH_TITLE, "");
            node.setProperty(PROPERTY_SHOW_NAV, true);
            node.setProperty(PROPERTY_SHOW_ALL_GRAPHS, true);
            node.setProperty(PROPERTY_SORT, "position");
            node.setProperty(PROPERTY_SORT_CUSTOM_ALPHA, "");
            node.setProperty(PROPERTY_RESTRICTION, "default");
            const refresh = () => refreshWidgets(node);
            refreshByNode.set(node.id, refresh);
            FAST_GROUPS_SERVICE.addFastGroupNode(refresh);
        },
        // A property edit changes which groups are listed and in what order, so it
        // must not wait for the throttle.
        onPropertyChanged(node) {
            refreshWidgets(node);
        },
        onRemoved(node) {
            const refresh = refreshByNode.get(node.id);
            if (refresh) {
                FAST_GROUPS_SERVICE.removeFastGroupNode(refresh);
            }
            refreshByNode.delete(node.id);
            rowsByNode.delete(node.id);
        },
    });
}
defineFastGroupsModeChanger({
    type: NodeTypesString.FAST_GROUPS_MUTER,
    modeOff: "never",
    offAction: "Mute all",
    helpActions: "mute and unmute",
});
