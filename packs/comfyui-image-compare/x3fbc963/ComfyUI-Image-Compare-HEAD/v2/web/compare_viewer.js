const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));

export function fitContain(sourceWidth, sourceHeight, maximumWidth, maximumHeight) {
  if (sourceWidth <= 0 || sourceHeight <= 0 || maximumWidth <= 0 || maximumHeight <= 0) {
    return { x: 0, y: 0, width: 0, height: 0 };
  }
  const scale = Math.min(maximumWidth / sourceWidth, maximumHeight / sourceHeight);
  const width = Math.max(1, Math.floor(sourceWidth * scale));
  const height = Math.max(1, Math.floor(sourceHeight * scale));
  return {
    x: Math.floor((maximumWidth - width) / 2),
    y: Math.floor((maximumHeight - height) / 2),
    width,
    height,
  };
}

export function sliderFromPointer(pointerX, left, width) {
  if (width <= 0) return 0.5;
  return clamp((pointerX - left) / width, 0, 1);
}

export class CompareViewer {
  constructor(container) {
    this.container = container;
    this.slider = 0.5;
    this.dragging = false;
    this.hovered = false;
    this.images = [];
    this.generation = 0;
    this.destroyed = false;

    const owner = container.ownerDocument;
    this.canvas = owner.createElement("canvas");
    this.canvas.style.width = "100%";
    this.canvas.style.height = "100%";
    this.canvas.style.display = "block";
    this.canvas.style.cursor = "ew-resize";
    this.canvas.tabIndex = 0;
    this.canvas.setAttribute("aria-label", "A and B image comparison slider");
    container.style.background = "#111";
    container.style.overflow = "hidden";
    container.style.borderRadius = "8px";
    container.append(this.canvas);
    this.context = this.canvas.getContext("2d");
    if (!this.context) throw new Error("A 2D canvas is required for Image Compare");

    this.onPointerDown = (event) => {
      const bounds = this.canvas.getBoundingClientRect();
      this.slider = sliderFromPointer(event.clientX, bounds.left, bounds.width);
      this.dragging = true;
      this.canvas.setPointerCapture?.(event.pointerId);
      this.draw();
      event.preventDefault();
    };
    this.onPointerMove = (event) => {
      const bounds = this.canvas.getBoundingClientRect();
      if (this.dragging) {
        this.slider = sliderFromPointer(event.clientX, bounds.left, bounds.width);
        this.draw();
        event.preventDefault();
      }
      const split = bounds.left + bounds.width * this.slider;
      const hovered = Math.abs(event.clientX - split) <= 15;
      if (hovered !== this.hovered) {
        this.hovered = hovered;
        this.draw();
      }
    };
    this.onPointerUp = (event) => {
      this.dragging = false;
      this.canvas.releasePointerCapture?.(event.pointerId);
      this.draw();
    };
    this.canvas.addEventListener("pointerdown", this.onPointerDown);
    this.canvas.addEventListener("pointermove", this.onPointerMove);
    this.canvas.addEventListener("pointerup", this.onPointerUp);
    this.canvas.addEventListener("pointercancel", this.onPointerUp);
    this.resize();
  }

  dimensions(image) {
    return {
      width: Number(image?.naturalWidth || image?.width || 0),
      height: Number(image?.naturalHeight || image?.height || 0),
    };
  }

  clearImages() {
    this.generation += 1;
    for (const image of this.images) {
      image.onload = null;
      image.onerror = null;
      image.removeAttribute("src");
    }
    this.images = [];
  }

  setImages(urls) {
    this.clearImages();
    const safe = [...urls].filter((value) => typeof value === "string" && value.length > 0).slice(0, 2);
    if (safe.length !== 2) {
      this.draw();
      return;
    }
    const generation = this.generation;
    this.images = safe.map((url) => {
      const image = this.container.ownerDocument.createElement("img");
      image.decoding = "async";
      image.onload = () => {
        if (!this.destroyed && generation === this.generation) this.draw();
      };
      image.onerror = () => {
        if (!this.destroyed && generation === this.generation) this.draw();
      };
      image.src = url;
      return image;
    });
    // Remove the prior comparison immediately; late decodes cannot leave stale
    // pixels visible while the replacement pair is loading.
    this.draw();
  }

  resize() {
    if (this.destroyed) return;
    const bounds = this.container.getBoundingClientRect();
    const width = Math.max(1, Math.round(bounds.width || this.container.clientWidth || 360));
    const height = Math.max(1, Math.round(bounds.height || this.container.clientHeight || 320));
    const ratio = clamp(this.container.ownerDocument.defaultView?.devicePixelRatio || 1, 1, 2);
    this.canvas.width = Math.round(width * ratio);
    this.canvas.height = Math.round(height * ratio);
    this.cssWidth = width;
    this.cssHeight = height;
    this.pixelRatio = ratio;
    this.draw();
  }

  drawImage(image, rect) {
    if (rect.width <= 0 || rect.height <= 0) return;
    this.context.drawImage(image, rect.x, rect.y, rect.width, rect.height);
  }

  draw() {
    if (this.destroyed) return;
    const context = this.context;
    const width = this.cssWidth || 1;
    const height = this.cssHeight || 1;
    const ratio = this.pixelRatio || 1;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#111";
    context.fillRect(0, 0, width, height);
    if (this.images.length !== 2) {
      context.fillStyle = "#ddd";
      context.font = "14px sans-serif";
      context.textAlign = "center";
      context.fillText("Run the node to compare two images", width / 2, height / 2);
      return;
    }

    const padding = 10;
    const labelHeight = 38;
    const box = {
      x: padding,
      y: padding,
      width: Math.max(1, width - padding * 2),
      height: Math.max(1, height - padding * 2),
    };
    const aSize = this.dimensions(this.images[0]);
    const bSize = this.dimensions(this.images[1]);
    const aFit = fitContain(aSize.width, aSize.height, box.width, box.height);
    const bFit = fitContain(bSize.width, bSize.height, box.width, box.height);
    const rectA = { x: box.x + aFit.x, y: box.y + aFit.y,
      width: aFit.width, height: aFit.height };
    const rectB = { x: box.x + bFit.x, y: box.y + bFit.y,
      width: bFit.width, height: bFit.height };
    this.drawImage(this.images[1], rectB);

    const split = box.x + Math.floor(box.width * this.slider);
    context.save();
    context.beginPath();
    context.rect(box.x, box.y, Math.max(0, split - box.x), box.height);
    context.clip();
    this.drawImage(this.images[0], rectA);
    context.restore();

    context.strokeStyle = "#00e0ff";
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(split, box.y);
    context.lineTo(split, box.y + box.height);
    context.stroke();
    if (this.hovered || this.dragging) {
      context.fillStyle = "#00e0ff";
      context.beginPath();
      context.arc(split, box.y + box.height / 2, 5, 0, Math.PI * 2);
      context.fill();
    }

    context.fillStyle = "white";
    context.shadowColor = "black";
    context.shadowOffsetX = 2;
    context.shadowOffsetY = 2;
    context.font = "bold 14px sans-serif";
    context.textAlign = "left";
    context.fillText("A", box.x + 8, box.y + 20);
    context.textAlign = "right";
    context.fillText("B", box.x + box.width - 8, box.y + 20);
    context.font = "10px sans-serif";
    context.textAlign = "left";
    context.fillText(`${aSize.width}x${aSize.height}`, box.x + 8, box.y + labelHeight);
    context.textAlign = "right";
    context.fillText(`${bSize.width}x${bSize.height}`, box.x + box.width - 8, box.y + labelHeight);
  }

  destroy() {
    if (this.destroyed) return;
    this.destroyed = true;
    this.clearImages();
    for (const [name, listener] of [
      ["pointerdown", this.onPointerDown],
      ["pointermove", this.onPointerMove],
      ["pointerup", this.onPointerUp],
      ["pointercancel", this.onPointerUp],
    ]) this.canvas.removeEventListener(name, listener);
    this.canvas.width = 0;
    this.canvas.height = 0;
  }
}
