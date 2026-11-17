// CI (job dashboard-demo): every API answer listed in the demo snapshot is in the static build that Vercel deploys.
// Run from dashboard/ after `npm run build:demo`.
import { existsSync, readFileSync } from "node:fs";

const meta = JSON.parse(readFileSync("out/demo/meta.json", "utf8"));
const missing = meta.files.filter((f) => !existsSync(`out/demo/api/${f}`));
if (missing.length) {
  console.error("missing in the demo build:", missing);
  process.exit(1);
}
console.log(`demo build OK: ${meta.files.length} API answers from ${meta.edits} labelled changes`);
