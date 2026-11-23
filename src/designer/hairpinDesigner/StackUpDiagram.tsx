import { t } from "../../i18n";

/** Schematic microstrip cross-section. Thickness tracks substrate h; labels use the form text. */
export default function StackUpDiagram(props: { eps_r: string; h: string; tan_d: string }) {
  const dieH = () => {
    const n = Number(props.h.trim());
    const mm = Number.isFinite(n) ? Math.min(5, Math.max(0.1, n)) : 1.58;
    return 26 + ((mm - 0.1) / 4.9) * 48;
  };
  const copperY = 8;
  const copperH = 8;
  const dieY = copperY + copperH;
  const groundY = () => dieY + dieH();
  return (
    <figure class="hd-stack" aria-label={t("hairpinDesigner.stack.aria")}>
      <svg class="hd-stack-svg" viewBox={`0 0 168 ${Math.ceil(groundY() + 10)}`} role="img">
        <title>{t("hairpinDesigner.stack.aria")}</title>
        <rect class="hd-stack-dielectric" x="16" y={dieY} width="136" height={dieH()} />
        <rect class="hd-stack-copper" x="44" y={copperY} width="80" height={copperH} />
        <line class="hd-stack-ground" x1="12" y1={groundY()} x2="156" y2={groundY()} />
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