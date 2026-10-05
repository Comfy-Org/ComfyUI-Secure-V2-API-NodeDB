import { app } from "/scripts/app.js";

// ── Live Preview ──────────────────────────────────────────────────────────
// Intercepts ComfyUI's websocket preview frames and displays them in a large
// draggable/resizable overlay window.

(function () {
    const STORAGE_KEY = 'LivePreview.geometry';
    const MIN_W = 200, MIN_H = 200;

    let overlayEl = null;
    let canvasEl = null;
    let ctx = null;
    let headerEl = null;
    let toggleBtn = null;
    let isVisible = false;
    let isDragging = false;
    let isResizing = false;
    let dragOffX = 0, dragOffY = 0;
    let resizeStartX = 0, resizeStartY = 0;
    let resizeStartW = 0, resizeStartH = 0;
    let previewCount = 0;
    let fpsInterval = null;
    let fpsCount = 0;
    let userHidden = false;   // true when the user explicitly closed the overlay

    // ── Geometry: clamping + persistence ───────────────────────────────────────
    // Holds the overlay fully inside the viewport on all four sides. When it is
    // larger than the viewport (Math.max floors the maximum at 0) it pins to the
    // top-left and overflows off the far edge — containment isn't possible then.
    function clampPosition(left, top, w, h) {
        const maxLeft = Math.max(0, window.innerWidth - w);
        const maxTop = Math.max(0, window.innerHeight - h);
        return {
            left: Math.min(Math.max(left, 0), maxLeft),
            top: Math.min(Math.max(top, 0), maxTop),
        };
    }

    function saveGeometry() {
        if (!overlayEl) return;
        const r = overlayEl.getBoundingClientRect();
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                left: r.left, top: r.top, width: r.width, height: r.height,
            }));
        } catch (e) {
            // Quota exceeded or storage disabled (private mode) — position just
            // won't persist; not worth interrupting the user over.
        }
    }

    function loadGeometry() {
        let g;
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return null;
            g = JSON.parse(raw);
        } catch (e) {
            return null;
        }
        const vals = [g?.left, g?.top, g?.width, g?.height];
        if (!vals.every(v => typeof v === 'number' && isFinite(v))) return null;
        return g;
    }

    // Applies stored geometry, or re-clamps the current geometry when `g` is
    // omitted (e.g. after the viewport shrank).
    function applyGeometry(g) {
        if (!overlayEl) return;
        const r = overlayEl.getBoundingClientRect();
        // Cap to the viewport as well as the floor: geometry stored on a larger
        // monitor could otherwise restore a window whose resize grip is off-screen.
        const clampSize = (v, min, limit) => Math.min(Math.max(v, min), Math.max(min, limit));
        const w = clampSize(g ? g.width : r.width, MIN_W, window.innerWidth);
        const h = clampSize(g ? g.height : r.height, MIN_H, window.innerHeight);
        const pos = clampPosition(g ? g.left : r.left, g ? g.top : r.top, w, h);
        overlayEl.style.right = 'auto';
        overlayEl.style.left = pos.left + 'px';
        overlayEl.style.top = pos.top + 'px';
        overlayEl.style.width = w + 'px';
        overlayEl.style.height = h + 'px';
    }

    // ── Build overlay ──────────────────────────────────────────────────────────
    function buildOverlay() {
        if (overlayEl) return;

        // ── Floating toggle button (always visible) ────────────────────────────
        toggleBtn = document.createElement('button');
        toggleBtn.textContent = '⚡';
        toggleBtn.title = 'Toggle Live Preview';
        Object.assign(toggleBtn.style, {
            position: 'fixed',
            bottom: '60px',
            right: '16px',
            zIndex: '10000',
            width: '38px',
            height: '38px',
            borderRadius: '50%',
            background: '#16213e',
            color: '#7c6aff',
            border: '2px solid #7c6aff',
            fontSize: '16px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 2px 12px rgba(0,0,0,0.6)',
            transition: 'background 0.15s, color 0.15s',
            padding: '0',
            lineHeight: '1',
        });
        toggleBtn.addEventListener('mouseenter', () => {
            toggleBtn.style.background = '#252550';
        });
        toggleBtn.addEventListener('mouseleave', () => {
            toggleBtn.style.background = isVisible ? '#7c6aff' : '#16213e';
        });
        toggleBtn.addEventListener('click', () => {
            if (isVisible) hideOverlay();
            else showOverlay();
        });
        document.body.appendChild(toggleBtn);

        // ── Main overlay window ────────────────────────────────────────────────
        overlayEl = document.createElement('div');
        Object.assign(overlayEl.style, {
            position: 'fixed',
            top: '60px',
            right: '60px',
            width: '520px',
            height: '560px',
            background: '#0d0d18',
            border: '2px solid #7c6aff',
            borderRadius: '10px',
            boxShadow: '0 8px 40px rgba(0,0,0,0.85)',
            zIndex: '9999',
            display: 'none',
            flexDirection: 'column',
            overflow: 'hidden',
            minWidth: '200px',
            minHeight: '200px',
            userSelect: 'none',
        });

        // Header bar
        headerEl = document.createElement('div');
        Object.assign(headerEl.style, {
            background: '#16213e',
            padding: '7px 10px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'grab',
            flexShrink: '0',
            borderBottom: '1px solid #252540',
        });

        const dot = document.createElement('div');
        dot.id = 'live-preview-dot';
        Object.assign(dot.style, {
            width: '8px', height: '8px',
            borderRadius: '50%',
            background: '#444',
            flexShrink: '0',
            transition: 'background 0.3s, box-shadow 0.3s',
        });

        const title = document.createElement('span');
        title.textContent = '⚡ Live Preview';
        Object.assign(title.style, {
            color: '#7c6aff',
            fontSize: '12px',
            fontWeight: '700',
            fontFamily: 'sans-serif',
            flex: '1',
        });

        const stepLabel = document.createElement('span');
        stepLabel.id = 'live-preview-step';
        Object.assign(stepLabel.style, {
            color: '#00d4aa',
            fontSize: '10px',
            fontFamily: 'monospace',
            minWidth: '50px',
            textAlign: 'right',
        });

        const fpsLabel = document.createElement('span');
        fpsLabel.id = 'live-preview-fps';
        Object.assign(fpsLabel.style, {
            color: '#555570',
            fontSize: '10px',
            fontFamily: 'monospace',
            minWidth: '40px',
            textAlign: 'right',
        });

        const closeBtn = document.createElement('button');
        closeBtn.textContent = '✕';
        Object.assign(closeBtn.style, {
            background: 'none', border: 'none',
            color: '#555570', cursor: 'pointer',
            fontSize: '14px', padding: '0 2px',
            lineHeight: '1', marginLeft: '4px',
        });
        closeBtn.addEventListener('mouseenter', () => closeBtn.style.color = '#ff5555');
        closeBtn.addEventListener('mouseleave', () => closeBtn.style.color = '#555570');
        closeBtn.addEventListener('click', hideOverlay);

        headerEl.appendChild(dot);
        headerEl.appendChild(title);
        headerEl.appendChild(stepLabel);
        headerEl.appendChild(fpsLabel);
        headerEl.appendChild(closeBtn);

        // Canvas
        canvasEl = document.createElement('canvas');
        Object.assign(canvasEl.style, {
            flex: '1',
            width: '100%',
            display: 'block',
            background: '#080810',
        });
        ctx = canvasEl.getContext('2d');

        // Resize grip
        const grip = document.createElement('div');
        Object.assign(grip.style, {
            position: 'absolute',
            bottom: '0', right: '0',
            width: '18px', height: '18px',
            cursor: 'se-resize',
            background: 'linear-gradient(135deg, transparent 50%, #7c6aff80 50%)',
            borderBottomRightRadius: '8px',
        });

        overlayEl.appendChild(headerEl);
        overlayEl.appendChild(canvasEl);
        overlayEl.appendChild(grip);
        document.body.appendChild(overlayEl);

        // ── Drag / resize ─────────────────────────────────────────────────────
        // The move/up listeners live on `document` only for the duration of a
        // gesture, so they aren't invoked on every mouse move across the page.
        function beginGesture() {
            document.addEventListener('mousemove', onPointerMove);
            document.addEventListener('mouseup', onPointerUp);
        }

        function onPointerMove(e) {
            if (isDragging) {
                const pos = clampPosition(
                    e.clientX - dragOffX, e.clientY - dragOffY,
                    overlayEl.offsetWidth, overlayEl.offsetHeight,
                );
                overlayEl.style.left = pos.left + 'px';
                overlayEl.style.top = pos.top + 'px';
            }
            if (isResizing) {
                const rect = overlayEl.getBoundingClientRect();
                // Cap growth so the resize grip stays reachable on-screen.
                const maxW = Math.max(MIN_W, window.innerWidth - rect.left);
                const maxH = Math.max(MIN_H, window.innerHeight - rect.top);
                const w = resizeStartW + (e.clientX - resizeStartX);
                const h = resizeStartH + (e.clientY - resizeStartY);
                overlayEl.style.width = Math.min(Math.max(MIN_W, w), maxW) + 'px';
                overlayEl.style.height = Math.min(Math.max(MIN_H, h), maxH) + 'px';
            }
        }

        function onPointerUp() {
            if (!isDragging && !isResizing) return;
            isDragging = false;
            isResizing = false;
            headerEl.style.cursor = 'grab';
            document.removeEventListener('mousemove', onPointerMove);
            document.removeEventListener('mouseup', onPointerUp);
            saveGeometry();
        }

        headerEl.addEventListener('mousedown', (e) => {
            if (e.target === closeBtn) return;
            const rect = overlayEl.getBoundingClientRect();
            isDragging = true;
            headerEl.style.cursor = 'grabbing';
            dragOffX = e.clientX - rect.left;
            dragOffY = e.clientY - rect.top;
            overlayEl.style.right = 'auto';
            beginGesture();
            e.preventDefault();
        });

        grip.addEventListener('mousedown', (e) => {
            const rect = overlayEl.getBoundingClientRect();
            // Re-anchor to left/top first: while anchored by `right`, growing the
            // width expands the window leftwards and the grip slides out from
            // under the cursor.
            overlayEl.style.right = 'auto';
            overlayEl.style.left = rect.left + 'px';
            overlayEl.style.top = rect.top + 'px';
            isResizing = true;
            resizeStartX = e.clientX;
            resizeStartY = e.clientY;
            resizeStartW = overlayEl.offsetWidth;
            resizeStartH = overlayEl.offsetHeight;
            beginGesture();
            e.preventDefault();
            e.stopPropagation();
        });

        // Restore the last position/size, and keep the window reachable if the
        // browser window is later made smaller. With nothing stored, the CSS
        // defaults above stand (they can't be measured while display:none).
        const stored = loadGeometry();
        if (stored) applyGeometry(stored);

        window.addEventListener('resize', () => {
            if (!isVisible) return;
            applyGeometry();
            saveGeometry();
        });
    }

    // ── Show / hide ────────────────────────────────────────────────────────────
    function showOverlay() {
        buildOverlay();
        overlayEl.style.display = 'flex';
        // Now that it has layout, re-clamp: the viewport may have changed size
        // (or monitors) since the geometry was stored.
        applyGeometry();
        isVisible = true;
        userHidden = false;
        toggleBtn.style.background = '#7c6aff';
        toggleBtn.style.color = '#fff';
        toggleBtn.title = 'Hide Live Preview';
    }

    function hideOverlay() {
        if (!overlayEl) return;
        overlayEl.style.display = 'none';
        isVisible = false;
        userHidden = true;
        if (toggleBtn) {
            toggleBtn.style.background = '#16213e';
            toggleBtn.style.color = '#7c6aff';
            toggleBtn.title = 'Show Live Preview';
        }
    }

    function setDot(state) {
        const dot = document.getElementById('live-preview-dot');
        if (!dot) return;
        if (state === 'active') {
            dot.style.background = '#00d4aa';
            dot.style.boxShadow = '0 0 6px #00d4aa';
        } else if (state === 'idle') {
            dot.style.background = '#7c6aff';
            dot.style.boxShadow = '0 0 6px #7c6aff88';
        } else if (state === 'error') {
            dot.style.background = '#ff5555';
            dot.style.boxShadow = '0 0 6px #ff555588';
        } else {
            dot.style.background = '#444';
            dot.style.boxShadow = 'none';
        }
    }

    function startFpsCounter() {
        if (fpsInterval) clearInterval(fpsInterval);
        fpsCount = 0;
        fpsInterval = setInterval(() => {
            const fps = fpsCount;
            fpsCount = 0;
            const el = document.getElementById('live-preview-fps');
            if (el) el.textContent = fps > 0 ? fps + ' fps' : '';
        }, 1000);
    }

    // ── Draw a preview frame ───────────────────────────────────────────────────
    function drawFrame(blob) {
        const url = URL.createObjectURL(blob);
        const img = new Image();
        img.onload = () => {
            const cw = canvasEl.offsetWidth  || 512;
            const ch = canvasEl.offsetHeight || 512;
            // Only reset canvas dimensions when they actually changed; resetting
            // every frame causes a blank flash if the user resizes mid-generation.
            if (canvasEl.width !== cw || canvasEl.height !== ch) {
                canvasEl.width  = cw;
                canvasEl.height = ch;
            } else {
                ctx.clearRect(0, 0, cw, ch);
            }
            const scale = Math.min(cw / img.width, ch / img.height);
            const dw = img.width  * scale;
            const dh = img.height * scale;
            ctx.drawImage(img, (cw - dw) / 2, (ch - dh) / 2, dw, dh);
            URL.revokeObjectURL(url);
            previewCount++;
            fpsCount++;
            const stepEl = document.getElementById('live-preview-step');
            if (stepEl) stepEl.textContent = 'step ' + previewCount;
        };
        img.src = url;
    }

    // ── Check if Live Preview node is present ──────────────────────────────────
    function hasLivePreviewNode() {
        if (!app.graph) return false;
        return (app.graph._nodes || []).some(n => n.type === 'LivePreview');
    }

    // ── Hook into ComfyUI websocket events ─────────────────────────────────────
    function hookWebSocket() {
        if (!app.api) { setTimeout(hookWebSocket, 500); return; }

        app.api.addEventListener('b_preview', (event) => {
            if (!hasLivePreviewNode()) return;
            const blob = event.detail;
            if (!blob) return;
            if (!isVisible && !userHidden) showOverlay();
            drawFrame(blob);
        });

        app.api.addEventListener('execution_start', () => {
            if (!hasLivePreviewNode()) return;
            previewCount = 0;
            fpsCount = 0;
            if (!isVisible && !userHidden) showOverlay();
            setDot('active');
            startFpsCounter();
            const stepEl = document.getElementById('live-preview-step');
            if (stepEl) stepEl.textContent = '';
            const fpsEl = document.getElementById('live-preview-fps');
            if (fpsEl) fpsEl.textContent = '';
        });

        app.api.addEventListener('status', (event) => {
            const q = event.detail?.exec_info?.queue_remaining ?? -1;
            if (q === 0) {
                setDot('idle');
                const fpsEl = document.getElementById('live-preview-fps');
                if (fpsEl) fpsEl.textContent = '';
                if (fpsInterval) { clearInterval(fpsInterval); fpsInterval = null; }
            }
        });

        app.api.addEventListener('execution_error', () => {
            setDot('error');
            if (fpsInterval) { clearInterval(fpsInterval); fpsInterval = null; }
        });

        console.log('[LivePreview] Ready');
    }

    // ── Register ───────────────────────────────────────────────────────────────
    app.registerExtension({
        name: 'LivePreview',
        async setup() {
            // Build the floating toggle button immediately on load
            buildOverlay();
            hookWebSocket();
        },
        nodeCreated(_node) {
            // overlay is already built in setup(); nothing extra needed here
        },
    });
})();
