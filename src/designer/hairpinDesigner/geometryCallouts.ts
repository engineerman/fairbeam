// Where step 3 writes each hairpin key on the closed-form layout.
// Positions are millimetres in the same frame as hairpin_filter_primitives.

import type { Design } from "../types.ts";
import { paramValues } from "../expr.ts";

export type HairpinCalloutKind = "plain" | "resonator" | "spacing";

export interface HairpinCallout {
  key: string;
  value: number;
  kind: HairpinCalloutKind;
  /** 1-based resonator or spacing number. */
  index?: number;
  a: [number, number, number];
  b: [number, number, number];
  /** Dot position when the midpoint of a–b would sit on a port marker. */
  pin?: [number, number, number];
}

function read(names: Record<string, number>, key: string): number {
  const value = names[key];
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(key);
  return value;
}

/** One callout per derived layout key, sitting on the metal it measures. */
export function hairpinGeometryCallouts(design: Design): HairpinCallout[] {
  const names = paramValues(design.params ?? []).names;
  const order = Math.round(read(names, "order"));
  if (order < 1) throw new Error("order");
  const q = read(names, "q_len");
  const feed = read(names, "feed_len");
  const margin = read(names, "board_margin");
  const wFeed = read(names, "w_feed");
  const tap = read(names, "tap_from_fold");
  const h = read(names, "h");
  const z = h + 0.2;
  const x0 = -feed;
  const yFeed = read(names, "y_feed0");
  const out: HairpinCallout[] = [];
  const span = (
    key: string, value: number, kind: HairpinCalloutKind,
    a: [number, number], b: [number, number], index?: number, pin?: [number, number],
  ) => {
    out.push({
      key, value, kind, index,
      a: [a[0], a[1], z],
      b: [b[0], b[1], z],
      pin: pin ? [pin[0], pin[1], z] : undefined,
    });
  };

  for (let k = 0; k < order; k++) {
    const w = read(names, `w${k}`);
    const gap = read(names, `gap${k}`);
    const x = read(names, `x_base${k}`);
    const openDown = read(names, `open_down${k}`) >= 0.5;
    const arm = openDown ? { y0: 0, y1: Math.max(q - w, 0) } : { y0: w, y1: q };
    const armH = Math.max(arm.y1 - arm.y0, 0.2);
    const yWidth = arm.y0 + armH * 0.28;
    const yGap = arm.y0 + armH * 0.72;
    span(`w${k}`, w, "resonator", [x, yWidth], [x + w, yWidth], k + 1);
    span(`gap${k}`, gap, "resonator", [x + w, yGap], [x + w + gap, yGap], k + 1);
    if (k === 0) {
      const xArm = x + w + gap + w / 2;
      span("q_len", q, "plain", [xArm, 0], [xArm, q]);
      const yFold = openDown ? q : 0;
      const yTap = openDown ? q - tap : tap;
      span("tap_from_fold", tap, "plain", [x + w / 2, yFold], [x + w / 2, yTap]);
    }
    if (k < order - 1) {
      const sp = read(names, `sp${k}`);
      const right = x + 2 * w + gap;
      const next = read(names, `x_base${k + 1}`);
      span(`sp${k}`, sp, "spacing", [right, q / 2], [next, q / 2], k + 1);
    }
  }

  // The line runs along the feed. The dot sits beside it so the port marker can still be hovered.
  const yFeedPin = yFeed + wFeed / 2 + Math.max(1.2, wFeed * 0.65);
  span("feed_len", feed, "plain", [x0, yFeed], [0, yFeed], undefined, [-feed / 2, yFeedPin]);
  span("w_feed", wFeed, "plain", [-feed * 0.55, yFeed - wFeed / 2], [-feed * 0.55, yFeed + wFeed / 2]);
  const xEnd = read(names, "x_end");
  const xMid = (x0 + xEnd + feed) / 2;
  span("board_margin", margin, "plain", [xMid, -margin], [xMid, 0]);
  return out;
}
