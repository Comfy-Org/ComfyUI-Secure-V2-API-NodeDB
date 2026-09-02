import { comfy } from '/comfy/api/v2.js';

// code based on mtb nodes by Mel Massadian https://github.com/melMass/comfy_mtb/
export const loadScript = (
  FILE_URL,
  async = true,
  type = 'text/javascript',
) => {
  return new Promise((resolve, reject) => {
    try {
      // Check if the script already exists
      const existingScript = document.querySelector(`script[src="${FILE_URL}"]`)
      if (existingScript) {
        resolve({ status: true, message: 'Script already loaded' })
        return
      }

      const scriptEle = document.createElement('script')
      scriptEle.type = type
      scriptEle.async = async
      scriptEle.src = FILE_URL

      scriptEle.addEventListener('load', (ev) => {
        resolve({ status: true })
      })

      scriptEle.addEventListener('error', (ev) => {
        reject({
          status: false,
          message: `Failed to load the script ${FILE_URL}`,
        })
      })

      document.body.appendChild(scriptEle)
    } catch (error) {
      reject(error)
    }
  })
}

// LIMITATION: the popup rendered markdown with app.extensionManager.renderMarkdownToHtml
// when the host had it and fell back to this bundled marked/DOMPurify pair when it did
// not. The host renderer lives on an internal store, so the fallback becomes the only
// path: the pack keeps its own complete implementation, which is what it shipped before
// the host had one. Costs two script loads that were conditional, and the popup's
// markdown dialect and sanitiser are now the pack's rather than following core's.
loadScript('kjweb_async/marked.min.js').catch((e) => {
  console.error(e)
})
loadScript('kjweb_async/purify.min.js').catch((e) => {
  console.error(e)
})

const categories = ["KJNodes", "SUPIR", "VoiceCraft", "Marigold", "IC-Light", "WanVideoWrapper"];

function isHelpPopupEnabled() {
  return comfy.settings.get("KJNodes.helpPopup") !== false;
}

comfy.defs.extend({ category: new RegExp(`^(${categories.join('|')})`) }, (b) => {
  if (!isHelpPopupEnabled()) return;
  const description = b.def.description;
  if (!description) return;

  b.onCreated((node) => {
    node.addBadge({
      text: '?',
      color: 'orange',
      onClick: () => {
        if (popupState.has(node.id)) {
          closeNodePopup(node.id)
        } else {
          openNodePopup(node.id, description)
        }
      },
    });
  });
  b.onRemoved((node) => closeNodePopup(node.id));
});

const create_documentation_stylesheet = () => {
    const tag = 'kj-documentation-stylesheet'

    let styleTag = document.getElementById(tag)

    if (!styleTag) {
      styleTag = document.createElement('style')
      styleTag.type = 'text/css'
      styleTag.id = tag
      styleTag.innerHTML = `
      .kj-documentation-popup {
        background: var(--comfy-menu-bg);
        position: absolute;
        color: var(--fg-color);
        font: 12px monospace;
        line-height: 1.5em;
        padding: 10px;
        border-radius: 10px;
        border-style: solid;
        border-width: medium;
        border-color: var(--border-color);
        z-index: 5;
        overflow: hidden;
       }
       .content-wrapper {
        overflow: auto;
        max-height: 100%;
        /* Scrollbar styling for Chrome */
        &::-webkit-scrollbar {
           width: 6px;
        }
        &::-webkit-scrollbar-track {
           background: var(--bg-color);
        }
        &::-webkit-scrollbar-thumb {
           background-color: var(--fg-color);
           border-radius: 6px;
           border: 3px solid var(--bg-color);
        }

        /* Scrollbar styling for Firefox */
        scrollbar-width: thin;
        scrollbar-color: var(--fg-color) var(--bg-color);
        a {
          color: yellow;
        }
        a:visited {
          color: orange;
        }
        a:hover {
          color: red;
        }
       }
        `
      document.head.appendChild(styleTag)
    }
  }

/**
 * Creates the documentation popup DOM and wires up resize/close interactions.
 * Returns { docElement, contentWrapper }.
 * @param {string} description - Markdown description text
 * @param {AbortSignal} signal - Signal to clean up event listeners
 * @param {() => void} onClose - Called when the close button is clicked
 */
function createDocPopup(description, signal, onClose) {
  create_documentation_stylesheet()

  const docElement = document.createElement('div')
  const contentWrapper = document.createElement('div')
  docElement.appendChild(contentWrapper)

  contentWrapper.classList.add('content-wrapper')
  docElement.classList.add('kj-documentation-popup')
  if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
    contentWrapper.innerHTML = DOMPurify.sanitize(marked.parse(description))
  } else {
    // Fallback: convert markdown links to <a> tags, auto-link bare URLs, preserve line breaks
    const escaped = description
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
      .replace(/(^|[^"'])(https?:\/\/[^\s<]+)/g, '$1<a href="$2" target="_blank">$2</a>')
      .replace(/\n/g, '<br>')
    contentWrapper.innerHTML = escaped
  }

  // resize handle
  const resizeHandle = document.createElement('div')
  resizeHandle.style.width = '0'
  resizeHandle.style.height = '0'
  resizeHandle.style.position = 'absolute'
  resizeHandle.style.bottom = '0'
  resizeHandle.style.right = '0'
  resizeHandle.style.cursor = 'se-resize'
  const borderColor = getComputedStyle(document.documentElement).getPropertyValue('--border-color').trim()
  resizeHandle.style.borderTop = '10px solid transparent'
  resizeHandle.style.borderLeft = '10px solid transparent'
  resizeHandle.style.borderBottom = `10px solid ${borderColor}`
  resizeHandle.style.borderRight = `10px solid ${borderColor}`
  docElement.appendChild(resizeHandle)

  let isResizing = false
  let startX, startY, startWidth, startHeight
  resizeHandle.addEventListener('mousedown', (e) => {
    e.preventDefault()
    e.stopPropagation()
    isResizing = true
    startX = e.clientX
    startY = e.clientY
    startWidth = parseInt(document.defaultView.getComputedStyle(docElement).width, 10)
    startHeight = parseInt(document.defaultView.getComputedStyle(docElement).height, 10)
  }, { signal })

  document.addEventListener('mousemove', (e) => {
    if (!isResizing) return
    const newWidth = startWidth + (e.clientX - startX)
    const newHeight = startHeight + (e.clientY - startY)
    docElement.style.width = `${newWidth}px`
    docElement.style.height = `${newHeight}px`
  }, { signal })

  document.addEventListener('mouseup', () => {
    isResizing = false
  }, { signal })

  // close button
  const closeButton = document.createElement('div')
  closeButton.textContent = '❌'
  closeButton.style.position = 'absolute'
  closeButton.style.top = '0'
  closeButton.style.right = '0'
  closeButton.style.cursor = 'pointer'
  closeButton.style.padding = '5px'
  closeButton.style.color = 'red'
  closeButton.style.fontSize = '12px'
  docElement.appendChild(closeButton)

  closeButton.addEventListener('mousedown', (e) => {
    e.stopPropagation()
    onClose()
  }, { signal })

  document.body.appendChild(docElement)
  return { docElement, contentWrapper }
}

/** Per-node popup state, keyed by node ID */
const popupState = new Map()

function closeNodePopup(nodeId) {
  const state = popupState.get(nodeId)
  if (!state) return
  if (state.docElement) {
    state.docElement.remove()
  }
  if (state.abortCtrl) {
    state.abortCtrl.abort()
  }
  state.stopFollowing?.forEach((stop) => stop())
  popupState.delete(nodeId)
}

function openNodePopup(nodeId, description) {
  closeNodePopup(nodeId)
  const state = popupState.get(nodeId) || {}
  popupState.set(nodeId, state)

  state.abortCtrl = new AbortController()
  const popup = createDocPopup(
    description,
    state.abortCtrl.signal,
    () => closeNodePopup(nodeId)
  )
  state.docElement = popup.docElement

  function updatePosition() {
    if (!state.docElement || !state.docElement.parentNode) return
    const rect = comfy.graph.node(nodeId)?.getScreenRect()
    if (!rect) return
    state.docElement.style.left = `${rect.x + rect.width + 10}px`
    state.docElement.style.top = `${rect.y}px`
  }

  // Event-driven rather than a frame loop: getScreenRect() answers under both
  // renderers, where the old DOM query only found an element under Nodes 2.0.
  updatePosition()
  state.stopFollowing = [
    comfy.onViewportChanged(updatePosition),
    comfy.onNodeMoved(updatePosition)
  ]
}
