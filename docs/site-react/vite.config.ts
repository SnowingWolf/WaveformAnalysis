import { defineConfig } from "vite";

export default defineConfig({
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
    process: JSON.stringify({ env: { NODE_ENV: "production" } }),
  },
  build: {
    emptyOutDir: true,
    lib: {
      entry: "src/main.tsx",
      formats: ["iife"],
      name: "WaveformDocs",
      fileName: () => "waveform-docs.js",
    },
    cssCodeSplit: false,
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
});
