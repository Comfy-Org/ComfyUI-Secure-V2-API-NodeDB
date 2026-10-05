import { app } from "../../../scripts/app.js"
import { ComfyWidgets } from "../../../scripts/widgets.js"

app.registerExtension({
  name: "DisplayValue",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "DisplayValue") return

    const _onNodeCreated = nodeType.prototype.onNodeCreated
    nodeType.prototype.onNodeCreated = function () {
      _onNodeCreated?.apply(this)

      this.properties ??= {}
      const value = this.properties.preview ?? ""

      const widget = ComfyWidgets.STRING(this, "preview", ["STRING", { multiline: true, default: value }], app).widget

      widget.inputEl.readOnly = true
      widget.element.style.opacity = "0.6"
      widget.serialize = true
    }

    const _onExecuted = nodeType.prototype.onExecuted
    nodeType.prototype.onExecuted = function (msg) {
      _onExecuted?.apply(this, arguments)

      const w = this.widgets?.find((w) => w.name === "preview")
      if (!w) return

      let val = Array.isArray(msg.value) ? msg.value.join("\n") : msg.value
      if (!val && this.properties?.preview) val = this.properties.preview

      w.value = val
      this.properties.preview = val
    }

    const _configure = nodeType.prototype.configure
    nodeType.prototype.configure = function () {
      return _configure?.apply(this, arguments)
    }

    const _onConfigure = nodeType.prototype.onConfigure
    nodeType.prototype.onConfigure = function () {
      _onConfigure?.apply(this, arguments)

      const val = this.properties?.preview
      if (val != null) {
        requestAnimationFrame(() => {
          const w = this.widgets?.find((w) => w.name === "preview")
          if (w) w.value = val
        })
      }
    }
  },
})
