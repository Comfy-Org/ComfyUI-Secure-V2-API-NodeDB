const VERTEX_SHADER = `
attribute vec2 a_position;
varying vec2 v_position;
void main() {
  v_position = a_position;
  gl_Position = vec4(a_position, 0.0, 1.0);
}`;

const FRAGMENT_SHADER = `
precision mediump float;
varying vec2 v_position;
uniform sampler2D u_texture;
uniform float u_yaw;
uniform float u_pitch;
uniform float u_fov;
uniform float u_aspect;
const float PI = 3.141592653589793;
void main() {
  float spread = tan(u_fov * 0.5);
  vec3 direction = normalize(vec3(
    v_position.x * spread * u_aspect,
    v_position.y * spread,
    -1.0
  ));
  float cp = cos(u_pitch);
  float sp = sin(u_pitch);
  direction = vec3(
    direction.x,
    direction.y * cp - direction.z * sp,
    direction.y * sp + direction.z * cp
  );
  float cy = cos(u_yaw);
  float sy = sin(u_yaw);
  direction = vec3(
    direction.x * cy - direction.z * sy,
    direction.y,
    direction.x * sy + direction.z * cy
  );
  vec2 uv = vec2(
    0.5 + atan(direction.x, -direction.z) / (2.0 * PI),
    0.5 - asin(clamp(direction.y, -1.0, 1.0)) / PI
  );
  gl_FragColor = texture2D(u_texture, uv);
}`;

const radians = (degrees) => degrees * Math.PI / 180;
const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));

export function dragView(startLon, startLat, deltaX, deltaY) {
  return {
    lon: startLon - deltaX * 0.1,
    lat: clamp(startLat + deltaY * 0.1, -85, 85),
  };
}

export function zoomFov(fov, deltaY) {
  return clamp(fov + deltaY * 0.05, 30, 90);
}

export function frameAt(elapsedMilliseconds, fps, frameCount) {
  if (frameCount <= 1) return 0;
  const safeFps = clamp(Number(fps) || 30, 1, 120);
  return Math.floor(Math.max(0, elapsedMilliseconds) * safeFps / 1000) % frameCount;
}

function compile(gl, type, source) {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("WebGL could not allocate a shader");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const reason = gl.getShaderInfoLog(shader) || "unknown shader error";
    gl.deleteShader(shader);
    throw new Error(`Panorama shader failed: ${reason}`);
  }
  return shader;
}

function program(gl) {
  const vertex = compile(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
  const fragment = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
  const value = gl.createProgram();
  if (!value) throw new Error("WebGL could not allocate a program");
  gl.attachShader(value, vertex);
  gl.attachShader(value, fragment);
  gl.linkProgram(value);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if (!gl.getProgramParameter(value, gl.LINK_STATUS)) {
    const reason = gl.getProgramInfoLog(value) || "unknown link error";
    gl.deleteProgram(value);
    throw new Error(`Panorama program failed: ${reason}`);
  }
  return value;
}

export class PanoramaViewer {
  constructor(container, { video = false } = {}) {
    this.container = container;
    this.video = video;
    this.lon = 0;
    this.lat = 0;
    this.fov = 75;
    this.frames = [];
    this.fps = 30;
    this.currentFrame = -1;
    this.playing = false;
    this.playStarted = 0;
    this.destroyed = false;
    this.loadGeneration = 0;

    const owner = container.ownerDocument;
    this.canvas = owner.createElement("canvas");
    this.canvas.style.width = "100%";
    this.canvas.style.height = "100%";
    this.canvas.style.display = "block";
    this.canvas.style.cursor = "grab";
    this.canvas.tabIndex = 0;
    this.canvas.setAttribute("aria-label", video ? "360 video panorama" : "360 panorama");

    this.status = owner.createElement("div");
    this.status.style.position = "absolute";
    this.status.style.left = "8px";
    this.status.style.top = "8px";
    this.status.style.padding = "3px 6px";
    this.status.style.borderRadius = "4px";
    this.status.style.background = "rgba(0, 0, 0, 0.58)";
    this.status.style.color = "white";
    this.status.style.font = "12px sans-serif";
    this.status.textContent = "Run the node to load a panorama";

    container.style.position = "relative";
    container.style.overflow = "hidden";
    container.style.background = "#000";
    container.style.borderRadius = "8px";
    container.append(this.canvas, this.status);

    this.gl = this.canvas.getContext("webgl", { alpha: false, antialias: true });
    if (!this.gl) throw new Error("This browser does not provide WebGL");
    this.program = program(this.gl);
    this.buffer = this.gl.createBuffer();
    this.texture = this.gl.createTexture();
    if (!this.buffer || !this.texture) throw new Error("WebGL resource allocation failed");
    this.position = this.gl.getAttribLocation(this.program, "a_position");
    this.uniforms = {
      texture: this.gl.getUniformLocation(this.program, "u_texture"),
      yaw: this.gl.getUniformLocation(this.program, "u_yaw"),
      pitch: this.gl.getUniformLocation(this.program, "u_pitch"),
      fov: this.gl.getUniformLocation(this.program, "u_fov"),
      aspect: this.gl.getUniformLocation(this.program, "u_aspect"),
    };
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.buffer);
    this.gl.bufferData(
      this.gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      this.gl.STATIC_DRAW,
    );
    this.gl.bindTexture(this.gl.TEXTURE_2D, this.texture);
    this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_WRAP_S, this.gl.REPEAT);
    this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_WRAP_T, this.gl.CLAMP_TO_EDGE);
    this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_MIN_FILTER, this.gl.LINEAR);
    this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_MAG_FILTER, this.gl.LINEAR);

    this.onPointerDown = (event) => {
      this.drag = { x: event.clientX, y: event.clientY, lon: this.lon, lat: this.lat };
      this.canvas.style.cursor = "grabbing";
      this.canvas.setPointerCapture?.(event.pointerId);
      event.preventDefault();
    };
    this.onPointerMove = (event) => {
      if (!this.drag) return;
      const view = dragView(
        this.drag.lon,
        this.drag.lat,
        event.clientX - this.drag.x,
        event.clientY - this.drag.y,
      );
      this.lon = view.lon;
      this.lat = view.lat;
      this.requestRender();
      event.preventDefault();
    };
    this.onPointerUp = (event) => {
      this.drag = undefined;
      this.canvas.style.cursor = "grab";
      this.canvas.releasePointerCapture?.(event.pointerId);
    };
    this.onWheel = (event) => {
      this.fov = zoomFov(this.fov, event.deltaY);
      this.requestRender();
      event.preventDefault();
    };
    this.canvas.addEventListener("pointerdown", this.onPointerDown);
    this.canvas.addEventListener("pointermove", this.onPointerMove);
    this.canvas.addEventListener("pointerup", this.onPointerUp);
    this.canvas.addEventListener("pointercancel", this.onPointerUp);
    this.canvas.addEventListener("wheel", this.onWheel, { passive: false });
    this.resize();
  }

  clock() {
    return this.container.ownerDocument.defaultView?.performance?.now?.() ?? performance.now();
  }

  requestFrame(callback) {
    const view = this.container.ownerDocument.defaultView;
    return view?.requestAnimationFrame?.(callback) ?? requestAnimationFrame(callback);
  }

  cancelFrame(handle) {
    const view = this.container.ownerDocument.defaultView;
    if (view?.cancelAnimationFrame) view.cancelAnimationFrame(handle);
    else cancelAnimationFrame(handle);
  }

  resize() {
    if (this.destroyed) return;
    const rect = this.container.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width || this.container.clientWidth || 320));
    const height = Math.max(1, Math.round(rect.height || this.container.clientHeight || 280));
    const ratio = clamp(this.container.ownerDocument.defaultView?.devicePixelRatio || 1, 1, 2);
    this.canvas.width = Math.round(width * ratio);
    this.canvas.height = Math.round(height * ratio);
    this.requestRender();
  }

  setFrames(urls, fps = 30, autoplay = this.video) {
    const frames = [...urls].filter((value) => typeof value === "string" && value.length > 0).slice(0, 512);
    this.frames = frames;
    this.fps = clamp(Number(fps) || 30, 1, 120);
    this.currentFrame = -1;
    this.playing = Boolean(autoplay && frames.length > 1);
    this.playStarted = this.clock();
    if (frames.length === 0) {
      this.status.textContent = "No panorama preview was produced";
      return;
    }
    this.status.textContent = frames.length > 1
      ? `${frames.length} frames · ${this.fps} FPS`
      : "Drag to look around · wheel to zoom";
    this.showFrame(0);
    if (this.playing) this.requestRender();
  }

  showFrame(index) {
    if (this.destroyed || index === this.currentFrame || !this.frames[index]) return;
    this.currentFrame = index;
    const generation = ++this.loadGeneration;
    const image = this.container.ownerDocument.createElement("img");
    image.decoding = "async";
    image.onload = () => {
      if (this.destroyed || generation !== this.loadGeneration) return;
      const gl = this.gl;
      gl.bindTexture(gl.TEXTURE_2D, this.texture);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
      gl.texImage2D(
        gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image,
      );
      this.requestRender();
    };
    image.onerror = () => {
      if (generation === this.loadGeneration) this.status.textContent = "Unable to load panorama preview";
    };
    image.src = this.frames[index];
    this.activeImage = image;
  }

  requestRender() {
    if (this.destroyed || this.animationHandle !== undefined) return;
    this.animationHandle = this.requestFrame((time) => {
      this.animationHandle = undefined;
      this.render(time);
    });
  }

  render(time = this.clock()) {
    if (this.destroyed) return;
    if (this.playing && this.frames.length > 1) {
      this.showFrame(frameAt(time - this.playStarted, this.fps, this.frames.length));
    }
    const gl = this.gl;
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.useProgram(this.program);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
    gl.enableVertexAttribArray(this.position);
    gl.vertexAttribPointer(this.position, 2, gl.FLOAT, false, 0, 0);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.texture);
    gl.uniform1i(this.uniforms.texture, 0);
    gl.uniform1f(this.uniforms.yaw, radians(this.lon));
    gl.uniform1f(this.uniforms.pitch, radians(this.lat));
    gl.uniform1f(this.uniforms.fov, radians(this.fov));
    gl.uniform1f(this.uniforms.aspect, this.canvas.width / this.canvas.height);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
    if (this.playing) this.requestRender();
  }

  destroy() {
    if (this.destroyed) return;
    this.destroyed = true;
    this.loadGeneration += 1;
    this.playing = false;
    if (this.animationHandle !== undefined) this.cancelFrame(this.animationHandle);
    for (const [name, listener] of [
      ["pointerdown", this.onPointerDown],
      ["pointermove", this.onPointerMove],
      ["pointerup", this.onPointerUp],
      ["pointercancel", this.onPointerUp],
      ["wheel", this.onWheel],
    ]) this.canvas.removeEventListener(name, listener);
    if (this.activeImage) {
      this.activeImage.onload = null;
      this.activeImage.onerror = null;
      this.activeImage.removeAttribute("src");
    }
    this.gl.deleteTexture(this.texture);
    this.gl.deleteBuffer(this.buffer);
    this.gl.deleteProgram(this.program);
  }
}
