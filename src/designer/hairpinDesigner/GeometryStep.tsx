import { Show, createEffect, createSignal, onCleanup, onMount } from "solid-js";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { fmt, t } from "../../i18n";
import { cssVar } from "../../lib/cssvar";
import { dimText } from "../../drawing/svg.ts";
import type { Design } from "../types.ts";
import { paramValues } from "../expr.ts";
import { quickBundle } from "../geometry.ts";
import { theme } from "../../state";
import {
  buildParts, portObject, sceneRadius, type SceneColors,
} from "../../scene/geometry.ts";
import type { PortGlyph } from "../../scene/portGlyphs.ts";
import { portMarkerRadius } from "../../scene/viewportLifecycle.ts";
import { renderPixelRatio } from "../../scene/renderBudget.ts";
import { niceLength } from "../../scene/viewportReadouts.ts";
import { viewportScaleBar } from "../../scene/viewportReadouts.ts";
import { hairpinHighlightKey, hairpinSynthesis, setHairpinHighlightKey } from "./state.ts";
import { hairpinGeometryCallouts, type HairpinCallout } from "./geometryCallouts.ts";

/** See-through filter metal. Colour stays the theme metal token (orange). */
const FILTER_OPACITY = 0.6;

interface DimSpan {
  ax: number;
  ay: number;
  bx: number;
  by: number;
}

interface DimMark extends DimSpan {
  a1x: number;
  a1y: number;
  a2x: number;
  a2y: number;
  b1x: number;
  b1y: number;
  b2x: number;
  b2y: number;
  /** Extension from the geometry end to the offset dimension line. */
  e1x: number;
  e1y: number;
  e2x: number;
  e2y: number;
  f1x: number;
  f1y: number;
  f2x: number;
  f2y: number;
  mx: number;
  my: number;
}

interface OverlayPin {
  x: number;
  y: number;
  text: string;
  port: boolean;
  key: string;
  /** Screen-space ends of the measured segment. Absent on port pins. */
  span?: DimSpan;
}

/** Offset dimension line, end ticks, and extensions. The line sits off the copper so it stays visible. */
function dimensionMark(span: DimSpan, away: { x: number; y: number }): DimMark | null {
  const dx = span.bx - span.ax;
  const dy = span.by - span.ay;
  const mag = Math.hypot(dx, dy);
  if (mag < 0.5) return null;
  const nx = -dy / mag;
  const ny = dx / mag;
  const midX = (span.ax + span.bx) / 2;
  const midY = (span.ay + span.by) / 2;
  const sign = (midX - away.x) * nx + (midY - away.y) * ny >= 0 ? 1 : -1;
  const off = 14 * sign;
  const ax = span.ax + nx * off;
  const ay = span.ay + ny * off;
  const bx = span.bx + nx * off;
  const by = span.by + ny * off;
  const tick = 5;
  return {
    ax, ay, bx, by,
    a1x: ax - nx * tick, a1y: ay - ny * tick, a2x: ax + nx * tick, a2y: ay + ny * tick,
    b1x: bx - nx * tick, b1y: by - ny * tick, b2x: bx + nx * tick, b2y: by + ny * tick,
    e1x: span.ax, e1y: span.ay, e2x: ax, e2y: ay,
    f1x: span.bx, f1y: span.by, f2x: bx, f2y: by,
    mx: (ax + bx) / 2,
    my: (ay + by) / 2,
  };
}

interface Overlay {
  pins: OverlayPin[];
  scale: { px: number; label: string } | null;
}

const EMPTY: Overlay = { pins: [], scale: null };

function sceneColors(): SceneColors {
  return {
    metal: cssVar("--al-3d-metal"),
    dielectric: cssVar("--al-3d-dielectric"),
    port: cssVar("--al-3d-port"),
    edge: cssVar("--al-3d-edge"),
    cut: cssVar("--al-3d-cutout"),
    domain: cssVar("--al-3d-domain"),
    nf2ff: cssVar("--al-3d-nf2ff"),
    ground: cssVar("--al-3d-ground"),
    grid: cssVar("--al-viewport-grid"),
    gridMajor: cssVar("--al-viewport-grid-major"),
  };
}

function designForView(design: Design): Design {
  return {
    ...design,
    parts: design.parts.map((part) => (part.name === "filter" ? { ...part, opacity: FILTER_OPACITY } : part)),
  };
}

function calloutText(row: HairpinCallout): string {
  const value = dimText(row.value);
  if (row.kind === "resonator") return t("hairpinDesigner.dim.resonator", { key: row.key, n: String(row.index ?? ""), value });
  if (row.kind === "spacing") return t("hairpinDesigner.dim.spacing", { key: row.key, n: String(row.index ?? ""), value });
  return t("hairpinDesigner.dim.value", { key: row.key, value });
}

export function HairpinModelView(props: { design: Design }) {
  let host!: HTMLDivElement;
  const [overlay, setOverlay] = createSignal<Overlay>(EMPTY);
  const [note, setNote] = createSignal("");
  const marks = () => {
    const away = { x: host?.clientWidth / 2 || 0, y: host?.clientHeight / 2 || 0 };
    return overlay().pins.flatMap((pin) => {
      if (!pin.span) return [];
      const mark = dimensionMark(pin.span, away);
      return mark ? [{ ...mark, key: pin.key }] : [];
    });
  };
  const popup = () => {
    const pin = overlay().pins.find((row) => row.key === hairpinHighlightKey());
    if (!pin) return null;
    const mark = marks().find((row) => row.key === pin.key);
    return { ...pin, x: mark?.mx ?? pin.x, y: mark?.my ?? pin.y };
  };

  onMount(() => {
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.setPixelRatio(renderPixelRatio(window.devicePixelRatio, false));
    renderer.domElement.className = "vp-canvas";
    host.prepend(renderer.domElement);

    const lutListeners: Array<{ texture: THREE.Texture; listener: (...args: unknown[]) => void }> = [];
    const textureEvents = THREE.Texture.prototype as unknown as {
      addEventListener(type: string, listener: (...args: unknown[]) => void): void;
      removeEventListener(type: string, listener: (...args: unknown[]) => void): void;
    };
    const trackLut = <T,>(run: () => T): T => {
      if (lutListeners.length) return run();
      const original = textureEvents.addEventListener;
      textureEvents.addEventListener = function (this: THREE.Texture, type, listener) {
        if (type === "dispose" && this.name === "DFG_LUT") lutListeners.push({ texture: this, listener });
        original.call(this, type, listener);
      };
      try { return run(); }
      finally { textureEvents.addEventListener = original; }
    };

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1, 0.05, 1e6);
    camera.up.set(0, 0, 1);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;
    controls.screenSpacePanning = true;
    controls.zoomToCursor = true;
    controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.PAN, RIGHT: THREE.MOUSE.PAN };

    const pmrem = new THREE.PMREMGenerator(renderer);
    const room = new RoomEnvironment();
    const env = trackLut(() => pmrem.fromScene(room, 0.04)).texture;
    room.dispose();
    scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 0.9));
    const sun = new THREE.DirectionalLight(0xffffff, 1.4);
    sun.position.set(0.6, -0.8, 1.2);
    scene.add(sun);

    const partsRoot = new THREE.Group();
    const overlayRoot = new THREE.Group();
    scene.add(partsRoot, overlayRoot);
    let glyphs: PortGlyph[] = [];
    let grid: THREE.GridHelper | null = null;
    let callouts: HairpinCallout[] = [];
    let bundlePorts: { number: number; type: string; R?: number; anchor: THREE.Vector3 }[] = [];
    let frame = 0;
    let framed = false;
    let sceneRadiusNow = { radius: 1, center: new THREE.Vector3() };

    const project = (v: THREE.Vector3) => {
      const p = v.clone().project(camera);
      const w = host.clientWidth;
      const h = host.clientHeight;
      if (p.z < -1 || p.z > 1) return null;
      return { x: (p.x * 0.5 + 0.5) * w, y: (-p.y * 0.5 + 0.5) * h };
    };

    const placeOverlay = () => {
      const pins: OverlayPin[] = [];
      for (const row of callouts) {
        const a = project(new THREE.Vector3(...row.a));
        const b = project(new THREE.Vector3(...row.b));
        if (!a || !b) continue;
        pins.push({
          key: row.key,
          text: calloutText(row),
          port: false,
          x: (a.x + b.x) / 2,
          y: (a.y + b.y) / 2,
          span: { ax: a.x, ay: a.y, bx: b.x, by: b.y },
        });
      }
      for (const port of bundlePorts) {
        const at = project(port.anchor);
        if (!at) continue;
        const planar = port.type === "microstrip" || port.type === "cpw";
        const kind = port.type === "cpw" ? "props.port.cpw" : "props.port.microstrip";
        const text = `P${port.number}${planar ? " · " + t(kind) : ""} · ${fmt.num(port.R ?? 0, 6)} Ω`;
        pins.push({ key: `port${port.number}`, text, port: true, x: at.x, y: at.y });
      }
      let scale: Overlay["scale"] = null;
      const origin = controls.target.clone();
      const right = origin.clone();
      right.x += 1;
      const p0 = project(origin);
      const p1 = project(right);
      if (p0 && p1) {
        const px = Math.hypot(p1.x - p0.x, p1.y - p0.y);
        if (px > 1e-3) scale = viewportScaleBar(1 / px, 1);
      }
      setOverlay({ pins, scale });
    };

    const requestRender = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const dist = camera.position.distanceTo(controls.target);
        const wpp = (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) * dist) / Math.max(host.clientHeight, 1);
        for (const g of glyphs) g.userData.update(wpp);
        trackLut(() => renderer.render(scene, camera));
        placeOverlay();
      });
    };

    const fitTop = (radius: number, center: THREE.Vector3) => {
      const aspect = Math.max(host.clientWidth / Math.max(host.clientHeight, 1), 0.01);
      camera.aspect = aspect;
      const fov = THREE.MathUtils.degToRad(camera.fov);
      const dist = (radius / Math.sin(fov / 2)) * 1.22 * Math.max(1, 1 / aspect);
      const dir = new THREE.Vector3(0, -0.0001, 1).normalize();
      camera.position.copy(center).addScaledVector(dir, dist);
      camera.near = Math.max(dist / 500, 0.01);
      camera.far = dist * 200;
      camera.updateProjectionMatrix();
      controls.target.copy(center);
      controls.update();
    };

    const resize = () => {
      const w = Math.max(host.clientWidth, 1);
      const h = Math.max(host.clientHeight, 1);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      if (!framed && host.clientWidth > 8 && host.clientHeight > 8) {
        framed = true;
        fitTop(sceneRadiusNow.radius, sceneRadiusNow.center);
      }
      requestRender();
    };

    const disposeObject = (obj: THREE.Object3D, keepGeometry: boolean) => {
      obj.traverse((node) => {
        const mesh = node as THREE.Mesh;
        if (!keepGeometry) mesh.geometry?.dispose?.();
        const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(material)) material.forEach((m) => m.dispose());
        else material?.dispose();
      });
    };

    const rebuild = () => {
      for (const child of [...partsRoot.children]) {
        partsRoot.remove(child);
        disposeObject(child, false);
      }
      for (const child of [...overlayRoot.children]) {
        overlayRoot.remove(child);
        disposeObject(child, true);
      }
      if (grid) {
        scene.remove(grid);
        grid.geometry.dispose();
        const materials = Array.isArray(grid.material) ? grid.material : [grid.material];
        materials.forEach((m) => m.dispose());
        grid = null;
      }
      glyphs = [];
      bundlePorts = [];
      callouts = [];
      setNote("");

      const names = paramValues(props.design.params ?? []).names;
      const built = quickBundle(designForView(props.design), names, null);
      if (!built) {
        setNote(t("hairpinDesigner.geometry.missing"));
        requestRender();
        return;
      }
      try { callouts = hairpinGeometryCallouts(props.design); }
      catch { setNote(t("hairpinDesigner.geometry.missing")); }

      const colors = sceneColors();
      scene.background = new THREE.Color(cssVar("--al-viewport"));
      const parts = buildParts(built, colors, env, false);
      for (const part of parts) {
        if (part.part.name === "filter") {
          for (const mesh of part.meshes) mesh.renderOrder = 2;
          for (const edge of part.edges) edge.renderOrder = 3;
        }
        partsRoot.add(part.group);
      }
      const fitted = sceneRadius(built);
      sceneRadiusNow = { radius: fitted.radius, center: fitted.center.clone() };
      framed = false;
      const portR = portMarkerRadius(fitted.radius, built.mesh?.x ?? []);
      for (const port of built.ports ?? []) {
        const planar = port.type === "microstrip" || port.type === "cpw";
        const k = "xyz".indexOf(port.direction);
        const sign = Math.sign(port.stop[k] - port.start[k]) || 1;
        const from = port.start.map((v, j) => j === k ? (port.actual_source_plane ?? v + sign * (port.feed_shift ?? 0)) : (v + port.stop[j]) / 2) as [number, number, number];
        const to = from.map((v, j) => j === k ? (port.reference_plane ?? port.start[k] + sign * (port.measurement_shift ?? 0)) : v) as [number, number, number];
        const glyph = portObject(planar ? from : port.start, planar ? to : port.stop, colors.port, portR, port.direction);
        glyphs.push(glyph);
        overlayRoot.add(glyph);
        bundlePorts.push({ number: port.number, type: port.type, R: port.R, anchor: glyph.userData.labelAnchor });
      }
      const ext = fitted.radius * 3;
      const step = niceLength(ext / 16);
      const divisions = Math.max(2, Math.round(ext / step));
      grid = new THREE.GridHelper(divisions * step, divisions, colors.gridMajor, colors.grid);
      grid.rotation.x = Math.PI / 2;
      grid.position.set(fitted.center.x, fitted.center.y, (built.focus?.min[2] ?? 0) - 0.2);
      const gridMat = Array.isArray(grid.material) ? grid.material : [grid.material];
      for (const material of gridMat) material.transparent = true;
      scene.add(grid);
      resize();
    };

    const onControls = () => requestRender();
    controls.addEventListener("change", onControls);
    const observer = new ResizeObserver(() => resize());
    observer.observe(host);
    createEffect(() => {
      theme();
      rebuild();
    });

    onCleanup(() => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.removeEventListener("change", onControls);
      controls.dispose();
      for (const { texture, listener } of lutListeners) texture.removeEventListener("dispose", listener);
      env.dispose();
      pmrem.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    });
  });

  return (
    <div class="viewport hd-stage" ref={host} role="group" aria-label={t("hairpinDesigner.geometry.aria")}>
      <div class="vp-labels">
        <svg class="hd-dim" aria-hidden="true">
          {marks().map((mark) => (
            <g
              class="hd-dim-item"
              classList={{ "hd-dim-item-active": mark.key === hairpinHighlightKey() }}
              data-dim={mark.key}
              onPointerEnter={() => setHairpinHighlightKey(mark.key)}
              onPointerLeave={() => setHairpinHighlightKey((cur) => (cur === mark.key ? null : cur))}
            >
              <line class="hd-dim-hit" x1={mark.ax} y1={mark.ay} x2={mark.bx} y2={mark.by} />
              <g class="hd-dim-stroke">
                <line x1={mark.e1x} y1={mark.e1y} x2={mark.e2x} y2={mark.e2y} />
                <line x1={mark.f1x} y1={mark.f1y} x2={mark.f2x} y2={mark.f2y} />
                <line x1={mark.ax} y1={mark.ay} x2={mark.bx} y2={mark.by} />
                <line x1={mark.a1x} y1={mark.a1y} x2={mark.a2x} y2={mark.a2y} />
                <line x1={mark.b1x} y1={mark.b1y} x2={mark.b2x} y2={mark.b2y} />
              </g>
            </g>
          ))}
        </svg>
        {overlay().pins.filter((pin) => pin.port).map((pin) => (
          <button
            type="button"
            class="hd-port-hit"
            data-dim={pin.key}
            aria-label={pin.text}
            style={{ left: `${pin.x}px`, top: `${pin.y}px` }}
            onPointerEnter={() => setHairpinHighlightKey(pin.key)}
            onPointerLeave={() => setHairpinHighlightKey((cur) => (cur === pin.key ? null : cur))}
            onFocus={() => setHairpinHighlightKey(pin.key)}
            onBlur={() => setHairpinHighlightKey((cur) => (cur === pin.key ? null : cur))}
          />
        ))}
        <Show when={popup()}>
          {(pin) => (
            <div class="hd-pin hd-pin-active" style={{ left: `${pin().x}px`, top: `${pin().y}px` }}>
              <span class={pin().port ? "vp-label vp-label-port" : "vp-label"}>{pin().text}</span>
            </div>
          )}
        </Show>
      </div>
      <Show when={overlay().scale}>
        {(scale) => (
          <div class="vp-hud vp-hud-br">
            <span class="readout"><span class="scalebar" style={{ width: `${scale().px}px` }}><span>{scale().label}</span></span></span>
          </div>
        )}
      </Show>
      <Show when={note()}><p class="hd-stage-note">{note()}</p></Show>
    </div>
  );
}

export default function GeometryStep() {
  const design = () => hairpinSynthesis()?.design ?? null;
  return (
    <Show when={design()} fallback={<p class="muted">{t("hairpinDesigner.geometry.missing")}</p>}>
      {(d) => <HairpinModelView design={d()} />}
    </Show>
  );
}
