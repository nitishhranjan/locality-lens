"use client";

import type { Stage } from "./types";

function Icon({ status }: { status: Stage["status"] }) {
  if (status === "done") {
    return (
      <svg width="8" height="8" viewBox="0 0 10 10" fill="none" aria-hidden>
        <path d="M1.5 5.2 3.9 7.5 8.5 2.5" stroke="#34d399" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (status === "error") {
    return (
      <svg width="8" height="8" viewBox="0 0 10 10" fill="none" aria-hidden>
        <path d="M2.2 2.2 7.8 7.8M7.8 2.2 2.2 7.8" stroke="#fb7185" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  if (status === "running") {
    return <span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--accent)" }} />;
  }
  return null;
}

/**
 * The pipeline rendered as a live agent trace - each stage reports its own
 * status, one-line detail, and cumulative elapsed time as the stream lands.
 */
export default function AgentTrace({ stages, totalElapsed }: { stages: Stage[]; totalElapsed: number | null }) {
  const done = stages.filter((s) => s.status === "done").length;

  return (
    <section className="panel">
      <div className="panel-head">
        <div className="panel-title">
          <span className={`dot ${stages.some((s) => s.status === "running") ? "live" : ""}`} />
          Agent trace
        </div>
        <span className="mono-sm">
          {totalElapsed !== null ? `${totalElapsed.toFixed(2)}s` : `${done}/${stages.length}`}
        </span>
      </div>

      <div className="panel-body">
        <div className="trace">
          {stages.map((stage) => (
            <div className="step" key={stage.id} data-status={stage.status}>
              <div className="step-rail">
                <span className="step-icon">
                  <Icon status={stage.status} />
                </span>
                <span className="step-line" />
              </div>

              <div className="step-main">
                <div className="step-label">
                  <span>{stage.label}</span>
                  {stage.elapsed !== undefined && (
                    <span className="mono-sm">{stage.elapsed.toFixed(2)}s</span>
                  )}
                </div>
                {stage.detail ? (
                  <div className="step-detail" title={stage.detail}>
                    {stage.detail}
                  </div>
                ) : stage.status === "running" ? (
                  <span className="shimmer" />
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
