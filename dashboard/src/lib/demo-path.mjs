// @ts-check
// Snapshot file name for an API request in demo mode. Plain JavaScript so that CI (scripts/check_demo_build.mjs)
// can run the exact function the dashboard uses. Must match `snapshot_name()` in scripts/demo_snapshot.py; the
// cases in demo-contract.json are checked against both.

/**
 * "/summary" -> summary.json; "/decisions" {limit:"10"} -> decisions__limit-10.json;
 * "/graph" {file:"src/shop/calc.py", lines:"3-4"} -> graph__file-src_shop_calc.py__lines-3-4.json
 * @param {string} path
 * @param {Record<string, string>} [params]
 * @returns {string} the snapshot file name (no folder)
 */
export function demoName(path, params = {}) {
  let name = path.replace(/^\/+|\/+$/g, "").replaceAll("/", "_");
  for (const k of Object.keys(params).sort()) {
    name += `__${k}-${params[k]}`;
  }
  // `u`: replace whole code points, as Python's re does, not UTF-16 halves.
  return `${name.replace(/[^A-Za-z0-9._-]/gu, "_")}.json`;
}

/**
 * @param {string} path
 * @param {Record<string, string>} [params]
 * @returns {string} the URL of the snapshot file in the static build
 */
export function demoPath(path, params = {}) {
  return `/demo/api/${demoName(path, params)}`;
}
