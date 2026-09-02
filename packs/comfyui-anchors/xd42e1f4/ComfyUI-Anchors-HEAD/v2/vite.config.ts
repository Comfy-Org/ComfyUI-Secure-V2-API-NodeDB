import { resolve } from 'node:path';
import { defineConfig, loadEnv } from 'vite';
import dts from 'vite-plugin-dts';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd());
  console.log(env);
  return {
    build: {
      lib: {
        entry: resolve(__dirname, 'lib/anchor.ts'),
        name: 'comfyui-anchors',
        formats: ['es'],
        fileName: `comfyui-anchors`,
      },
      rollupOptions: {
        external: ['/comfy/api/v2.js'],
      },
    },
    plugins: [dts({ include: ['lib'] })],
  };
});
