import { cp, mkdir } from "node:fs/promises";

await mkdir("dist/schemas", { recursive: true });
await cp("schemas", "dist/schemas", { recursive: true });
console.log("copied public JSON Schema contracts to dist/schemas");
