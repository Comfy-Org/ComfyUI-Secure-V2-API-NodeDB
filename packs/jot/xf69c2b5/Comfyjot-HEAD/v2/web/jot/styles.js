const STYLE_ID = "comfyjot-overlay-styles";

export function ensureStyles() {
  if (document.getElementById(STYLE_ID)) {
    return;
  }

  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .comfyjot-root {
      position: absolute;
      inset: 0;
      z-index: 1000;
      pointer-events: none;
    }

    .comfyjot-root[hidden] {
      display: none !important;
    }

    .comfyjot-surface {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      touch-action: none;
      cursor: default;
    }

    .comfyjot-surface.is-editing {
      pointer-events: auto;
      cursor: crosshair;
    }

    .comfyjot-rail {
      position: absolute;
      left: 50%;
      bottom: 1rem;
      transform: translateX(-50%);
      width: max-content;
      max-width: calc(100% - 2rem);
      box-sizing: border-box;
      display: flex;
      flex-wrap: wrap;
      align-items: stretch;
      justify-content: center;
      gap: 0.55rem;
      padding: 0.78rem 0.75rem 0.75rem;
      border-radius: 1.15rem;
      border: 1px solid var(--p-panel-border-color, var(--border-color));
      background: var(--comfy-menu-secondary-bg, var(--bg-color));
      box-shadow: var(--bar-shadow);
      color: var(--fg-color, #f5f7fa);
      pointer-events: auto;
      user-select: none;
    }

    .comfyjot-brand {
      display: grid;
      align-content: center;
      justify-items: center;
      gap: 0.18rem;
      min-width: 5.85rem;
    }

    .comfyjot-brand__label {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      padding: 0.2rem 0 0.24rem;
      font-size: 0.62rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      opacity: 0.6;
      pointer-events: none;
      text-align: center;
      white-space: nowrap;
    }

    .comfyjot-cluster {
      display: grid;
      align-content: center;
      gap: 0.35rem;
      min-height: 3.6rem;
      padding: 0.42rem 0.48rem;
      border-radius: 0.95rem;
      border: 1px solid var(--p-panel-border-color, var(--border-color));
      background: var(--bg-color);
    }

    .comfyjot-pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 1.9rem;
      width: auto;
      min-width: 5.4rem;
      padding: 0 0.55rem;
      border-radius: 0.85rem;
      border: 1px solid var(--p-button-secondary-border-color, var(--p-panel-border-color, var(--border-color)));
      background: var(--p-button-secondary-background, var(--comfy-input-bg, var(--bg-color)));
      color: inherit;
      font: inherit;
      font-size: 0.75rem;
      font-weight: 600;
      cursor: pointer;
      transition: background-color 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
    }

    .comfyjot-pill:hover {
      transform: translateY(-1px);
      background: var(--p-button-secondary-hover-background, var(--comfy-input-bg, var(--bg-color)));
    }

    .comfyjot-pill.is-active {
      background: var(--p-button-primary-background, #4a8cf7);
      color: var(--p-button-primary-color, white);
      border-color: var(--p-button-primary-border-color, transparent);
    }

    .comfyjot-pill--ink {
      width: 100%;
      min-width: 5.85rem;
      align-self: stretch;
    }

    .comfyjot-grid {
      display: grid;
      gap: 0.4rem;
    }

    .comfyjot-grid--tools {
      grid-template-columns: 1fr;
      grid-template-rows: repeat(2, minmax(0, 1fr));
    }

    .comfyjot-grid--actions {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      grid-template-rows: repeat(2, minmax(0, 1fr));
    }

    .comfyjot-grid--actions .comfyjot-icon-button,
    .comfyjot-grid--tools .comfyjot-icon-button {
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .comfyjot-icon-button {
      width: 2.25rem;
      min-width: 2.25rem;
      height: 2.25rem;
      min-height: 2.25rem;
      border-radius: 0.85rem;
      border: 1px solid var(--p-button-secondary-border-color, var(--p-panel-border-color, var(--border-color)));
      background: var(--p-button-secondary-background, var(--comfy-input-bg, var(--bg-color)));
      color: inherit;
      cursor: pointer;
      transition: background-color 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
    }

    .comfyjot-icon-button:hover {
      transform: translateY(-1px);
      background: var(--p-button-secondary-hover-background, var(--comfy-input-bg, var(--bg-color)));
    }

    .comfyjot-icon-button.is-active {
      background: var(--p-button-primary-background, #4a8cf7);
      color: var(--p-button-primary-color, white);
      border-color: var(--p-button-primary-border-color, transparent);
    }

    .comfyjot-icon-button--redo i {
      display: inline-block;
      transform: scaleX(-1);
    }

    .comfyjot-icon-button:disabled {
      opacity: 0.45;
      cursor: default;
      transform: none;
    }

    .comfyjot-size {
      display: grid;
      gap: 0.4rem;
      min-width: 11.25rem;
    }

    .comfyjot-size__label {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.4rem;
      font-size: 0.72rem;
      opacity: 0.82;
    }

    .comfyjot-size__slider {
      width: 100%;
      min-height: 4rem;
      position: relative;
      border-radius: 0.95rem;
      border: 1px solid var(--p-panel-border-color, var(--border-color));
      background: var(--comfy-input-bg, var(--bg-color));
      overflow: hidden;
      --comfyjot-brush-ratio: 0.2;
      --comfyjot-brush-dot-size: 12px;
    }

    .comfyjot-size__slider::before {
      content: "";
      position: absolute;
      left: 0.9rem;
      right: 0.9rem;
      top: 50%;
      height: 0.24rem;
      border-radius: 999px;
      background: color-mix(in srgb, var(--fg-color) 16%, transparent);
      transform: translateY(-50%);
      opacity: 1;
      pointer-events: none;
    }

    .comfyjot-size__input {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      margin: 0;
      padding: 0;
      appearance: none;
      -webkit-appearance: none;
      background: transparent;
      cursor: pointer;
      z-index: 2;
    }

    .comfyjot-size__input::-webkit-slider-runnable-track {
      height: 100%;
      background: transparent;
      border: 0;
    }

    .comfyjot-size__input::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 1px;
      height: 100%;
      border: 0;
      background: transparent;
      box-shadow: none;
    }

    .comfyjot-size__input::-moz-range-track {
      height: 100%;
      background: transparent;
      border: 0;
    }

    .comfyjot-size__input::-moz-range-thumb {
      width: 1px;
      height: 100%;
      border: 0;
      border-radius: 0;
      background: transparent;
      box-shadow: none;
    }

    .comfyjot-size__dot {
      position: absolute;
      left: calc(0.95rem + (100% - 1.95rem) * var(--comfyjot-brush-ratio));
      top: 50%;
      transform: translate(-50%, -50%);
      border-radius: 999px;
      background: currentColor;
      box-shadow: 0 0 0 1px color-mix(in srgb, currentColor 35%, transparent);
      z-index: 1;
      pointer-events: none;
      transition: width 0.15s ease, height 0.15s ease, left 0.12s ease, top 0.12s ease;
    }

    .comfyjot-size__slider:hover {
      border-color: color-mix(in srgb, var(--p-button-primary-background, var(--p-primary-color)) 38%, var(--p-panel-border-color, var(--border-color)));
    }

    .comfyjot-size__slider:focus-within {
      border-color: var(--p-button-primary-background, var(--p-primary-color));
      box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--p-button-primary-background, var(--p-primary-color)) 45%, transparent);
    }

    .comfyjot-color {
      display: grid;
      gap: 0.45rem;
      min-width: 13rem;
    }

    .comfyjot-color__picker {
      width: 100%;
      height: 2rem;
      padding: 0;
      display: block;
      appearance: none;
      -webkit-appearance: none;
      border: 1px solid color-mix(in srgb, var(--p-panel-border-color, rgba(255, 255, 255, 0.12)) 75%, transparent);
      border-radius: 0.85rem;
      background: transparent;
      overflow: hidden;
      cursor: pointer;
    }

    .comfyjot-color__picker::-webkit-color-swatch-wrapper {
      padding: 0;
    }

    .comfyjot-color__picker::-webkit-color-swatch {
      border: 0;
      border-radius: 0.75rem;
    }

    .comfyjot-color__picker::-moz-color-swatch {
      border: 0;
      border-radius: 0.75rem;
    }

    .comfyjot-swatch-grid {
      display: grid;
      grid-template-columns: repeat(8, minmax(0, 1fr));
      gap: 0.35rem;
    }

    .comfyjot-swatch {
      width: 1.1rem;
      min-width: 1.1rem;
      aspect-ratio: 1;
      border-radius: 999px;
      border: 2px solid transparent;
      box-shadow:
        0 0 0 1px color-mix(in srgb, var(--fg-color, #f5f7fa) 12%, transparent),
        inset 0 0 0 1px color-mix(in srgb, black 10%, transparent);
      cursor: pointer;
      transition: transform 0.18s ease, border-color 0.18s ease;
    }

    .comfyjot-swatch:hover {
      transform: translateY(-1px) scale(1.03);
    }

    .comfyjot-swatch.is-active {
      border-color: var(--fg-color, #f5f7fa);
    }

    .comfyjot-divider {
      width: 1px;
      min-height: 3.6rem;
      background: color-mix(in srgb, var(--p-panel-border-color, rgba(255, 255, 255, 0.12)) 80%, transparent);
    }

    .comfyjot-sidebar-launcher .comfyjot-pill {
      width: 100%;
    }

    .comfyjot-sidebar-launcher {
      display: grid;
      gap: 0.85rem;
      padding: 1rem;
      color: var(--fg-color, #f5f7fa);
    }

    .comfyjot-sidebar-launcher__card {
      display: grid;
      gap: 0.55rem;
      padding: 0.9rem;
      border-radius: 0.95rem;
      border: 1px solid var(--p-panel-border-color, var(--border-color));
      background: var(--bg-color);
      line-height: 1.5;
    }

    @media (max-width: 900px) {
      .comfyjot-rail {
        max-width: calc(100% - 1rem);
      }

      .comfyjot-divider {
        width: 100%;
        min-height: 1px;
        height: 1px;
      }

      .comfyjot-color {
        min-width: min(100%, 18rem);
      }
    }

    @media (max-width: 640px) {
      .comfyjot-rail {
        bottom: 0.65rem;
        gap: 0.45rem;
        padding: 0.7rem 0.65rem 0.65rem;
      }

      .comfyjot-brand,
      .comfyjot-cluster,
      .comfyjot-pill--ink {
        width: 100%;
      }

      .comfyjot-color,
      .comfyjot-size {
        min-width: 100%;
      }

      .comfyjot-swatch-grid {
        grid-template-columns: repeat(4, minmax(0, 1fr));
      }
    }
  `;
  document.head.appendChild(style);
}
