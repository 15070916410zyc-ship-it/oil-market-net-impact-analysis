import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";

type EChartViewProps = {
  option: EChartsOption;
  className?: string;
  height?: number | string;
  ariaLabel: string;
  resetKey?: string;
};

export function EChartView({ option, className = "", height = 360, ariaLabel, resetKey }: EChartViewProps) {
  return (
    <div className={`echart-view ${className}`.trim()} role="img" aria-label={ariaLabel}>
      <ReactECharts
        key={resetKey}
        option={option}
        notMerge
        lazyUpdate
        style={{ height, width: "100%" }}
        opts={{ renderer: "canvas" }}
      />
    </div>
  );
}
