import { defineConfig } from 'vite'

export default defineConfig({
  root: 'frontend',
  build: {
    outDir: '../static/app',
    emptyOutDir: true,
    rollupOptions: {
      input: 'frontend/index.html',
      output: {
        entryFileNames: 'main.js',
        assetFileNames: (chunkInfo) => {
          if (chunkInfo.name && chunkInfo.name.endsWith('.css')) return 'style.css'
          return '[name][extname]'
        },
      },
    },
  },
  server: {
    port: 5173,
  },
})
