import type { ReactNode } from "react";
import type { StageDef } from "./lifecycleConfig";

export function LifecycleStageCard({ stage, children }: { stage: StageDef; children: ReactNode }) {
  const Icon = stage.icon;
  return (
    <article className={`zb-stage zb-n-${stage.number}`}>
      <header>
        <span className="zb-num">{stage.number}</span>
        <Icon className="zb-stage-icon" aria-hidden="true" />
        <div>
          <h2>{stage.title}</h2>
          <p>{stage.text}</p>
        </div>
      </header>
      <div className={`zb-tiles cols-${stage.columns}`}>{children}</div>
    </article>
  );
}
