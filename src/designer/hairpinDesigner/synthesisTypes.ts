// Body and result of POST /api/filter-synthesis for the hairpin wizard.
import type { Design } from "../types.ts";

/** chebyshev | butterworth | equiripple. Equiripple ripple is not Chebyshev passband ripple. */
export type FilterSynthesisResponseKind = "chebyshev" | "butterworth" | "equiripple";

export interface FilterSynthesisRequest {
  topology: "hairpin_microstrip_bp";
  electrical?: {
    f0_hz?: number;
    bw_hz?: number;
    order?: number;
    ripple_db?: number;
    response?: FilterSynthesisResponseKind;
    z0?: number;
  };
  stack?: {
    stack_kind?: "microstrip";
    eps_r?: number;
    thickness_mm?: number;
    tan_d?: number;
  };
  layout?: {
    feed_len_mm?: number;
    board_margin_mm?: number;
    intra_gap_mm?: number;
  };
  preview_only?: boolean;
}

export interface FilterSynthesisPreview {
  f_hz: number[];
  s11_db: number[];
  s21_db: number[];
  s11_deg?: number[];
  s21_deg?: number[];
  s21_group_delay_ns?: number[];
}

export interface FilterSynthesisResponse {
  /** Present when preview_only is false. */
  design?: Design;
  preview?: FilterSynthesisPreview;
  dimensions?: Array<{ key: string; value: number; unit?: string; label?: string }>;
  caveats?: string[];
}
