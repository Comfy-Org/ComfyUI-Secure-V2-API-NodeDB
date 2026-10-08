import { resolve } from 'node:path'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: {
    '@/base/credits/comfyCredits': resolve('packages/shared-frontend-utils/src/creditsUtil.ts'),
    '@/utils/formatUtil': resolve('packages/shared-frontend-utils/src/formatUtil.ts'),
    '@/utils/networkUtil': resolve('packages/shared-frontend-utils/src/networkUtil.ts'),
    '@': resolve('src')
  } },
  define: {
    __COMFYUI_FRONTEND_VERSION__: JSON.stringify('acceptance-test'),
    __COMFYUI_FRONTEND_COMMIT__: JSON.stringify(process.env.AUTHOR_FRONTEND_COMMIT),
    __SENTRY_DSN__: JSON.stringify(''),
    __ALGOLIA_APP_ID__: JSON.stringify(''),
    __ALGOLIA_API_KEY__: JSON.stringify(''),
    __USE_PROD_CONFIG__: false,
    __DISTRIBUTION__: JSON.stringify('localhost'),
    __IS_NIGHTLY__: false
  },
  server: { host: '127.0.0.1', port: Number(process.env.AUTHOR_BROWSER_PORT), strictPort: true, cors: true }
})
