export const LORA_PATTERN = /<lora:([^:]+):([-\d\.]+)(?::([-\d\.]+))?>/g;

export function mergeLoras(lorasText, lorasArr) {
  // Parse lorasText into a map: name -> {strength, clipStrength}
  const parsedLoras = {};
  let match;
  LORA_PATTERN.lastIndex = 0;
  while ((match = LORA_PATTERN.exec(lorasText)) !== null) {
    const name = match[1];
    const modelStrength = Number(match[2]);
    const clipStrength = match[3] ? Number(match[3]) : modelStrength;
    parsedLoras[name] = { strength: modelStrength, clipStrength };
  }

  // Build result array in the order of lorasArr
  const result = [];
  const usedNames = new Set();

  for (const lora of lorasArr) {
    if (parsedLoras[lora.name]) {
      result.push({
        name: lora.name,
        strength: lora.strength !== undefined ? lora.strength : parsedLoras[lora.name].strength,
        active: lora.active !== undefined ? lora.active : true,
        expanded: lora.expanded !== undefined ? lora.expanded : false,
        clipStrength: lora.clipStrength !== undefined ? lora.clipStrength : parsedLoras[lora.name].clipStrength,
        selected: !!lora.selected,
      });
      usedNames.add(lora.name);
    }
  }

  // Add any new loras from lorasText that are not in lorasArr, in their text order
  for (const name in parsedLoras) {
    if (!usedNames.has(name)) {
      result.push({
        name,
        strength: parsedLoras[name].strength,
        active: true,
        clipStrength: parsedLoras[name].clipStrength,
        selected: false,
      });
    }
  }

  return result;
}
