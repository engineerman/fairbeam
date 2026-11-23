import DimensionTable from "./DimensionTable.tsx";
import GeometryStep from "./GeometryStep.tsx";
import PreviewPlot from "./PreviewPlot.tsx";
import SolveStep from "./SolveStep.tsx";

/** One Önizleme screen: compact geometry, ideal S, dimensions, and the commit method. */
export default function PreviewStep() {
  return (
    <div class="hd-preview">
      <div class="hd-preview-col">
        <div class="hd-preview-geom">
          <GeometryStep />
        </div>
        <DimensionTable />
      </div>
      <div class="hd-preview-col">
        <div class="hd-preview-plot-wrap">
          <PreviewPlot />
        </div>
        <SolveStep />
      </div>
    </div>
  );
}
