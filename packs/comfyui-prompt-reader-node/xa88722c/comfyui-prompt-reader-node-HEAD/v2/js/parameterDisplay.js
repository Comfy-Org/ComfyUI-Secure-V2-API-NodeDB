import { comfy } from '/comfy/api/v2.js';
import { readout, textPayload } from './utils.js';


comfy.defs.extend('SDParameterGenerator', (builder) => {
  builder.onCreated((node) => {
    readout(node, 'steps_display');
    readout(node, 'aspect_ratio_display');
    const size = node.getSize();
    node.setSize({ width: size.width * 2, height: size.height * 1.2 });
  });
  builder.onExecuted((node, result) => {
    const text = textPayload(result);
    if (text.length < 10) return;
    const aspect = String(text[0]);
    const model = String(text[1]);
    const width = Number(text[2]);
    const height = Number(text[3]);
    const totalSteps = Number(text[4]);
    const start = Number(text[5]);
    const baseSteps = Number(text[6]);
    const ratios = text[8] ?? {};
    const scales = text[9] ?? {};
    const aspectMessage = aspect === 'custom'
      ? `Custom aspect ratio: ${width} x ${height}`
      : `Optimal resolution for ${model} model\nwith aspect ratio ${aspect}: ${width} x ${height}`;
    if (aspect !== 'custom') {
      node.widgets.get('width')?.setValue(width);
      node.widgets.get('height')?.setValue(height);
    }
    const stepMessage = start === 1
      ? `Total steps: ${totalSteps},\nRefiner off`
      : `Total steps: ${totalSteps},\nRefiner start at step: ${baseSteps} (${Math.round(start * 100)}%)`;
    node.widgets.get('steps_display')?.setValue(stepMessage);
    node.widgets.get('aspect_ratio_display')?.setValue(aspectMessage);

    const scaling = Number(scales[model]);
    const options = ['custom', ...Object.entries(ratios).map(([ratio, dims]) => (
      `${ratio} - ${Number(dims[0]) * scaling}x${Number(dims[1]) * scaling}`
    ))];
    const widget = node.widgets.get('aspect_ratio');
    widget?.setOption('values', options);
    if (aspect !== 'custom' && Array.isArray(ratios[aspect])) {
      widget?.setValue(
        `${aspect} - ${Number(ratios[aspect][0]) * scaling}x${Number(ratios[aspect][1]) * scaling}`,
      );
    }
  });
});
