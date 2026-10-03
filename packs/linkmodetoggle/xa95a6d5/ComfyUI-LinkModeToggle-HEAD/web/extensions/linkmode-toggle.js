// LinkModeToggle — front-end extension for ComfyUI
// Adds: F8/Ctrl+K hotkeys + a small toolbar button that cycles SPLINE/LINEAR/STRAIGHT.

(() => {
  const ORDER = ["SPLINE","LINEAR","STRAIGHT"];
  const KEY   = "LinkModeToggle.mode";

  // Robustly get the LiteGraph canvas object and the DOM <canvas> elements
  const getCanvasObj = () => window.app?.canvas || window.app?.graphcanvas || null;

  // Cycle & persistence
  const setMode = (name) => {
    const c = getCanvasObj();
    if (!c) return false;
    const modes = { STRAIGHT:0, SPLINE:1, LINEAR:2 };

    const ok =
      (typeof c.setLinkRenderMode === "function" && (c.setLinkRenderMode(modes[name]), true)) ||
      ("links_render_mode" in c && (() => {
        const K = c.constructor;
        const KM = {
          STRAIGHT: K?.LINK_RENDER_MODE_STRAIGHT ?? K?.STRAIGHT_LINKS ?? 0,
          SPLINE:   K?.LINK_RENDER_MODE_SPLINE  ?? K?.SPLINE_LINKS   ?? 1,
          LINEAR:   K?.LINK_RENDER_MODE_LINEAR  ?? K?.LINEAR_LINKS   ?? 2,
        };
        c.links_render_mode = KM[name] ?? modes[name];
        c.dirty_canvas = true; c.draw(true, true);
        return true;
      })()) ||
      ("render_curved_links" in c && (() => {
        c.render_curved_links = (name === "SPLINE");
        c.dirty_canvas = true; c.draw(true, true);
        return true;
      })()) ||
      ("render_link_curved" in c && (() => {
        c.render_link_curved = (name === "SPLINE");
        c.redraw?.(true,true); c.draw?.(true,true);
        return true;
      })());

    if (ok) localStorage.setItem(KEY, name);
    updateButtonUI(name, ok);
    return ok;
  };

  const cycle = () => {
    const cur  = localStorage.getItem(KEY) || "SPLINE";
    const idx  = Math.max(0, ORDER.indexOf(cur));
    const next = ORDER[(idx + 1) % ORDER.length];
    setMode(next);
  };

  // Button
  let btn, badge;
  const updateButtonUI = (mode, ok) => {
    if (!btn) return;
    btn.dataset.mode = mode;
    btn.title = `Link Mode: ${mode} (F8 / Ctrl+K to toggle)`;
    if (badge) badge.textContent = mode[0]; // S/L/S
    btn.classList.toggle("lmt-failed", !ok);
  };

    // --- build a Prime/Comfy-styled button like the others in the toolbar ---
    const buildButton = () => {
        if (btn) return btn;

        btn = document.createElement("button");
        // match existing toolbar buttons
        btn.className = [
            "p-button", "p-component", "p-button-icon-only", "p-button-secondary",
            "h-8", "w-8", "bg-interface-panel-surface", "p-0", "hover:bg-button-hover-surface!"
        ].join(" ");
        btn.type = "button";
        btn.setAttribute("aria-label", "Cycle Link Mode (F8 / Ctrl+K)");
        btn.setAttribute("data-pc-name", "button");
        btn.setAttribute("data-p-disabled", "false");
        btn.setAttribute("data-p-severity", "secondary");
        btn.style.borderRadius = "8px";
        btn.style.border = "none";

        // icon (uses lucide class system like other buttons)
        const icon = document.createElement("i");
        // looks like a curve; feel free to change to: lucide--bezier-curve / pen-tool / route
        icon.className = "icon-[lucide--bezier-curve] h-4 w-4";
        btn.appendChild(icon);

        // tiny badge (S/L/…) in the corner so you know current mode at a glance
        badge = document.createElement("span");
        badge.className = "lmt-badge";
        badge.textContent = (localStorage.getItem(KEY) || "SPLINE")[0];
        btn.appendChild(badge);

        btn.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); cycle(); });
        return btn;
    };


    // --- find the bottom-right group and dock the button there ---
    const attachButton = () => {
        const b = buildButton();

        // Find the toolbar group you pasted (bottom-right palette)
        // We anchor off a known child button to be resilient to class churn.
        const group =
            document.querySelector('[data-testid="toggle-link-visibility-button"]')
                ?.closest('span.p-buttongroup[role="group"]')
            || document.querySelector('span.p-buttongroup[role="group"].right-0.bottom-0');

        if (group) {
            // Optional: put a divider before our button for symmetry
            const divider = document.createElement("div");
            divider.className = "h-[27px] w-[1px] self-center bg-node-divider";

            // If we don’t already exist, append divider + button to the group
            if (!group.contains(b)) {
                group.appendChild(divider);
                group.appendChild(b);
            }
            b.classList.remove("lmt-floating", "lmt-bottom-right", "lmt-in-toolbar");
            // We’re in the toolbar now
            return true;
        }

        // Fallback: float at bottom-right (won’t block nodes; z-index is high)
        if (!document.body.contains(b)) document.body.appendChild(b);
        b.classList.add("lmt-floating", "lmt-bottom-right");
        return false;
    };


    // Keep hotkeys the same; just add a MutationObserver so we reattach if UI changes
    const observeUI = () => {
        const obs = new MutationObserver(() => {
            // if button got removed (UI re-render), re-attach
            if (!document.querySelector(".lmt-btn")) attachButton();
        });
        obs.observe(document.body, { childList: true, subtree: true });
        return obs;
    };


   

  // Hotkeys
  const keyHandler = (e) => {
    const ctrlK = e.code === "KeyK" && e.ctrlKey && !e.altKey && !e.shiftKey;
    const f8    = e.code === "F8"    && !e.ctrlKey && !e.altKey && !e.shiftKey;
    if (!(ctrlK || f8)) return;

    const t = e.target;
    const tag = (t && t.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || t?.isContentEditable) return;

    e.preventDefault();
    e.stopPropagation();
    cycle();
  };

  const bindHotkeys = () => {
    const cobj = getCanvasObj();
    const targets = [window, document, document.body, cobj?.canvas, cobj?.bgcanvas]
      .filter(t => t && typeof t.addEventListener === "function");
    targets.forEach(t => t.addEventListener("keydown", keyHandler, { capture: true }));
    console.log("[LinkModeToggle] Hotkeys ready (F8 / Ctrl+K). Bound on:", targets.length, "targets.");
  };

  // Boot sequence with retries until app + canvas are ready
const boot = () => {
    const tryInit = (attempt = 0) => {
        const ready = window.app && getCanvasObj();
        if (!ready) {
            if (attempt < 60) return void setTimeout(() => tryInit(attempt + 1), 250);
            console.warn("[LinkModeToggle] Timed out waiting for ComfyUI app/canvas.");
            return;
        }
        setMode(localStorage.getItem(KEY) || "SPLINE");
        attachButton();
        bindHotkeys();
        observeUI();
    };
    tryInit();
};

  // Use Comfy’s extension API if present
  if (window.app?.registerExtension) {
    app.registerExtension({
      name: "LinkModeToggle",
      setup() { boot(); },
    });
  } else {
    // Older frontends: best-effort boot
    document.addEventListener("DOMContentLoaded", boot);
    boot();
  }
})();


console.log("%c[LinkModeToggle] v0.1.0 loaded","color: #00e6e6;");

