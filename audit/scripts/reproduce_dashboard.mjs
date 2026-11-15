// Exercise the actual canvas-sizing function without browser dependencies.
// Usage: node reproduce_dashboard.mjs /path/to/AI-SDN-Traffic-Management
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

assert.ok(process.argv[2], "Usage: node reproduce_dashboard.mjs /path/to/AI-SDN-Traffic-Management");
const html = fs.readFileSync(path.join(process.argv[2], "index.html"), "utf8");
const source = html.match(/function setupCanvas\(canvas\) \{[\s\S]*?\n\}/)?.[0];
assert.ok(source, "setupCanvas function must be present");
const context = vm.createContext({ window: { devicePixelRatio: 2 } });
vm.runInContext(source, context);
const canvas = {
  parentElement: { clientWidth: 600 },
  height: 220,
  style: {},
  dataset: {},
  getAttribute(name) { return String(this[name]); },
  getContext() { return { setTransform() {} }; },
};
const heights = [];
for (let i = 0; i < 3; i++) {
  context.setupCanvas(canvas);
  heights.push({ css: canvas.style.height, backing: canvas.height });
}
if (heights.every(h => h.css === "220px" && h.backing === 440)) {
  console.log("FIX VERIFIED: repeated DPR=2 redraws keep the logical and backing heights stable:", heights);
} else {
  assert.deepEqual(heights.map(h => h.css), ["220px", "440px", "880px"]);
  console.log("BUG REPRODUCED: on DPR=2 displays, each redraw doubles the chart height:", heights);
}
