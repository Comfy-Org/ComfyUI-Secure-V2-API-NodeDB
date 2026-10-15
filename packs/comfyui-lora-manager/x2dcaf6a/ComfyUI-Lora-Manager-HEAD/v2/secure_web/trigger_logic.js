// Pinned native value bodies. Settings/UI/SDK authority lives in the caller.
function normalizeTagText(text) {
  return typeof text === "string" ? text.trim().toLowerCase() : "";
}

function splitTopLevelCommas(text) {
  if (typeof text !== "string" || !text.trim()) {
    return [];
  }

  const parts = [];
  let current = "";
  let depth = 0;

  for (const char of text) {
    if (char === "(") {
      depth += 1;
      current += char;
      continue;
    }
    if (char === ")") {
      depth = Math.max(0, depth - 1);
      current += char;
      continue;
    }
    if (char === "," && depth === 0) {
      const trimmed = current.trim();
      if (trimmed) {
        parts.push(trimmed);
      }
      current = "";
      continue;
    }
    current += char;
  }

  const trimmed = current.trim();
  if (trimmed) {
    parts.push(trimmed);
  }

  return parts;
}

function isGroupTag(tag) {
  return Array.isArray(tag?.items);
}

function parseSerializedText(text) {
  const normalizedText = typeof text === "string" ? text.trim() : "";
  const strengthMatch = normalizedText.match(/^\((.+):([\d.]+)\)$/);
  if (!strengthMatch) {
    return {
      text: normalizedText,
      strength: null,
    };
  }

  const parsedStrength = Number(strengthMatch[2]);
  return {
    text: strengthMatch[1].trim(),
    strength: Number.isFinite(parsedStrength) ? parsedStrength : null,
  };
}

function cloneTag(tag) {
  if (!isGroupTag(tag)) {
    return { ...tag };
  }
  return {
    ...tag,
    items: tag.items.map((item) => ({ ...item })),
  };
}

function collectHighlightTokens(wordsArray) {
  const tokens = new Set();

  const addToken = (text) => {
    const normalized = normalizeTagText(text);
    if (normalized) {
      tokens.add(normalized);
    }
  };

  wordsArray.forEach((rawWord) => {
    if (typeof rawWord !== "string") {
      return;
    }

    addToken(rawWord);

    const groupParts = rawWord.split(/,{2,}/);
    groupParts.forEach((groupPart) => {
      addToken(groupPart);
      splitTopLevelCommas(groupPart).forEach(addToken);
    });

    splitTopLevelCommas(rawWord).forEach(addToken);
  });

  return tokens;
}

function buildLegacyTagState(existingTags, allowStrengthAdjustment) {
  return existingTags.reduce((acc, tag) => {
    const parsed = parseSerializedText(tag.text);
    const key = parsed.text;
    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push({
      active: tag.active,
      strength:
        allowStrengthAdjustment
          ? (tag.strength !== undefined && tag.strength !== null ? tag.strength : parsed.strength)
          : null,
    });
    return acc;
  }, {});
}

function buildGroupState(existingTags, allowStrengthAdjustment) {
  return existingTags.reduce((acc, tag) => {
    const parsed = parseSerializedText(tag.text);
    const key = parsed.text;
    if (!acc[key]) {
      acc[key] = [];
    }

    const itemState = {};
    if (Array.isArray(tag.items)) {
      tag.items.forEach((item) => {
        const itemKey = item.text;
        if (!itemState[itemKey]) {
          itemState[itemKey] = [];
        }
        itemState[itemKey].push({
          active: item.active,
        });
      });
    } else {
      splitTopLevelCommas(tag.text).forEach((itemText) => {
        if (!itemState[itemText]) {
          itemState[itemText] = [];
        }
        itemState[itemText].push({
          active: tag.active,
        });
      });
    }

    acc[key].push({
      active: tag.active,
      strength:
        allowStrengthAdjustment
          ? (tag.strength !== undefined && tag.strength !== null ? tag.strength : parsed.strength)
          : null,
      itemState,
    });
    return acc;
  }, {});
}

function consumeQueuedState(stateMap, key) {
  const queue = stateMap[key];
  if (queue && queue.length > 0) {
    return queue.shift();
  }
  return null;
}


export { collectHighlightTokens, splitTopLevelCommas };

export function reconcileTags(existingTagValues, message, groupMode, defaultActive, allowStrengthAdjustment = false) {
    const existingTags = (existingTagValues || []).map(cloneTag);
    let tagArray = [];

    if (groupMode) {
      const existingGroupState = buildGroupState(existingTags, allowStrengthAdjustment);
      const groups = message.trim()
        ? (message.includes(",,") ? message.split(/,{2,}/) : [message])
            .map((group) => group.trim())
            .filter(Boolean)
        : [];

      tagArray = groups.map((group) => {
        const existing = consumeQueuedState(existingGroupState, group);
        const itemState = existing?.itemState || {};
        const items = splitTopLevelCommas(group).map((itemText) => {
          const savedItem = consumeQueuedState(itemState, itemText);
          return {
            text: itemText,
            active: savedItem ? savedItem.active : true,
            highlighted: false,
            strength: null,
          };
        });

        return {
          text: group,
          active: existing ? existing.active : defaultActive,
          highlighted: false,
          strength: existing ? existing.strength : null,
          items,
        };
      });
    } else {
      const existingTagState = buildLegacyTagState(existingTags, allowStrengthAdjustment);
      tagArray = splitTopLevelCommas(message).map((word) => {
        const existing = consumeQueuedState(existingTagState, word);
        return {
          text: word,
          active: existing ? existing.active : defaultActive,
          highlighted: false,
          strength: existing ? existing.strength : null,
        };
      });
    }


return tagArray;
}

export function applyHighlightTags(tags, highlightSet) {
        const updatedTags = (tags || []).map((tag) => {
          if (Array.isArray(tag.items)) {
            const items = tag.items.map((item) => ({
              ...item,
              highlighted: highlightSet.size > 0 && highlightSet.has(normalizeTagText(item.text)),
            }));

            return {
              ...tag,
              items,
              highlighted:
                highlightSet.size > 0 &&
                (highlightSet.has(normalizeTagText(tag.text)) ||
                  items.some((item) => item.highlighted)),
            };
          }

          return {
            ...tag,
            highlighted: highlightSet.size > 0 && highlightSet.has(normalizeTagText(tag.text)),
          };
        });


return updatedTags;
}

export function serializeTags(tags) {
        const value = tags || [];
        return value.map((tag) => {
          if (Array.isArray(tag.items)) {
            return {
              ...tag,
              text:
                tag.strength !== undefined && tag.strength !== null
                  ? `(${tag.text}:${tag.strength.toFixed(2)})`
                  : tag.text,
              items: tag.items.map((item) => ({ ...item })),
            };
          }

          if (tag.strength !== undefined && tag.strength !== null) {
            return {
              ...tag,
              text: `(${tag.text}:${tag.strength.toFixed(2)})`,
            };
          }

          return tag;
        });

}

export function formatStrengthValue(value) {
  if (value === undefined || value === null) {
    return null;
  }
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return null;
  }
  return num.toFixed(2);
}


export function readSavedTriggerWidgets(widgetsValues, tagWidgetIndex, originalMessageWidgetIndex) {
  const projection = { restoreTags: false, restoreMessage: false };
      if (widgetsValues && widgetsValues.length > 0) {
        if (tagWidgetIndex >= 0) {
          const savedValue = widgetsValues[tagWidgetIndex];
          if (savedValue) {
            projection.tags = Array.isArray(savedValue) ? savedValue : []; projection.restoreTags = true;
          }
        }
        if (originalMessageWidgetIndex >= 0) {
          const originalMessage = widgetsValues[originalMessageWidgetIndex];
          if (originalMessage) {
            projection.message = originalMessage; projection.restoreMessage = true;
          }
        }
      }


  return projection;
}
