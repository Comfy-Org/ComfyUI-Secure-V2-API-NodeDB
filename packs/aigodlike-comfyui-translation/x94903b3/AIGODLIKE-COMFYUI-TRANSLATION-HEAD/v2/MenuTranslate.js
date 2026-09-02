/** Pure locale-schema conversion. Host rendering stays host-owned. */

const SYNTAX_CHARACTERS = /[@${}|%]/g;

export function normalizeI18nKey(value) {
  return typeof value === 'string' ? value.replaceAll('.', '_') : '';
}

// Keep this byte-for-byte equivalent in meaning to ComfyUI's public locale
// serializer. Labels and descriptions pass through vue-i18n's compiler;
// tooltips are raw and therefore deliberately are not escaped here.
export function escapeI18nMessage(value) {
  if (typeof value !== 'string') return '';
  return value
    .replaceAll('\\', '\\\\')
    .replace(SYNTAX_CHARACTERS, (character) => `{'${character}'}`);
}

function nonEmptyString(value) {
  return typeof value === 'string' && value.length ? value : undefined;
}

function translatedValue(dictionary, ...candidates) {
  if (!dictionary || typeof dictionary !== 'object') return undefined;
  for (const candidate of candidates) {
    if (typeof candidate !== 'string') continue;
    const translated = nonEmptyString(dictionary[candidate]);
    if (translated !== undefined) return translated;
  }
  return undefined;
}

function translateInput(source, input) {
  const inputTranslations = source.inputs;
  const widgetTranslations = source.widgets;
  const name = translatedValue(
    inputTranslations,
    input.name,
    input.localizedName,
  ) ?? translatedValue(
    widgetTranslations,
    input.name,
    input.localizedName,
  );

  const sourceTooltip = nonEmptyString(input.options?.tooltip);
  const tooltip = sourceTooltip === undefined ? undefined : translatedValue(
    inputTranslations,
    sourceTooltip,
  ) ?? translatedValue(widgetTranslations, sourceTooltip);

  if (name === undefined && tooltip === undefined) return undefined;
  return {
    ...(name === undefined ? {} : { name: escapeI18nMessage(name) }),
    ...(tooltip === undefined ? {} : { tooltip }),
  };
}

function translateOutput(source, output) {
  const name = translatedValue(source.outputs, output.name, output.type);
  const sourceTooltip = nonEmptyString(output.tooltip);
  const tooltip = sourceTooltip === undefined
    ? undefined
    : translatedValue(source.outputs, sourceTooltip);
  if (name === undefined && tooltip === undefined) return undefined;
  return {
    ...(name === undefined ? {} : { name: escapeI18nMessage(name) }),
    ...(tooltip === undefined ? {} : { tooltip }),
  };
}

/**
 * Convert the upstream phrase-oriented node dictionaries using the live,
 * inert definition views. This is why output names can become the native
 * index-keyed schema without teaching core anything about AIGODLIKE's format.
 */
export function buildNodeDefinitions(legacyNodes, definitions) {
  const result = Object.create(null);
  if (!legacyNodes || typeof legacyNodes !== 'object') return result;

  for (const definition of definitions) {
    const source = legacyNodes[definition.type];
    if (!source || typeof source !== 'object') continue;

    const inputs = Object.create(null);
    for (const input of definition.inputs) {
      const translated = translateInput(source, input);
      if (translated !== undefined) {
        inputs[normalizeI18nKey(input.name)] = translated;
      }
    }

    const outputs = Object.create(null);
    definition.outputs.forEach((output, index) => {
      const translated = translateOutput(source, output);
      if (translated !== undefined) outputs[String(index)] = translated;
    });

    const title = nonEmptyString(source.title);
    const description = nonEmptyString(source.description);
    result[normalizeI18nKey(definition.type)] = {
      ...(title === undefined ? {} : {
        display_name: escapeI18nMessage(title),
      }),
      ...(description === undefined ? {} : {
        description: escapeI18nMessage(description),
      }),
      ...(Object.keys(inputs).length ? { inputs } : {}),
      ...(Object.keys(outputs).length ? { outputs } : {}),
    };
  }
  return result;
}

export function buildNativeCatalog(generated, definitions) {
  if (!generated || typeof generated !== 'object') {
    throw new TypeError('generated locale catalog must be an object');
  }
  return {
    messages: {
      ...generated.messages,
      nodeDefs: buildNodeDefinitions(generated.nodes, definitions),
    },
    phrases: generated.phrases,
  };
}
