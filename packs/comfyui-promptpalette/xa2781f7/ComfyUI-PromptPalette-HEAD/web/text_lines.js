import { Line } from "./line.js";

export class TextLines {
  #lines;

  constructor(text) {
    this.#lines = text.split("\n");
  }

  toggleCommentAt(index) {
    const line = this.#getLineAt(index);
    if (!line) return;
    line.toggleCommentedOut();
    this.#lines[index] = line.buildText();
  }

  adjustWeightAt(index, delta) {
    const line = this.#getLineAt(index);
    if (!line) return;
    line.adjustWeight(delta);
    this.#lines[index] = line.buildText();
  }

  #getLineAt(index) {
    if (index < 0 || index >= this.#lines.length) return null;
    return new Line(this.#lines[index]);
  }

  toString() {
    return this.#lines.join("\n");
  }
}
