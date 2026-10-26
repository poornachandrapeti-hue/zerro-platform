import type { LucideIcon } from "lucide-react";
import { ModuleTile } from "./ModuleTile";

export type SupportTile = {
  id: string;
  label: string;
  icon: LucideIcon;
  disabled: boolean;
  reason?: string;
  onOpen: () => void;
};

export function ContinuousSupportRibbon({ items }: { items: SupportTile[] }) {
  return (
    <section className="zb-ribbon" aria-label="Continuous project support">
      <div className="zb-ribbon-copy">
        <h2>CONTINUOUS PROJECT SUPPORT</h2>
        <p>Enabling collaboration, governance and continuous improvement across the entire lifecycle.</p>
      </div>
      <div className="zb-ribbon-rule" aria-hidden="true" />
      <div className="zb-ribbon-tiles">
        {items.map((item) => (
          <ModuleTile
            key={item.id}
            label={item.label}
            tone="support"
            icon={item.icon}
            disabled={item.disabled}
            reason={item.reason}
            badge={item.id}
            onOpen={item.onOpen}
          />
        ))}
      </div>
    </section>
  );
}
