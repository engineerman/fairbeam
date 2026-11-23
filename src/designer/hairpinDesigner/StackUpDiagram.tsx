import { t } from "../../i18n";

export type StackUpKind = "microstrip" | "stripline";

/** Schematic stack cross-section. Thickness tracks form h; labels use the form text. */
export default function StackUpDiagram(props: {
  kind: StackUpKind;
  eps_r: string;
  h: string;
  tan_d: string;
}) {
  const dieH = () => {
    const n = Number(props.h.trim());
    const mm = Number.isFinite(n) ? Math.min(5, Math.max(0.1, n)) : 1.58;
    return 26 + ((mm - 0.1) / 4.9) * 48;
  };
  const copperH = 8;
  const ariaKey = () =>
    props.kind === "stripline" ? "hairpinDesigner.stack.ariaStripline" : "hairpinDesigner.stack.aria";

  const layout = () => {
    const h = dieH();
    if (props.kind === "stripline") {
      // Dielectric −b/2…+b/2, grounds at ±b/2, center strip at midplane (z = 0).
      const pad = 10;
      return {
        kind: "stripline" as const,
        height: Math.ceil(pad + h + 10),
        dieY: pad,
        dieH: h,
        topGroundY: pad,
        bottomGroundY: pad + h,
        copperY: pad + h / 2 - copperH / 2,
      };
    }
    const copperY = 8;
    const dieY = copperY + copperH;
    const groundY = dieY + h;
    return {
      kind: "microstrip" as const,
      height: Math.ceil(groundY + 10),
      dieY,
      dieH: h,
      groundY,
      copperY,
    };
  };

  return (
    <figure class="hd-stack" data-stack-kind={props.kind} aria-label={t(ariaKey())}>
      <svg class="hd-stack-svg" viewBox={`0 0 168 ${layout().height}`} role="img">
        <title>{t(ariaKey())}</title>
        <rect class="hd-stack-dielectric" x="16" y={layout().dieY} width="136" height={layout().dieH} />
        {layout().kind === "stripline" ? (
          <>
            <line class="hd-stack-ground" x1="12" y1={layout().topGroundY} x2="156" y2={layout().topGroundY} />
            <rect class="hd-stack-copper" x="44" y={layout().copperY} width="80" height={copperH} />
            <line class="hd-stack-ground" x1="12" y1={layout().bottomGroundY} x2="156" y2={layout().bottomGroundY} />
          </>
        ) : (
          <>
            <rect class="hd-stack-copper" x="44" y={layout().copperY} width="80" height={copperH} />
            <line class="hd-stack-ground" x1="12" y1={layout().groundY} x2="156" y2={layout().groundY} />
          </>
        )}
      </svg>
      <ul class="hd-stack-labels">
        <li>Cu</li>
        <li>εr = {props.eps_r}</li>
        <li>h = {props.h} mm</li>
        <li>tan δ = {props.tan_d}</li>
      </ul>
    </figure>
  );
}
