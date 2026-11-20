import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/** The hosted preview runs under the host's own security policy (which allows Pyodide/WebAssembly). */
const stripCspForPreview = (): Plugin => ({
  name: "strip-csp-for-preview",
  transformIndexHtml(html) {
    return process.env.VITE_PREVIEW === "1" ? html.replace(/<meta http-equiv="Content-Security-Policy"[^>]*>\s*/, "") : html;
  },
});

/** Hosted academy: the UI (GitHub Pages) talks to the API on its own HTTPS origin. */
const cspForHosted = (): Plugin => ({
  name: "csp-for-hosted",
  transformIndexHtml(html) {
    if (process.env.VITE_HOSTED !== "1") return html;
    const api = process.env.VITE_API_BASE ?? "";
    return html.replace("connect-src 'self' http://127.0.0.1:8765", `connect-src 'self' ${api}`).replace("media-src 'self' blob: data:", `media-src 'self' blob: data: ${api}`);
  },
});

export default defineConfig({
  plugins: [react(), stripCspForPreview(), cspForHosted()],
  base: "./",
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8765" } },
});
