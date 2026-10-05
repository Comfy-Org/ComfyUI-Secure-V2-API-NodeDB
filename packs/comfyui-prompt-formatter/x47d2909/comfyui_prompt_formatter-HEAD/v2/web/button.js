import { comfy } from "/comfy/api/v2.js";

const TARGETS = ["CLIPTextEncodeFormatter", "TextOnlyFormatter"];
const BUTTONS = ["💫 Format Prompt", "✒️ Convert Tags", "⏪ Undo Last Change"];
const states = new WeakMap();

const BRACKET_OPENING = new Set(["(", "[", "{"]);
const BRACKET_CLOSING = new Set([")", "]", "}"]);
const BRACKET_REVERSE = new Map([[")", "("], ["]", "["], ["}", "{"]]);
const BLACKLISTED_TAGS = [
  /^tagme$/,
  /^.*text$/,
  /^.*_bubble$/,
  /^onomatopoeia$/,
  /^dialogue$/,
  /^.*_(artwork)$/,
  /^watermark$/,
  /^signature$/,
  /^20\d\d$/,
];

function removeWhitespaceExcessive(prompt) {
  return prompt
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => line.trim().split(/\s+/u).join(" "))
    .join("\n");
}

function removeMismatchedBrackets(prompt) {
  const stack = [];
  const positions = [];
  const result = [];
  for (const character of prompt) {
    if (BRACKET_OPENING.has(character)) {
      stack.push(character);
      positions.push(result.length);
      result.push(character);
    } else if (BRACKET_CLOSING.has(character)) {
      if (stack.length && stack.at(-1) === BRACKET_REVERSE.get(character)) {
        stack.pop();
        positions.pop();
        result.push(character);
      }
    } else {
      result.push(character);
    }
  }
  for (const position of positions.reverse()) result.splice(position, 1);
  return result.join("");
}

function spaceAnd(prompt) {
  return prompt.replace(/(.*?)\s*(AND)\s*(.*?)/gu, "$1 $2 $3");
}

function spaceBrackets(prompt) {
  return prompt
    .split(/(<[^>]+>)/gu)
    .map((part) => part.startsWith("<")
      ? part
      : part.replace(/([)\]}>])([([{<])/gu, "$1 $2"))
    .join("");
}

function alignCommas(prompt) {
  let adjusted = prompt;
  if (adjusted.includes("BREAK")) {
    const parts = adjusted.split("BREAK");
    adjusted = parts.map((part, index) => {
      if (index === 0) return part.replace(/[ ,]+$/u, "");
      if (index === parts.length - 1) return part.replace(/^[ ,]+/u, "");
      return part.replace(/^[ ,]+|[ ,]+$/gu, "");
    }).join(" BREAK ").trim();
    adjusted = adjusted.replace(/([^\n])[\s,]*\n[\s,]*BREAK/gu, "$1\nBREAK");
    adjusted = adjusted.replace(/BREAK[\s,]*\n[\s,]*/gu, "BREAK\n");
  }
  return adjusted.split(",").map((part) => part.trim()).filter(Boolean).join(", ");
}

function depthAndGradient(text) {
  let depth = 0;
  const depths = [];
  const gradients = [];
  for (const character of text) {
    if (BRACKET_OPENING.has(character)) {
      depth += 1;
      gradients.push("^");
    } else if (BRACKET_CLOSING.has(character)) {
      depth -= 1;
      gradients.push("v");
    } else {
      gradients.push("-");
    }
    depths.push(depth);
  }
  return { depths, gradients };
}

function getMappings(text) {
  const { depths, gradients } = depthAndGradient(text);
  const brackets = [...text].map((character) => "[]()<>".includes(character) ? character : " ");
  return { depths, gradients, brackets };
}

function calculateWeight(depth, square) {
  return square ? 1 / (1.1 ** depth) : 1.1 ** depth;
}

function getWeight(prompt, maps, position, consecutive, gradientSearch, square) {
  let remaining = consecutive;
  let search = gradientSearch;
  while (position + remaining <= prompt.length) {
    if (remaining === 0) return { insertAt: prompt, weight: 0, consecutive: 1 };
    const end = position + remaining;
    if (square && [":", "|"].includes(prompt[position])) {
      if (maps.depths.at(-2) === maps.depths[position]) {
        return { insertAt: prompt, weight: 0, consecutive: 1 };
      }
      if (search.includes(String(maps.depths[position]))) {
        search = search.replace(String(maps.depths[position]), "");
        remaining -= 1;
      }
    } else if (
      maps.gradients.slice(position, end).join("") === "v".repeat(remaining)
      && maps.depths.slice(position - 1, end).join("") === search
    ) {
      return {
        insertAt: position,
        weight: calculateWeight(remaining, square),
        consecutive: remaining,
      };
    } else if (
      maps.gradients[position] === "v"
      && search.includes(maps.depths.slice(position - 1, end - 1).join(""))
    ) {
      const narrowing = maps.gradients.slice(position, end).filter((item) => item === "v").length;
      search = search.slice(narrowing);
      remaining -= 1;
    }
    position += 1;
  }
  throw new Error(`Somehow weight index searching has gone outside of prompt length with prompt: ${prompt}`);
}

function bracketToWeights(prompt) {
  const excluded = [...prompt.matchAll(/<[^>]+>/gu)].map((match) => ({
    start: match.index,
    end: match.index + match[0].length,
    text: match[0],
  }));
  const segments = [];
  let previous = 0;
  for (const item of excluded) {
    segments.push(prompt.slice(previous, item.start));
    previous = item.end;
  }
  segments.push(prompt.slice(previous));

  const updated = segments.map((segment) => {
    let maps = getMappings(segment);
    let position = 0;
    let result = segment;
    while (position < result.length) {
      if (BRACKET_OPENING.has(result[position])) {
        const opening = result.slice(position).match(/^(?<!\\)(\(+|\[+)/u);
        if (opening) {
          const consecutive = opening[0].length;
          const values = [];
          for (
            let depth = maps.depths[position] - 1;
            depth < maps.depths[position] + consecutive;
            depth += 1
          ) values.push(depth);
          const gradientSearch = values.reverse().join("");
          const square = opening[0].includes("[");
          const found = getWeight(
            result,
            maps,
            position + opening[0].length,
            consecutive,
            gradientSearch,
            square,
          );
          if (found.weight) {
            const beforeClose = result.slice(0, found.insertAt + 1);
            const currentWeight = /:(\d+.?\d*|\d*.?\d+)(?=[)\]]$)/u.test(beforeClose);
            if (currentWeight) {
              result = result.slice(0, position)
                + "("
                + result.slice(position + found.consecutive, found.insertAt)
                + ")"
                + result.slice(found.insertAt + consecutive);
            } else {
              const weight = found.weight.toFixed(2).replace(/0+$/u, "").replace(/\.$/u, "");
              result = result.slice(0, position)
                + "("
                + result.slice(position + found.consecutive, found.insertAt)
                + `:${weight})`
                + result.slice(found.insertAt + consecutive);
            }
          }
          maps = getMappings(result);
          position += 1;
        }
      }
      const next = result.slice(position).match(/(?<!\\)[([]/u);
      if (!next) break;
      position += next.index;
    }
    return result;
  });

  let finalPrompt = "";
  updated.forEach((segment, index) => {
    finalPrompt += segment;
    if (index < excluded.length) finalPrompt += excluded[index].text;
  });
  return finalPrompt.replace(/(?<!\\)\(([^:]+):1(?:\.0*)?\)/gu, "$1");
}

function splitDedupeParts(line) {
  const separator = /(?<!\\)(?:\([^)]*\)|\[[^\]]*\])(?=(?:\s*(?:,|BREAK|<[^>]+>)|\s*$))|,|\s*BREAK\s*|<[^>]+>/gu;
  const parts = [];
  let previous = 0;
  for (const match of line.matchAll(separator)) {
    parts.push(line.slice(previous, match.index), match[0]);
    previous = match.index + match[0].length;
  }
  parts.push(line.slice(previous));
  return parts;
}

function dedupeTokens(prompt) {
  const seen = new Set();
  const processed = prompt.split("\n").map((line) => {
    if (!/(?:,|\s*BREAK\s*|<[^>]+>)/u.test(line)) return line;
    const result = [];
    for (const part of splitDedupeParts(line)) {
      const normalized = part.trim();
      if (!normalized) continue;
      if (normalized === "," || normalized === "BREAK" || /^<[^>]+>$/u.test(normalized)) {
        result.push(` ${normalized} `);
      } else if (!seen.has(normalized)) {
        seen.add(normalized);
        result.push(part);
      }
    }
    return result.join("").replace(/\s*BREAK\s*/gu, " BREAK ").trim().split(/\s+/u).join(" ");
  });
  return processed.join("\n").trim();
}

export function formatPrompt(value) {
  let prompt = String(value).normalize("NFKC");
  prompt = removeMismatchedBrackets(prompt);
  prompt = dedupeTokens(prompt);
  prompt = removeWhitespaceExcessive(prompt);
  prompt = prompt.replace(/([([{<])|([)\]}>])/gu, (match, opening, closing) => opening || closing);
  prompt = spaceAnd(prompt);
  prompt = spaceBrackets(prompt);
  prompt = alignCommas(prompt);
  prompt = prompt.replace(/\s*\|\s*/gu, "|");
  prompt = bracketToWeights(prompt);
  return prompt.replace(/,\s*(<)/gu, " $1");
}

export function convertTags(value) {
  const lines = String(value).match(/[^\n]*\n|[^\n]+$/gu) || [];
  return lines.map((line) => {
    const hasNewline = line.endsWith("\n");
    const body = hasNewline ? line.slice(0, -1) : line;
    if (!body.trim() || body.includes("BREAK") || body.includes(",")
        || ((body.includes("(") || body.includes(")")) && !body.includes("_"))) {
      return line;
    }
    const tags = body.trim().split(/\s+/u).filter((tag) => {
      const stripped = tag.replace(/[()]/gu, "");
      return !BLACKLISTED_TAGS.some((pattern) => pattern.test(stripped));
    });
    const formatted = tags.map((tag) => tag
      .replaceAll("_", " ")
      .replaceAll("\\(", "(")
      .replaceAll("\\)", ")")
      .replaceAll("(", "\\(")
      .replaceAll(")", "\\)"));
    return `${formatted.join(", ")},${hasNewline ? "\n" : ""}`;
  }).join("");
}

function dispose(node) {
  const state = states.get(node);
  if (!state) return;
  states.delete(node);
  for (const unsubscribe of state.unsubscribers) unsubscribe?.();
  for (const name of BUTTONS) node.widgets.remove(name);
}

function addButton(node, name, activate) {
  node.widgets.remove(name);
  const button = node.widgets.add({
    type: "button",
    name,
    value: null,
    serialize: false,
  });
  return button.on("activate", activate);
}

export function install(node) {
  dispose(node);
  const text = node.widgets.get("text");
  if (!text) throw new Error("Prompt Formatter text widget is unavailable");
  const state = { previous: String(text.getValue() ?? ""), unsubscribers: [] };
  state.unsubscribers.push(addButton(node, BUTTONS[0], () => {
    state.previous = String(text.getValue() ?? "");
    text.setValue(formatPrompt(state.previous));
  }));
  state.unsubscribers.push(addButton(node, BUTTONS[1], () => {
    state.previous = String(text.getValue() ?? "");
    text.setValue(convertTags(state.previous));
  }));
  state.unsubscribers.push(addButton(node, BUTTONS[2], () => {
    text.setValue(state.previous);
  }));
  states.set(node, state);
}

for (const nodeType of TARGETS) {
  comfy.defs.extend(nodeType, (builder) => {
    builder.onCreated((node) => install(node));
    builder.onRemoved((node) => dispose(node));
  });
}

export const __testing = { dispose, states };
