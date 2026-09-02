/** Bundled locale metadata, mapped onto ComfyUI's canonical locale ids. */
export const LOCALES = Object.freeze({
  zh: Object.freeze({
    legacyId: 'zh-CN',
    nativeName: '中文',
    englishName: 'Chinese Simplified',
  }),
  'zh-TW': Object.freeze({
    legacyId: 'zh-TW',
    nativeName: '繁體中文',
    englishName: 'Traditional Chinese',
  }),
  ja: Object.freeze({
    legacyId: 'ja-JP',
    nativeName: '日本語',
    englishName: 'Japanese',
  }),
  ko: Object.freeze({
    legacyId: 'ko-KR',
    nativeName: '한국어 (韓國)',
    englishName: 'Korean (Korea)',
  }),
  ru: Object.freeze({
    legacyId: 'ru-RU',
    nativeName: 'Русский',
    englishName: 'Russian',
  }),
});

export const LEGACY_TO_HOST_LOCALE = Object.freeze({
  'zh-CN': 'zh',
  'zh-TW': 'zh-TW',
  'ja-JP': 'ja',
  'ko-KR': 'ko',
  'ru-RU': 'ru',
  'en-US': 'en',
});

export const SUPPORTED_LOCALES = Object.freeze(Object.keys(LOCALES));

export function canonicalLocale(value) {
  if (typeof value !== 'string') return 'en';
  return LEGACY_TO_HOST_LOCALE[value] ??
    (SUPPORTED_LOCALES.includes(value) ? value : 'en');
}
