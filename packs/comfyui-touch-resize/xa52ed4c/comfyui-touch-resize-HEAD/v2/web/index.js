import { comfy } from "/comfy/api/v2.js";

import {
  RESIZE_CONFIG,
  createResizeController,
  handleCenters,
} from "./geometry.js";

function sameSize(left, right) {
  return left.width === right.width && left.height === right.height;
}

export function resolveTarget(graph) {
  const nodes = graph.selection();
  const groups = graph.groupSelection();
  if (nodes.length + groups.length !== 1) return undefined;

  if (nodes.length === 1) {
    const node = nodes[0];
    if (node.isPinned() || node.isCollapsed()) return undefined;
    return Object.freeze({
      id: `node:${node.id}`,
      kind: "node",
      handle: node,
      bounds: Object.freeze(node.getBounds()),
      position: Object.freeze(node.getPosition()),
      size: Object.freeze(node.getSize()),
      minimum: Object.freeze(node.getMinimumSize()),
    });
  }

  const group = groups[0];
  const bounds = Object.freeze(group.getBounds());
  return Object.freeze({
    id: `group:${group.id}`,
    kind: "group",
    handle: group,
    bounds,
    position: Object.freeze({ x: bounds.x, y: bounds.y }),
    size: Object.freeze({ width: bounds.width, height: bounds.height }),
    minimum: RESIZE_CONFIG.groupMinSize,
  });
}

export function installTouchResize(api = comfy) {
  const controller = createResizeController();
  let activeTarget;
  let regionSignature = "";
  let viewportScale = 1;
  let overlay;

  const updateHitRegions = (target, viewport) => {
    const regions = target
      ? handleCenters(target.bounds).map((point) => {
          const center = viewport.graphToViewport(point);
          return Object.freeze({
            kind: "circle",
            x: center.x,
            y: center.y,
            radius: RESIZE_CONFIG.hitRadiusPx,
          });
        })
      : [];
    const signature = JSON.stringify(regions);
    if (signature !== regionSignature) {
      regionSignature = signature;
      overlay.setHitRegions(regions);
    }
  };

  const draw = (context, _size, viewport) => {
    viewportScale = viewport.scale;
    const target = resolveTarget(api.graph);
    updateHitRegions(target, viewport);
    if (!target) return;
    context.save();
    context.globalAlpha = RESIZE_CONFIG.alpha;
    context.fillStyle = RESIZE_CONFIG.fillColor;
    context.strokeStyle = RESIZE_CONFIG.strokeColor;
    context.lineWidth = 2;
    for (const point of handleCenters(target.bounds)) {
      const center = viewport.graphToViewport(point);
      const radius = point.corner === controller.activeCorner
        ? RESIZE_CONFIG.handleRadiusPx * RESIZE_CONFIG.activeScale
        : RESIZE_CONFIG.handleRadiusPx;
      context.beginPath();
      context.arc(center.x, center.y, radius, 0, Math.PI * 2);
      context.fill();
      context.stroke();
    }
    context.restore();
  };

  const release = (pointerId) => {
    const command = controller.onPointerEnd(pointerId);
    if (!command) return;
    activeTarget = undefined;
    overlay.redraw();
  };

  overlay = api.ui.mountGraphOverlay({
    id: "comfy.touch-resize.handles",
    ariaLabel: "Touch resize handles",
    interactive: true,
    draw,
    onPointerDown(event) {
      if (controller.locked) return;
      const target = resolveTarget(api.graph);
      const command = controller.onPointerDown(
        { pointerId: event.pointerId, x: event.graph.x, y: event.graph.y },
        target,
        RESIZE_CONFIG.hitRadiusPx / Math.max(0.0001, viewportScale),
      );
      if (!command) return;
      activeTarget = target;
      overlay.redraw();
    },
    onPointerMove(event) {
      const command = controller.onPointerMove({
        pointerId: event.pointerId,
        x: event.graph.x,
        y: event.graph.y,
      });
      const target = activeTarget;
      if (!command || !target || target.id !== command.targetId) return;
      if (target.kind === "group") {
        target.handle.setBounds({ ...command.position, ...command.size });
      } else {
        const currentPosition = target.handle.getPosition();
        if (currentPosition.x !== command.position.x ||
            currentPosition.y !== command.position.y) {
          target.handle.setPosition(command.position);
        }
        const currentSize = target.handle.getSize();
        if (!sameSize(currentSize, command.size)) {
          target.handle.setSize(command.size);
        }
      }
      overlay.redraw();
    },
    onPointerUp(event) {
      release(event.pointerId);
    },
    onPointerCancel(event) {
      release(event.pointerId);
    },
    onKeyDown(event) {
      if (event.key !== "Escape") return;
      if (controller.reset()) {
        activeTarget = undefined;
        overlay.redraw();
      }
    },
  });

  return Object.freeze({
    overlay,
    controller,
    remove() {
      controller.reset();
      activeTarget = undefined;
      overlay.setHitRegions([]);
      overlay.remove();
    },
  });
}

export const touchResize = installTouchResize(comfy);
