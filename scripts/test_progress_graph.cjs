const assert = require("node:assert/strict");
const { layoutGraph, safeURL } = require("../progress/app.js");
const result = layoutGraph([
  { id: "release", depends_on: ["review", "build"] },
  { id: "review", depends_on: ["build"] },
  { id: "build", depends_on: [] },
]);
assert.equal(result.positions.find((n) => n.id === "release").tier, 2);
assert.equal(result.positions.find((n) => n.id === "build").tier, 0);
assert.ok(
  result.positions.find((n) => n.id === "release").x >
    result.positions.find((n) => n.id === "review").x,
);
assert.throws(
  () =>
    layoutGraph([
      { id: "a", depends_on: ["b"] },
      { id: "b", depends_on: ["a"] },
    ]),
  /cycle/,
);
assert.throws(
  () => layoutGraph([{ id: "a", depends_on: ["absent"] }]),
  /unknown dependency/,
);
assert.throws(() => layoutGraph([{ id: "a" }, { id: "a" }]), /duplicate/);
assert.equal(safeURL("javascript:alert(1)"), null);
assert.equal(safeURL("file:///etc/passwd"), null);
assert.equal(safeURL("http://localhost:8765"), "http://localhost:8765/");
assert.equal(
  safeURL("https://github.com/ronoktanvir/uptime"),
  "https://github.com/ronoktanvir/uptime",
);
console.log(
  "Progress graph: dependency ordering, invalid graphs, and link safety passed.",
);
