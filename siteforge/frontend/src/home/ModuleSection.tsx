import type { ReactNode } from "react";

export function ModuleSection({ title, columns, children }: { title: string; columns: number; children: ReactNode }) {
  if (!children) return null;
  return (
    <section className="board-group">
      <h3>{title}</h3>
      <div className={`module-grid cols-${columns}`}>{children}</div>
    </section>
  );
}

export function ModulePlaceholder({ name, onHome }: { name: string; onHome: () => void }) {
  return (
    <section className="panel">
      <h2>{name}</h2>
      <p>This module is on the home screen and does not have its own workspace yet.</p>
      <button className="primary" type="button" onClick={onHome}>
        Back to Home
      </button>
    </section>
  );
}
