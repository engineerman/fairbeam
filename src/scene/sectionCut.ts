import * as THREE from "three";

const EPS = 1e-9;
const plane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
const planes: THREE.Plane[] = [];

/** The world-Z cut a slider value resolves to: null at the domain top or above (the whole model, clipping off),
 *  the domain floor at or below it. */
export function sectionCutZ(domain: { min: readonly number[]; max: readonly number[] }, z: number | null): number | null {
  const lo = domain.min[2], hi = domain.max[2];
  if (z === null || !Number.isFinite(z) || !(hi > lo)) return null;
  if (z >= hi - Math.max((hi - lo) * 1e-6, EPS)) return null;
  return z <= lo ? lo : z;
}

export function sectionKeepsPoint(cutZ: number | null, pointZ: number): boolean {
  return cutZ === null || pointZ <= cutZ + EPS;
}

/** The one array every clipped material holds; materials see a new cut without being touched. */
export function sectionClippingPlanes(): THREE.Plane[] {
  return planes;
}

export function syncSectionPlane(cutZ: number | null): void {
  if (cutZ === null) { planes.length = 0; return; }
  plane.constant = cutZ;
  planes.length = 0;
  planes.push(plane);
}
