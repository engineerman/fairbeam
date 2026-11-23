import type { JSX } from "solid-js";
import hairpinUrl from "../assets/hairpin-filter-home.png";

export type HairpinFilterIconProps = JSX.ImgHTMLAttributes<HTMLImageElement> & {
  /** Display width in CSS pixels (height follows the asset aspect). */
  size?: number;
};

/** Product mark: photographed hairpin bandpass on a transparent backdrop. */
export default function HairpinFilterIcon(props: HairpinFilterIconProps) {
  const { size = 160, width, height, alt, ...imgProps } = props;
  const w = () => Number(width ?? size);
  // Asset is 240×153 (2×-ish for ~120–168 CSS px tiles).
  const h = () => Number(height ?? Math.round(w() * (153 / 240)));
  return (
    <img
      {...imgProps}
      src={hairpinUrl}
      width={w()}
      height={h()}
      alt={alt ?? ""}
      draggable={false}
      aria-hidden={imgProps["aria-hidden"] ?? (alt ? undefined : true)}
    />
  );
}
