/** Pack-owned Label layout and drawing, retained from pinned rgthree 6b76ee6. */
export const LABEL_DEFAULTS = Object.freeze({
  fontSize: 12,
  fontFamily: 'Arial',
  fontColor: '#ffffff',
  textAlign: 'left',
  backgroundColor: 'transparent',
  padding: 0,
  borderRadius: 0,
  angle: 0,
});

export function layoutLabel(title, properties, context) {
  const fontSize = properties.fontSize;
  const font = `${Math.max(fontSize || 0, 1)}px ${properties.fontFamily ?? 'Arial'}`;
  context.font = font;
  context.textBaseline = 'top';
  const padding = Number(properties.padding) ?? 0;
  const lines = (title ?? '').replace(/\\n/g, '\n').replace(/\n*$/, '').split('\n');
  const widths = lines.map((line) => context.measureText(line).width);
  const width = Math.max(...widths) + padding * 2;
  const height = fontSize * lines.length + padding * 2;
  const angle = (parseInt(String(properties.angle ?? 0)) || 0) * Math.PI / 180;
  const textAlign = ['center', 'right'].includes(properties.textAlign) ? properties.textAlign : 'left';
  const textX = textAlign === 'center' ? width / 2 : textAlign === 'right' ? width - padding : padding;
  context.textAlign = textAlign;
  // Include actual glyph overhang as well as the background rectangle. These
  // are drawing bounds only: saved size and hit testing stay unrotated.
  let left = Math.min(0, width), top = Math.min(0, height);
  let right = Math.max(0, width), bottom = Math.max(0, height);
  lines.forEach((line, index) => {
    const m = context.measureText(line || ' ');
    const y = padding + index * fontSize;
    left = Math.min(left, textX - (m.actualBoundingBoxLeft ?? 0));
    right = Math.max(right, textX + (m.actualBoundingBoxRight ?? m.width));
    top = Math.min(top, y - (m.actualBoundingBoxAscent ?? 0));
    bottom = Math.max(bottom, y + (m.actualBoundingBoxDescent ?? fontSize));
  });
  const cx = width / 2, cy = height / 2;
  const points = [[left, top], [right, top], [right, bottom], [left, bottom]].map(([x, y]) => [
    cx + (x - cx) * Math.cos(angle) - (y - cy) * Math.sin(angle),
    cy + (x - cx) * Math.sin(angle) + (y - cy) * Math.cos(angle),
  ]);
  const x = Math.floor(Math.min(...points.map((p) => p[0]))) - 2;
  const y = Math.floor(Math.min(...points.map((p) => p[1]))) - 2;
  const bounds = {
    x, y,
    width: Math.max(1, Math.ceil(Math.max(...points.map((p) => p[0]))) - x + 2),
    height: Math.max(1, Math.ceil(Math.max(...points.map((p) => p[1]))) - y + 2),
  };
  if (![width, height, x, y, bounds.width, bounds.height].every(Number.isFinite)) {
    throw new RangeError('Label properties must produce finite geometry');
  }
  return { width, height, font, fontSize, padding, lines, angle, textAlign, textX, bounds };
}

export function drawLabel(context, layout, properties) {
  context.save();
  context.font = layout.font;
  if (layout.angle) {
    context.translate(layout.width / 2, layout.height / 2);
    context.rotate(layout.angle);
    context.translate(-layout.width / 2, -layout.height / 2);
  }
  const backgroundColor = properties.backgroundColor || '';
  if (backgroundColor) {
    context.beginPath();
    context.roundRect(0, 0, layout.width, layout.height, [Number(properties.borderRadius) || 0]);
    context.fillStyle = backgroundColor;
    context.fill();
  }
  context.textAlign = 'left';
  if (layout.textAlign !== 'left') context.textAlign = layout.textAlign;
  context.textBaseline = 'top';
  context.fillStyle = properties.fontColor || '#ffffff';
  let currentY = layout.padding;
  for (const line of layout.lines) {
    context.fillText(line || ' ', layout.textX, currentY);
    currentY += layout.fontSize;
  }
  context.restore();
}
