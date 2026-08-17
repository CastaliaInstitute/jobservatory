import { cp, mkdir } from "node:fs/promises";

await mkdir("dist/schemas", { recursive: true });
await cp("schemas", "dist/schemas", { recursive: true });
await mkdir("dist/api/ml/annotation-packages", { recursive: true });
await cp("ml/eval/independent/packages", "dist/api/ml/annotation-packages", { recursive: true });
console.log("copied public JSON Schema contracts and blind annotation packages to dist");
