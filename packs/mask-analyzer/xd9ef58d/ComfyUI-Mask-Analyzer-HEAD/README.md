# ComfyUI Mask Analyzer

Custom ComfyUI nodes for analyzing a mask's structural complexity and routing downstream logic between direct, simplified, and overlay strategies.

## What This Does

This repository provides two nodes:

- `Mask Analyze`: inspects a mask, counts connected components, measures aspect ratio, estimates complexity, and returns a recommended strategy.
- `Mask Strategy Switch`: converts the returned strategy string into a concrete integer selector you can feed into your own workflow logic.

The goal is to make mask-dependent workflows easier to automate when you want different behavior for simple masks, cluttered masks, or wide / overlay-like masks.

## Installation

### Option 1: Manual Git Install

Clone this repository into your ComfyUI `custom_nodes` directory:

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/imk-design/ComfyUI-Mask-Analyzer.git
```

Restart ComfyUI after cloning.

### Option 2: ComfyUI Manager

Once the repository is added to ComfyUI Manager / Registry, install it there the same way as any other custom node.

## Where to Place It

The repository folder should live directly inside:

```text
ComfyUI/custom_nodes/ComfyUI-Mask-Analyzer
```

ComfyUI should then detect the package through the repository root `__init__.py`.

## Dependencies

No extra installation step is required for the current version.

- `numpy` and `torch` are already part of a normal ComfyUI environment.
- `opencv-python` is optional. If OpenCV is available, the node uses it for connected-component analysis.
- If OpenCV is not installed, the node falls back to a NumPy implementation automatically.

## Usage

1. Add `Mask Analyze` after any node that produces a `MASK`.
2. Tune the thresholds if needed:
   - `min_component_area` filters out tiny fragments.
   - `small_component_area` defines what counts as a small component.
   - `direct_max_components`, `overlay_min_components`, `wide_aspect_overlay`, and `small_ratio_overlay` control strategy selection.
3. Use the returned `strategy` output directly in text/debug logic, or feed it into `Mask Strategy Switch`.
4. Use the switch node's integer output to drive your own downstream branches, conditioning, or parameter toggles.

## Node Reference

### Mask Analyze

**Inputs**

- `mask` (`MASK`): source mask to inspect.
- `threshold` (`FLOAT`): binarization threshold applied before analysis.
- `min_component_area` (`INT`): ignores connected components smaller than this area.
- `small_component_area` (`INT`): components at or below this area count as "small".
- `direct_max_components` (`INT`): upper bound for preferring the `direct` strategy.
- `overlay_min_components` (`INT`): lower bound for forcing the `overlay` strategy.
- `wide_aspect_overlay` (`FLOAT`): aspect ratio threshold for forcing the `overlay` strategy.
- `small_ratio_overlay` (`FLOAT`): small-component ratio threshold for forcing the `overlay` strategy.

**Outputs**

- `component_count` (`INT`)
- `small_component_count` (`INT`)
- `small_component_ratio` (`FLOAT`)
- `aspect_ratio` (`FLOAT`)
- `complexity_score` (`FLOAT`)
- `strategy` (`STRING`): one of `direct`, `simplified`, or `overlay`
- `use_overlay_mode` (`BOOLEAN`)

### Mask Strategy Switch

**Inputs**

- `strategy` (`STRING`)
- `direct_value` (`INT`)
- `simplified_value` (`INT`)
- `overlay_value` (`INT`)

**Outputs**

- `selected_value` (`INT`)

Use this node when you want a simple numeric selector instead of string-based branching.

## Minimal Example

Typical pattern:

```text
MASK source -> Mask Analyze -> strategy -> Mask Strategy Switch -> downstream selector
```

Example interpretation:

- `direct`: use the original mask path
- `simplified`: use a lighter cleanup / simplification path
- `overlay`: switch to an overlay-oriented path for many small or wide components

## Notes

- Category in ComfyUI: `Mask Tools`
- Node display names: `Mask Analyze`, `Mask Strategy Switch`
- The node does not write files, use hardcoded local paths, or require external services
