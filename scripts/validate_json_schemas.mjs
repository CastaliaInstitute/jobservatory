import { readFile, readdir } from "node:fs/promises";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const pairs = [
  ["schemas/observatory.schema.json", "public/api/observatory.json"],
  ["schemas/data-card.schema.json", "public/api/data-card.json"],
  ["schemas/apocalypso-signal.schema.json", "public/api/apocalypso/jobs-signal.json"],
  ["schemas/learned-retrieval.schema.json", "public/api/ml/learned-retrieval-metrics.json"],
  ["schemas/hierarchical-classifier.schema.json", "public/api/ml/hierarchical-classifier-metrics.json"],
  ["schemas/counterfactual-audit.schema.json", "public/api/ml/counterfactual-audit.json"],
  ["schemas/release-readiness.schema.json", "public/api/ml/release-readiness.json"],
  ["schemas/production-benchmark.schema.json", "public/api/ops/production-benchmark.json"],
  ["schemas/accessibility-audit.schema.json", "public/api/ops/accessibility-audit.json"],
  ["schemas/serving-index-manifest.schema.json", "public/api/search/manifest-v1.json"],
  ["schemas/serving-index.schema.json", "public/api/search/index-v1.json"],
  ["schemas/retrieval-service-benchmark.schema.json", "public/api/ops/retrieval-service-benchmark.json"],
  ["schemas/source-rights-register.schema.json", "public/api/governance/source-rights-register.json"],
  ["schemas/source-rights-decisions.schema.json", "config/source-rights-decisions.json"],
  ["schemas/independent-evaluation-readiness.schema.json", "public/api/ml/independent-evaluation-readiness.json"],
];
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const schemaFiles = (await readdir("schemas")).filter(name => name.endsWith(".schema.json"));
for (const name of schemaFiles) ajv.addSchema(JSON.parse(await readFile(`schemas/${name}`, "utf8")));
for (const [schemaPath, artifactPath] of pairs) {
  const schema = JSON.parse(await readFile(schemaPath, "utf8"));
  const artifact = JSON.parse(await readFile(artifactPath, "utf8"));
  const validate = ajv.getSchema(schema.$id);
  if (!validate) throw new Error(`schema was not registered: ${schemaPath}`);
  if (!validate(artifact)) throw new Error(`${artifactPath} violates ${schemaPath}: ${ajv.errorsText(validate.errors, { separator: "\n" })}`);
}
console.log(`validated ${pairs.length} artifacts against JSON Schema 2020-12 contracts`);
