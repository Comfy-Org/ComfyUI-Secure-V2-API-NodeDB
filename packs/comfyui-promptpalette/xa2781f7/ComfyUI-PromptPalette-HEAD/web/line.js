const COMMENT_PREFIX = "// ";
const LINE_RE = /^(\s*\/\/\s*)?(.*?)(\/\/.*)?$/;
const WEIGHT_RE = /^\((.+):(\d+\.?\d*)\)$/;
const MIN_WEIGHT = 0.1;
const MAX_WEIGHT = 2.0;

export class Line {
  #commentedOut;
  #phraseText;
  #trailingComment;
  #weight;

  constructor(rawText = "") {
    const [, commentPrefix, body, trailingComment] = rawText.match(LINE_RE);
    this.#commentedOut = !!commentPrefix;
    this.#trailingComment = trailingComment ?? "";

    const { phrase, weight } = this.#parseWeightedText(body);
    this.#phraseText = phrase;
    this.#weight = weight;
  }

  #parseWeightedText(text) {
    const cleanText = text.trim().replace(/,\s*$/, "");
    const match = cleanText.match(WEIGHT_RE);
    if (match) {
      return { phrase: match[1], weight: parseFloat(match[2]) || 1.0 };
    }
    return { phrase: cleanText, weight: 1.0 };
  }

  get commentedOut() {
    return this.#commentedOut;
  }

  toggleCommentedOut() {
    this.#commentedOut = !this.#commentedOut;
  }

  get displayText() {
    if (this.#trailingComment) {
      return `${this.#phraseText} ${this.#trailingComment}`;
    }
    return this.#phraseText;
  }

  hasPhraseText() {
    return this.#phraseText.trim() !== "";
  }

  get weightText() {
    // Round to 2 decimal places first
    const rounded = Math.round(this.#weight * 100) / 100;
    // If the value has a non-zero second decimal place, show 2 decimals
    if (rounded * 10 !== Math.floor(rounded * 10)) {
      return rounded.toFixed(2);
    }
    // Otherwise show 1 decimal
    return rounded.toFixed(1);
  }

  get weight() {
    return this.#weight;
  }

  adjustWeight(delta) {
    const newWeight = this.#weight + delta;
    const clampedWeight = Math.min(MAX_WEIGHT, Math.max(MIN_WEIGHT, newWeight));
    this.#weight = Math.round(clampedWeight * 10) / 10;
  }

  buildText() {
    const weightedText =
      this.#weight === 1.0
        ? this.#phraseText
        : `(${this.#phraseText}:${this.#weight})`;
    const textWithTrailingComment = this.#trailingComment
      ? `${weightedText} ${this.#trailingComment}`
      : weightedText;
    return this.#commentedOut
      ? COMMENT_PREFIX + textWithTrailingComment
      : textWithTrailingComment;
  }
}
