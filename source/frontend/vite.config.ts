import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/** The hosted preview runs under the host's own security policy (which allows Pyodide/WebAssembly). */
const stripCspForPreview = (): Plugin => ({
  name: "strip-csp-for-preview",
  transformIndexHtml(html) {
    return process.env.VITE_PREVIEW === "1" ? html.replace(/<meta http-equiv="Content-Security-Policy"[^>]*>\s*/, "") : html;
  },
});

export default defineConfig({
  plugins: [react(), stripCspForPreview()],
  base: "./",
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8765" } },
});
