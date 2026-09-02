export function secureLog(enabled, ...values) {
  if (enabled) console.log('[cg-image-filter]', ...values);
}
