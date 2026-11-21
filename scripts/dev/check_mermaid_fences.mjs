// Offline mermaid check for a markdown page's ```mermaid fences.
// Uses the frontend's own vendored mermaid + jsdom — no browser, no network.
// Usage: node scripts/dev/check_mermaid_fences.mjs <file.md> [more.md ...]
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

// Resolution follows the SCRIPT's path, so require from the frontend's package.json.
const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(resolve(here, "../../frontend/package.json"));

const { JSDOM } = require("jsdom");
const dom = new JSDOM("<!doctype html><html><body></body></html>");
for (const k of ["window", "document", "navigator", "Element", "HTMLElement", "Node", "DOMParser"]) {
  globalThis[k] = k === "window" ? dom.window : dom.window[k];
}

const mermaid = (await import(require.resolve("mermaid"))).default;
mermaid.initialize({ startOnLoad: false });

const fences = (text) => {
  const out = [];
  const re = /```mermaid\n([\s\S]*?)```/g;
  let m;
  while ((m = re.exec(text))) out.push(m[1]);
  return out;
};

let failures = 0;
for (const file of process.argv.slice(2)) {
  const blocks = fences(readFileSync(file, "utf8"));
  if (!blocks.length) {
    console.log(`${file}: no mermaid fences`);
    continue;
  }
  for (const [i, code] of blocks.entries()) {
    try {
      await mermaid.parse(code);
      console.log(`${file} fig.${i + 1}: OK`);
    } catch (err) {
      failures += 1;
      console.log(`${file} fig.${i + 1}: FAIL — ${err.message.split("\n")[0]}`);
    }
  }
}
process.exit(failures ? 1 : 0);
