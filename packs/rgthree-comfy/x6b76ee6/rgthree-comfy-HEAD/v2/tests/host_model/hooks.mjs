// Maps the two value imports of the host's unmodified resolution.ts onto the test shims.
// Everything else resolves normally; `import type` lines are erased by Node's type stripping.
import { registerHooks } from 'node:module'

const SHIMS = {
  '@/lib/litegraph/src/node/slotLinks': new URL('./slotLinks.mjs', import.meta.url).href,
  '@/types/nodeId': new URL('./nodeId.mjs', import.meta.url).href,
}

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (Object.hasOwn(SHIMS, specifier)) {
      return { url: SHIMS[specifier], shortCircuit: true, format: 'module' }
    }
    return nextResolve(specifier, context)
  },
})
