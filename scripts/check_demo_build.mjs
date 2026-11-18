// CI (job dashboard-demo): the static demo build that Vercel deploys answers every request the dashboard makes.
// Run from dashboard/ after `npm run build:demo`. Checks, using the dashboard's own naming function:
//   1. demoName() gives the names listed in demo-contract.json (scripts/demo_snapshot.py is tested against the
//      same list in tests/test_demo_snapshot.py, so the two implementations cannot drift apart);
//   2. every request the pages make (contract `requests`) has its file in out/;
//   3. every file the system map or a graph links to has its graph in out/ (each node opens /graph?file=...).
import { existsSync, readFileSync } from "node:fs";
import { demoName } from "../dashboard/src/lib/demo-path.mjs";

const contract = JSON.parse(readFileSync(new URL("../dashboard/src/lib/demo-contract.json", import.meta.url), "utf8"));
const problems = [];

for (const [path, params, want] of contract.names) {
  const got = demoName(path, params);
  if (got !== want) problems.push(`demoName(${path}, ${JSON.stringify(params)}) = ${got}, expected ${want}`);
}

const file = (path, params = {}) => `out/demo/api/${demoName(path, params)}`;
const read = (path, params) => JSON.parse(readFileSync(file(path, params), "utf8"));
for (const [path, params] of contract.requests) {
  if (!existsSync(file(path, params))) problems.push(`missing ${file(path, params)} (${path} ${JSON.stringify(params)})`);
}

const links = (graph) => (graph.nodes ?? []).map((n) => n.id).filter((id) => id && id !== "?");
let graphs = 0;
if (existsSync(file("/map"))) {
  const todo = links(read("/map"));
  const seen = new Set();
  while (todo.length) {
    const f = todo.pop();
    if (seen.has(f)) continue;
    seen.add(f);
    if (!existsSync(file("/graph", { file: f }))) {
      problems.push(`missing graph for ${f}: ${file("/graph", { file: f })}`);
      continue;
    }
    graphs += 1;
    todo.push(...links(read("/graph", { file: f })));
  }
}

if (problems.length) {
  console.error("demo build problems:\n  " + problems.join("\n  "));
  process.exit(1);
}
console.log(`demo build OK: ${contract.requests.length} page requests and ${graphs} graphs served`);
