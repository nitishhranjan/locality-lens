"use client";

import type { Metric } from "./types";

function format(metric: Metric): { value: string; unit: string } {
  switch (metric.unit) {
    case "score":
      return { value: String(metric.value), unit: "/100" };
    case "km2":
      return { value: metric.value.toFixed(2), unit: "km²" };
    case "per_km2":
      return { value: metric.value.toFixed(0), unit: "/km²" };
    default:
      return { value: String(metric.value), unit: "" };
  }
}

export default function MetricGrid({ metrics }: { metrics: Metric[] }) {
  if (metrics.length === 0) return null;

  return (
    <section className="panel">
      <div className="panel-head">
        <div className="panel-title">
          <span className="dot live" />
          Metrics chosen for you
        </div>
        <span className="mono-sm">{metrics.length} selected</span>
      </div>

      <div className="panel-body">
        <div className="metrics">
          {metrics.map((metric, i) => {
            const { value, unit } = format(metric);
            // Only bounded scores get a meter - a raw count has no ceiling
            // to fill, and a bar against an invented maximum would mislead.
            const isScore = metric.unit === "score";
            const tier = metric.value >= 70 ? "high" : metric.value >= 40 ? "mid" : "low";

            return (
              <div className="metric" key={metric.key} style={{ animationDelay: `${i * 45}ms` }} title={metric.about}>
                <div className="metric-label">{metric.label}</div>
                <div>
                  <span className="metric-value">{value}</span>
                  {unit && <span className="metric-unit">{unit}</span>}
                </div>
                {isScore && (
                  <div className="meter">
                    <div className="meter-fill" data-tier={tier} style={{ width: `${Math.min(100, metric.value)}%` }} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
