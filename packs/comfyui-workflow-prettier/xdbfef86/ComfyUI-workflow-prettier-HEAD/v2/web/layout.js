export const PRETTIFIER_NODE_TYPE = "WorkflowPrettifier";
export const MAX_UNDO = 10;

export const DEFAULT_OPTIONS = Object.freeze({
  layout: "Layered (Vertical Stacks)",
  direction: "Left to Right",
  groupHandling: "Auto (Respect Groups)",
  horizontalSpacing: 100,
  verticalSpacing: 100,
  groupPadding: 100,
});

function position(node) {
  return node.getPosition();
}

function size(node) {
  return node.getSize();
}

function move(node, x, y) {
  node.setPosition({ x, y });
}

function workflowNodes(graph) {
  return graph.nodes().filter((node) => node.type !== PRETTIFIER_NODE_TYPE);
}

function linksFor(graph) {
  return graph.links().filter(Boolean);
}

export function buildDAG(graph, nodes = workflowNodes(graph)) {
  const nodeMap = new Map();
  const adj = new Map();
  const revAdj = new Map();
  const ids = new Set();

  for (const node of nodes) {
    nodeMap.set(node.id, node);
    adj.set(node.id, []);
    revAdj.set(node.id, []);
    ids.add(node.id);
  }

  for (const link of linksFor(graph)) {
    const source = link.sourceNodeId;
    const target = link.targetNodeId;
    if (ids.has(source) && ids.has(target)) {
      adj.get(source).push(target);
      revAdj.get(target).push(source);
    }
  }
  return { adj, revAdj, nodeMap };
}

export function topoSort(nodeMap, adj, revAdj) {
  const inDegree = new Map();
  for (const id of nodeMap.keys()) inDegree.set(id, revAdj.get(id)?.length ?? 0);

  const queue = [];
  for (const [id, degree] of inDegree) if (degree === 0) queue.push(id);
  queue.sort((left, right) => {
    const a = position(nodeMap.get(left));
    const b = position(nodeMap.get(right));
    return a.y !== b.y ? a.y - b.y : a.x - b.x;
  });

  const sorted = [];
  const visited = new Set();
  while (queue.length) {
    const id = queue.shift();
    sorted.push(id);
    visited.add(id);
    for (const target of adj.get(id) ?? []) {
      const next = inDegree.get(target) - 1;
      inDegree.set(target, next);
      if (next === 0) queue.push(target);
    }
  }
  // Cycles are intentionally retained, in stable graph order.
  for (const id of nodeMap.keys()) if (!visited.has(id)) sorted.push(id);
  return sorted;
}

function assignLayers(topo, adj) {
  const layer = new Map(topo.map((id) => [id, 0]));
  for (const id of topo) {
    const current = layer.get(id);
    for (const target of adj.get(id) ?? []) {
      if (current + 1 > layer.get(target)) layer.set(target, current + 1);
    }
  }
  return layer;
}

function layerArrays(layerMap) {
  const max = Math.max(...layerMap.values(), 0);
  const layers = Array.from({ length: max + 1 }, () => []);
  for (const [id, layer] of layerMap) layers[layer].push(id);
  return layers;
}

function barycenter(id, neighborAdj, neighborLayer, positions) {
  const neighbors = (neighborAdj.get(id) ?? []).filter((item) => neighborLayer.includes(item));
  if (!neighbors.length) return null;
  return neighbors.reduce((sum, item) => sum + (positions.get(item) ?? 0), 0) / neighbors.length;
}

function minimizeCrossings(rawLayers, adj, revAdj, nodeMap) {
  const layers = rawLayers.map((layer) => [...layer]);
  for (const layer of layers) {
    layer.sort((left, right) => position(nodeMap.get(left)).y - position(nodeMap.get(right)).y);
  }

  for (let pass = 0; pass < 6; pass += 1) {
    for (let index = 1; index < layers.length; index += 1) {
      const positions = new Map(layers[index - 1].map((id, order) => [id, order]));
      layers[index] = layers[index]
        .map((id, order) => ({ id, order, value: barycenter(id, revAdj, layers[index - 1], positions) }))
        .sort((a, b) => a.value == null ? (b.value == null ? a.order - b.order : 1)
          : b.value == null ? -1 : a.value - b.value)
        .map(({ id }) => id);
    }
    for (let index = layers.length - 2; index >= 0; index -= 1) {
      const positions = new Map(layers[index + 1].map((id, order) => [id, order]));
      layers[index] = layers[index]
        .map((id, order) => ({ id, order, value: barycenter(id, adj, layers[index + 1], positions) }))
        .sort((a, b) => a.value == null ? (b.value == null ? a.order - b.order : 1)
          : b.value == null ? -1 : a.value - b.value)
        .map(({ id }) => id);
    }
  }
  return layers;
}

function alignLayer(layer, neighborAdj, referenceLayer, yPositions, nodeMap, spacing) {
  const reference = new Set(referenceLayer);
  const positioned = [];
  const unpositioned = [];

  for (const id of layer) {
    const neighbors = (neighborAdj.get(id) ?? []).filter((item) => reference.has(item));
    if (!neighbors.length) {
      unpositioned.push(id);
      continue;
    }
    const centers = neighbors
      .map((item) => (yPositions.get(item) ?? 0) + size(nodeMap.get(item)).height / 2)
      .sort((a, b) => a - b);
    const middle = Math.floor(centers.length / 2);
    const median = centers.length % 2 ? centers[middle] : (centers[middle - 1] + centers[middle]) / 2;
    yPositions.set(id, median - size(nodeMap.get(id)).height / 2);
    positioned.push(id);
  }

  let lastBottom = 0;
  for (const id of positioned) {
    lastBottom = Math.max(lastBottom, (yPositions.get(id) ?? 0) + size(nodeMap.get(id)).height);
  }
  for (const id of unpositioned) {
    yPositions.set(id, lastBottom + spacing);
    lastBottom += size(nodeMap.get(id)).height + spacing;
  }

  const ordered = [...layer].sort((a, b) => (yPositions.get(a) ?? 0) - (yPositions.get(b) ?? 0));
  for (let index = 1; index < ordered.length; index += 1) {
    const previous = ordered[index - 1];
    const bottom = (yPositions.get(previous) ?? 0) + size(nodeMap.get(previous)).height;
    if ((yPositions.get(ordered[index]) ?? 0) < bottom + spacing) {
      yPositions.set(ordered[index], bottom + spacing);
    }
  }
}

function assignCoordinates(layers, adj, revAdj, nodeMap, spacing) {
  const yPositions = new Map();
  if (!layers.length) return yPositions;
  let anchor = 0;
  for (let index = 1; index < layers.length; index += 1) {
    if (layers[index].length > layers[anchor].length) anchor = index;
  }

  let y = 0;
  for (const id of layers[anchor]) {
    yPositions.set(id, y);
    y += size(nodeMap.get(id)).height + spacing;
  }
  for (let index = anchor + 1; index < layers.length; index += 1) {
    alignLayer(layers[index], revAdj, layers[index - 1], yPositions, nodeMap, spacing);
  }
  for (let index = anchor - 1; index >= 0; index -= 1) {
    alignLayer(layers[index], adj, layers[index + 1], yPositions, nodeMap, spacing);
  }

  const minimum = Math.min(...yPositions.values(), 0);
  if (Number.isFinite(minimum) && minimum !== 0) {
    for (const [id, value] of yPositions) yPositions.set(id, value - minimum);
  }
  return yPositions;
}

export function layoutLayered(graph, nodes, startX, startY, options = {}) {
  if (!nodes.length) return { width: 0, height: 0 };
  if (nodes.length === 1) {
    move(nodes[0], startX, startY);
    return { ...size(nodes[0]) };
  }
  const horizontal = options.horizontalSpacing ?? 100;
  const vertical = options.verticalSpacing ?? 100;
  const { adj, revAdj, nodeMap } = buildDAG(graph, nodes);
  const topo = topoSort(nodeMap, adj, revAdj);
  const layers = minimizeCrossings(layerArrays(assignLayers(topo, adj)), adj, revAdj, nodeMap);
  const yPositions = assignCoordinates(layers, adj, revAdj, nodeMap, vertical);
  const widths = layers.map((layer) => Math.max(...layer.map((id) => size(nodeMap.get(id)).width), 200));

  let x = startX;
  let totalWidth = 0;
  let totalHeight = 0;
  layers.forEach((layer, column) => {
    for (const id of layer) {
      const node = nodeMap.get(id);
      move(node, x, startY + (yPositions.get(id) ?? 0));
      totalHeight = Math.max(totalHeight, position(node).y + size(node).height - startY);
    }
    x += widths[column] + horizontal;
    totalWidth = x - startX - horizontal;
  });
  return { width: totalWidth, height: totalHeight };
}

export function layoutLinear(graph, nodes, startX, startY, options = {}) {
  if (!nodes.length) return { width: 0, height: 0 };
  const horizontal = options.horizontalSpacing ?? 100;
  const { adj, revAdj, nodeMap } = buildDAG(graph, nodes);
  let x = startX;
  let maxHeight = 0;
  for (const id of topoSort(nodeMap, adj, revAdj)) {
    const node = nodeMap.get(id);
    move(node, x, startY);
    x += size(node).width + horizontal;
    maxHeight = Math.max(maxHeight, size(node).height);
  }
  return { width: x - startX - horizontal, height: maxHeight };
}

export function layoutCompact(_graph, nodes, startX, startY, options = {}) {
  if (!nodes.length) return { width: 0, height: 0 };
  const horizontal = options.horizontalSpacing ?? 100;
  const vertical = options.verticalSpacing ?? 100;
  const sorted = [...nodes].sort((a, b) => size(b).height - size(a).height);
  const area = sorted.reduce((sum, node) => sum +
    (size(node).width + horizontal) * (size(node).height + vertical), 0);
  const targetWidth = Math.sqrt(area) * 1.1;
  let shelfX = startX;
  let shelfY = startY;
  let shelfHeight = 0;
  let maxX = startX;
  let maxY = startY;
  for (const node of sorted) {
    const dimensions = size(node);
    if (shelfX + dimensions.width - startX > targetWidth && shelfX > startX) {
      shelfY += shelfHeight + vertical;
      shelfX = startX;
      shelfHeight = 0;
    }
    move(node, shelfX, shelfY);
    shelfX += dimensions.width + horizontal;
    shelfHeight = Math.max(shelfHeight, dimensions.height);
    maxX = Math.max(maxX, shelfX);
    maxY = Math.max(maxY, shelfY + dimensions.height);
  }
  return { width: maxX - startX - horizontal, height: maxY - startY };
}

export function layoutSortByType(graph, nodes, startX, startY, options = {}) {
  if (!nodes.length) return { width: 0, height: 0 };
  const horizontal = options.horizontalSpacing ?? 100;
  const vertical = options.verticalSpacing ?? 100;
  const groups = new Map();
  for (const node of nodes) {
    if (!groups.has(node.type)) groups.set(node.type, []);
    groups.get(node.type).push(node);
  }
  const { adj, revAdj, nodeMap } = buildDAG(graph, nodes);
  const layers = assignLayers(topoSort(nodeMap, adj, revAdj), adj);
  const average = new Map([...groups].map(([type, items]) => [
    type,
    items.reduce((sum, item) => sum + (layers.get(item.id) ?? 0), 0) / items.length,
  ]));
  const types = [...groups.keys()].sort((a, b) => average.get(a) - average.get(b));
  let x = startX;
  let totalHeight = 0;
  for (const type of types) {
    let y = startY;
    let width = 0;
    for (const node of groups.get(type)) {
      move(node, x, y);
      width = Math.max(width, size(node).width);
      y += size(node).height + vertical;
    }
    totalHeight = Math.max(totalHeight, y - startY - vertical);
    x += width + horizontal;
  }
  return { width: x - startX - horizontal, height: totalHeight };
}

function resolveOverlaps(nodes, horizontal, vertical) {
  if (nodes.length < 2) return;
  const sorted = [...nodes].sort((a, b) => position(a).y - position(b).y);
  const rows = [];
  let row = [sorted[0]];
  for (const node of sorted.slice(1)) {
    const first = row[0];
    if (position(node).y < position(first).y + size(first).height - 10) row.push(node);
    else {
      rows.push(row);
      row = [node];
    }
  }
  rows.push(row);

  for (const items of rows) {
    items.sort((a, b) => position(a).x - position(b).x);
    for (let index = 1; index < items.length; index += 1) {
      const previous = items[index - 1];
      const required = position(previous).x + size(previous).width + horizontal;
      if (position(items[index]).x < required) move(items[index], required, position(items[index]).y);
    }
  }

  for (let index = 1; index < rows.length; index += 1) {
    const previousBottom = Math.max(...rows[index - 1].map((node) => position(node).y + size(node).height));
    const currentTop = Math.min(...rows[index].map((node) => position(node).y));
    if (currentTop >= previousBottom + vertical) continue;
    const shift = previousBottom + vertical - currentTop;
    for (const node of rows[index]) move(node, position(node).x, position(node).y + shift);
  }
}

function applyDirection(graph, nodes, direction, options) {
  if (direction === "Left to Right" || !nodes.length) return;
  const minX = Math.min(...nodes.map((node) => position(node).x));
  const minY = Math.min(...nodes.map((node) => position(node).y));
  const groups = graph.groups();

  if (direction === "Top to Bottom") {
    for (const node of nodes) {
      const current = position(node);
      move(node, minX + current.y - minY, minY + current.x - minX);
    }
    for (const group of groups) {
      const bounds = group.getBounds();
      group.setBounds({
        x: minX + bounds.y - minY,
        y: minY + bounds.x - minX,
        width: bounds.height,
        height: bounds.width,
      });
    }
    resolveOverlaps(nodes, options.horizontalSpacing ?? 100, options.verticalSpacing ?? 100);
  } else if (direction === "Right to Left") {
    const maximum = Math.max(...nodes.map((node) => position(node).x + size(node).width));
    for (const node of nodes) {
      const current = position(node);
      move(node, maximum - current.x - size(node).width, current.y);
    }
    for (const group of groups) {
      const bounds = group.getBounds();
      group.setBounds({ ...bounds, x: maximum - bounds.x - bounds.width });
    }
  }
}

export function partitionByGroup(graph) {
  const groups = graph.groups();
  const grouped = new Map(groups.map((group) => [group.id, []]));
  const assigned = new Set();
  for (const node of workflowNodes(graph)) {
    const nodePosition = position(node);
    const dimensions = size(node);
    const center = {
      x: nodePosition.x + dimensions.width / 2,
      y: nodePosition.y + dimensions.height / 2,
    };
    let best;
    let area = Infinity;
    for (const group of groups) {
      const bounds = group.getBounds();
      const inside = center.x >= bounds.x && center.x <= bounds.x + bounds.width &&
        center.y >= bounds.y && center.y <= bounds.y + bounds.height;
      const candidateArea = bounds.width * bounds.height;
      if (inside && candidateArea < area) {
        best = group;
        area = candidateArea;
      }
    }
    if (best) {
      grouped.get(best.id).push(node);
      assigned.add(node.id);
    }
  }
  return {
    groups,
    grouped,
    ungrouped: workflowNodes(graph).filter((node) => !assigned.has(node.id)),
  };
}

function virtualNode(id, width, height) {
  let currentPosition = { x: 0, y: 0 };
  return Object.freeze({
    id,
    type: "virtual",
    getPosition: () => ({ ...currentPosition }),
    setPosition: (next) => { currentPosition = { ...next }; },
    getSize: () => ({ width, height }),
  });
}

function layoutWithGroups(graph, layout, options) {
  const padding = options.groupPadding ?? 100;
  const titleHeight = 34;
  const groupSpacing = options.groupSpacing ?? 100;
  const { groups, grouped, ungrouped } = partitionByGroup(graph);
  if (![...grouped.values()].some((nodes) => nodes.length)) {
    layout(graph, workflowNodes(graph), 100, 100, options);
    return;
  }

  const groupSizes = new Map();
  for (const group of groups) {
    const nodes = grouped.get(group.id);
    groupSizes.set(group.id, nodes.length ? layout(graph, nodes, 0, 0, options) : { width: 0, height: 0 });
  }

  const owner = new Map();
  for (const [groupId, nodes] of grouped) for (const node of nodes) owner.set(node.id, `group:${groupId}`);
  for (const node of ungrouped) owner.set(node.id, `node:${node.id}`);

  const virtual = [];
  const virtualById = new Map();
  for (const group of groups) {
    if (!grouped.get(group.id).length) continue;
    const dimensions = groupSizes.get(group.id);
    const item = virtualNode(`group:${group.id}`, dimensions.width + padding * 2,
      dimensions.height + padding * 2 + titleHeight);
    virtual.push(item);
    virtualById.set(item.id, item);
  }
  for (const node of ungrouped) {
    const dimensions = size(node);
    const item = virtualNode(`node:${node.id}`, dimensions.width, dimensions.height);
    virtual.push(item);
    virtualById.set(item.id, item);
  }

  const seen = new Set();
  const virtualLinks = [];
  for (const link of graph.links()) {
    const source = owner.get(link.sourceNodeId);
    const target = owner.get(link.targetNodeId);
    const key = `${source}->${target}`;
    if (source && target && source !== target && !seen.has(key)) {
      seen.add(key);
      virtualLinks.push({ sourceNodeId: source, targetNodeId: target });
    }
  }
  const fakeGraph = Object.freeze({
    nodes: () => virtual,
    links: () => virtualLinks,
    groups: () => [],
  });
  layout(fakeGraph, virtual, 100, 100, {
    ...options,
    horizontalSpacing: groupSpacing,
    verticalSpacing: groupSpacing,
  });

  for (const group of groups) {
    const nodes = grouped.get(group.id);
    if (!nodes.length) continue;
    const item = virtualById.get(`group:${group.id}`);
    const origin = position(item);
    for (const node of nodes) {
      const current = position(node);
      move(node, current.x + origin.x + padding, current.y + origin.y + padding + titleHeight);
    }
    const dimensions = size(item);
    group.setBounds({ x: origin.x, y: origin.y, ...dimensions });
  }
  for (const node of ungrouped) {
    const target = position(virtualById.get(`node:${node.id}`));
    move(node, target.x, target.y);
  }
}

const LAYOUTS = Object.freeze({
  "Layered (Vertical Stacks)": layoutLayered,
  Linear: layoutLinear,
  "Compact (Tight Rectangle)": layoutCompact,
  "Sort by Type": layoutSortByType,
});

export function runPrettify(graph, options = DEFAULT_OPTIONS) {
  const resolved = { ...DEFAULT_OPTIONS, ...options };
  const layout = LAYOUTS[resolved.layout] ?? layoutLayered;
  const nodes = workflowNodes(graph);
  if (resolved.groupHandling === "Ignore Groups") layout(graph, nodes, 100, 100, resolved);
  else layoutWithGroups(graph, layout, resolved);
  applyDirection(graph, nodes, resolved.direction, resolved);
}

export function selectedWorkflowNodes(graph) {
  return graph.selection().filter((node) => node.type !== PRETTIFIER_NODE_TYPE);
}

export function alignNodes(graph, mode) {
  const selected = selectedWorkflowNodes(graph);
  if (selected.length < 2) return false;
  const widths = (node) => size(node).width;
  const heights = (node) => size(node).height;
  switch (mode) {
    case "left": {
      const value = Math.min(...selected.map((node) => position(node).x));
      selected.forEach((node) => move(node, value, position(node).y));
      break;
    }
    case "right": {
      const value = Math.max(...selected.map((node) => position(node).x + widths(node)));
      selected.forEach((node) => move(node, value - widths(node), position(node).y));
      break;
    }
    case "top": {
      const value = Math.min(...selected.map((node) => position(node).y));
      selected.forEach((node) => move(node, position(node).x, value));
      break;
    }
    case "bottom": {
      const value = Math.max(...selected.map((node) => position(node).y + heights(node)));
      selected.forEach((node) => move(node, position(node).x, value - heights(node)));
      break;
    }
    case "centerH": {
      const value = selected.reduce((sum, node) => sum + position(node).x + widths(node) / 2, 0) / selected.length;
      selected.forEach((node) => move(node, value - widths(node) / 2, position(node).y));
      break;
    }
    case "centerV": {
      const value = selected.reduce((sum, node) => sum + position(node).y + heights(node) / 2, 0) / selected.length;
      selected.forEach((node) => move(node, position(node).x, value - heights(node) / 2));
      break;
    }
    case "distributeH": {
      if (selected.length < 3) return false;
      const ordered = [...selected].sort((a, b) => position(a).x - position(b).x);
      const first = position(ordered[0]).x;
      const last = position(ordered.at(-1)).x + widths(ordered.at(-1));
      const gap = (last - first - ordered.reduce((sum, node) => sum + widths(node), 0)) / (ordered.length - 1);
      let cursor = first;
      for (const node of ordered) {
        move(node, cursor, position(node).y);
        cursor += widths(node) + gap;
      }
      break;
    }
    case "distributeV": {
      if (selected.length < 3) return false;
      const ordered = [...selected].sort((a, b) => position(a).y - position(b).y);
      const first = position(ordered[0]).y;
      const last = position(ordered.at(-1)).y + heights(ordered.at(-1));
      const gap = (last - first - ordered.reduce((sum, node) => sum + heights(node), 0)) / (ordered.length - 1);
      let cursor = first;
      for (const node of ordered) {
        move(node, position(node).x, cursor);
        cursor += heights(node) + gap;
      }
      break;
    }
    default:
      return false;
  }
  return true;
}

export function equalizeSpacing(graph, options = DEFAULT_OPTIONS) {
  const nodes = workflowNodes(graph);
  if (nodes.length < 2) return false;
  const horizontal = options.horizontalSpacing ?? 100;
  const vertical = options.verticalSpacing ?? 100;
  const sorted = [...nodes].sort((a, b) => position(a).x - position(b).x);
  const columns = [];
  let column = [sorted[0]];
  for (const node of sorted.slice(1)) {
    const previous = column.at(-1);
    if (position(node).x < position(previous).x + size(previous).width + horizontal * 0.3) column.push(node);
    else {
      columns.push(column);
      column = [node];
    }
  }
  columns.push(column);

  for (const items of columns) {
    items.sort((a, b) => position(a).y - position(b).y);
    let y = position(items[0]).y;
    for (const node of items) {
      move(node, position(node).x, y);
      y += size(node).height + vertical;
    }
  }
  let x = position(columns[0][0]).x;
  for (const items of columns) {
    let width = 0;
    for (const node of items) {
      move(node, x, position(node).y);
      width = Math.max(width, size(node).width);
    }
    x += width + horizontal;
  }
  return true;
}

export class LocalUndo {
  constructor(limit = MAX_UNDO) {
    this.limit = limit;
    this.stacks = new Map();
  }

  key(documentId, graph) {
    return `${documentId ?? "temporary"}:${graph.id}`;
  }

  depth(documentId, graph) {
    return this.stacks.get(this.key(documentId, graph))?.length ?? 0;
  }

  push(documentId, graph) {
    const key = this.key(documentId, graph);
    const stack = this.stacks.get(key) ?? [];
    stack.push({
      nodes: graph.nodes().map((node) => ({ id: node.id, position: position(node) })),
      groups: graph.groups().map((group) => ({ id: group.id, bounds: group.getBounds() })),
    });
    if (stack.length > this.limit) stack.shift();
    this.stacks.set(key, stack);
  }

  pop(documentId, graph) {
    const key = this.key(documentId, graph);
    const stack = this.stacks.get(key);
    const state = stack?.pop();
    if (!state) return false;
    const groups = new Map(graph.groups().map((group) => [group.id, group]));
    graph.batch(() => {
      for (const saved of state.nodes) {
        const node = graph.node(saved.id);
        if (node) node.setPosition(saved.position);
      }
      for (const saved of state.groups) groups.get(saved.id)?.setBounds(saved.bounds);
    });
    if (!stack.length) this.stacks.delete(key);
    return true;
  }

  clearDocument(documentId) {
    if (!documentId) return;
    for (const key of [...this.stacks.keys()]) {
      if (key.startsWith(`${documentId}:`)) this.stacks.delete(key);
    }
  }
}
