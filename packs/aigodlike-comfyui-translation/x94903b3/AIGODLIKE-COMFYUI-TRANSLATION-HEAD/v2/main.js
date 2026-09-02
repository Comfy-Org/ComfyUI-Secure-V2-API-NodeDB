import { comfy } from '/comfy/api/v2.js';

import { canonicalLocale, SUPPORTED_LOCALES } from './LocaleMap.js';
import { buildNativeCatalog } from './MenuTranslate.js';


export const EXTENSION_NAME = 'AIGODLIKE.Translation';
const CORE_LOCALE_SETTING = 'Comfy.Locale';
const LAST_LOCALE_KEY = 'AIGODLIKE.Translation/last-locale';

const LOADERS = Object.freeze({
  zh: () => import('./catalogs/zh.js'),
  'zh-TW': () => import('./catalogs/zh-TW.js'),
  ja: () => import('./catalogs/ja.js'),
  ko: () => import('./catalogs/ko.js'),
  ru: () => import('./catalogs/ru.js'),
});

const registered = new Set();
let lastNonEnglish = 'zh';

async function rememberLocale(locale) {
  if (!SUPPORTED_LOCALES.includes(locale)) return;
  lastNonEnglish = locale;
  try {
    await comfy.storage.set(LAST_LOCALE_KEY, locale);
  } catch (_error) {
    // A storage quota failure must not stop locale registration.
  }
}

async function registerLocale(value) {
  const locale = canonicalLocale(value);
  if (locale === 'en' || registered.has(locale)) return;
  const loader = LOADERS[locale];
  if (loader === undefined) return;

  const module = await loader();
  const catalog = buildNativeCatalog(module.default, comfy.defs.all());
  comfy.localization.registerCatalog(locale, catalog);
  registered.add(locale);
}

async function initialize() {
  try {
    const stored = canonicalLocale(await comfy.storage.get(LAST_LOCALE_KEY));
    if (stored !== 'en') lastNonEnglish = stored;
  } catch (_error) {
    // The core locale setting remains the source of truth.
  }

  // Prime the synchronous cache for this core-owned setting. Its first read in
  // a sandbox intentionally answers undefined while the host backfills it.
  comfy.settings.get(CORE_LOCALE_SETTING);

  // Catalogs are static data and total under 1.8 MiB. Registering all five
  // once avoids a flash of English and makes the first locale selection work
  // even before the asynchronous core-setting cache has been backfilled.
  await Promise.all(SUPPORTED_LOCALES.map(registerLocale));

  const current = canonicalLocale(comfy.settings.get(CORE_LOCALE_SETTING));
  if (current !== 'en') await rememberLocale(current);

  comfy.settings.onChange(CORE_LOCALE_SETTING, (value) => {
    const locale = canonicalLocale(value);
    void registerLocale(locale);
    void rememberLocale(locale);
  });

  comfy.ui.addActionBarButton({
    id: 'AIGODLIKE.Translation.switchLocale',
    icon: 'icon-[lucide--languages]',
    label: 'Switch locale',
    tooltip: 'Switch between English and the last translated locale',
    run: () => {
      const locale = canonicalLocale(comfy.settings.get(CORE_LOCALE_SETTING));
      void comfy.settings.set(
        CORE_LOCALE_SETTING,
        locale === 'en' ? lastNonEnglish : 'en',
      );
    },
  });
}

await initialize();
