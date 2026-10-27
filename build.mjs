// Rebuild the front end:  npm install && npm run build   (needs Node 18+; Termux: pkg install nodejs)
import { build } from "esbuild";
await build({
  entryPoints: { app: "src/main.jsx" }, outdir: "static", bundle: true, minify: true, sourcemap: false,
  target: ["es2019", "chrome90", "safari14"], jsx: "automatic", loader: { ".png": "dataurl" },
  define: { "process.env.NODE_ENV": '"production"' }, legalComments: "none", logLevel: "info",
});
