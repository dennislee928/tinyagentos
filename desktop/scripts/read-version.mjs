// Reads __version__ from ../tinyagentos/__init__.py at Vite build time.
// Single source of truth with the backend.
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const initPath = resolve(HERE, "..", "..", "tinyagentos", "__init__.py");

export function readBackendVersion() {
  try {
    const src = readFileSync(initPath, "utf8");
    const m = src.match(/^\s*__version__\s*=\s*['"]([^'"]+)['"]/m);
    return m ? m[1] : "dev";
  } catch {
    return "dev";
  }
}
