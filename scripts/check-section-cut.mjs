// The Z section cut: which slider values cut the model, which points survive the cut, and the one plane
// array every clipped material shares.
//   node --experimental-strip-types scripts/check-section-cut.mjs
import assert from "node:assert/strict";
import { buildParts } from "../src/scene/geometry.ts";
import { sectionClippingPlanes, sectionCutZ, sectionKeepsPoint, syncSectionPlane } from "../src/scene/sectionCut.ts";

const domain = { min: [-10, -10, -2], max: [10, 10, 4] };

assert.equal(sectionCutZ(domain, null), null, "no value is the whole model");
assert.equal(sectionCutZ(domain, Number.NaN), null, "NaN is the whole model");
assert.equal(sectionCutZ({ min: [0, 0, 1], max: [1, 1, 1] }, 1), null, "a flat domain never cuts");
assert.equal(sectionCutZ(domain, 4), null, "the domain top is the whole model");
assert.equal(sectionCutZ(domain, 9), null, "above the domain is the whole model");
assert.equal(sectionCutZ(domain, -7), -2, "below the domain clamps to the floor");
assert.equal(sectionCutZ(domain, 1), 1, "a midpoint cuts where it is");

assert.equal(sectionKeepsPoint(null, 5), true, "no cut keeps everything");
assert.equal(sectionKeepsPoint(1.5, 1.5), true, "a point on the plane is kept");
assert.equal(sectionKeepsPoint(1.5, 1.5 - 1e-12), true, "a point just below is kept");
assert.equal(sectionKeepsPoint(1.5, 2), false, "a point above the plane is cut away");

const planes = sectionClippingPlanes();
syncSectionPlane(null);
assert.equal(sectionClippingPlanes(), planes, "one shared array");
assert.equal(planes.length, 0, "whole model: nothing clips");

syncSectionPlane(1.5);
assert.equal(sectionClippingPlanes(), planes, "the same array after a cut");
assert.equal(planes.length, 1);
const [plane] = planes;
assert.equal(plane.constant, 1.5);
assert.deepEqual([plane.normal.x, plane.normal.y, plane.normal.z], [0, 0, -1]);
assert.ok(plane.distanceToPoint({ x: 0, y: 0, z: 1 }) > 0 && plane.distanceToPoint({ x: 0, y: 0, z: 2 }) < 0,
  "three.js keeps the positive side: below the cut stays, above is clipped");

syncSectionPlane(0.25);
assert.equal(sectionClippingPlanes(), planes, "the same array after a second cut");
assert.equal(planes[0], plane, "the same plane object after a second cut");
assert.equal(planes[0].constant, 0.25);

syncSectionPlane(null);
assert.equal(planes.length, 0, "turning the cut off empties the shared array");

// every solid the 3D view draws follows the cut, including a part's second shape (its own material clone),
// approximated shapes (wireframes) and cut-outs
const shape = { kind: "linpoly", normal: 2, elevation: 0, length: 1, points: [[0, 0], [4, 0], [4, 3]], priority: 1, bbox: [[0, 0, 0], [4, 3, 1]], exact: true };
const built = buildParts({ parts: [
  { name: "strip", type: "Metal", bbox: shape.bbox, primitives: [shape, { ...shape, elevation: 2 }, { ...shape, exact: false }] },
  { name: "hole", type: "Metal", void: true, bbox: shape.bbox, primitives: [shape] },
] }, { metal: "#b87333", dielectric: "#ffffff", edge: "#000000", cut: "#0000ff" }, null, false);
const materials = [];
for (const p of built) p.group.traverse((o) => o.material && materials.push(o.material));
assert.ok(materials.length >= 8, "solids, edges, the wireframe and the cut-out passes were built");
for (const m of materials) assert.equal(m.clippingPlanes, planes, `${m.type} holds the shared plane array`);

console.log("section cut checks passed");
