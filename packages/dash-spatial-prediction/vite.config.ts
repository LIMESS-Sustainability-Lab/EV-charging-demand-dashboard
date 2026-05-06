import { defineConfig } from "vite";
import { resolve } from "path";

export default defineConfig({
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  build: {
    lib: {
      entry: resolve(__dirname, "src/ts/index.ts"),
      name: "dash_react_components",
      formats: ["iife"],
      fileName: () => "dash_react_components.js",
    },
    outDir: resolve(__dirname, "dash_spatial_prediction/dash_react_components"),
    emptyOutDir: false,
    rollupOptions: {
      external: ["react", "react-dom"],
      output: {
        globals: {
          react: "React",
          "react-dom": "ReactDOM",
        },
        assetFileNames: "dash_react_components.[ext]",
      },
    },
    cssCodeSplit: false,
  },
});
