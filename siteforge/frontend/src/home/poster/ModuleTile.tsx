import type { LucideIcon } from "lucide-react";
import type { TileTone } from "./lifecycleConfig";

export function ModuleTile({
  label,
  tone,
  icon: Icon,
  wide,
  disabled,
  reason,
  badge,
  onOpen,
}: {
  label: string;
  tone: TileTone | "support";
  icon: LucideIcon;
  wide?: boolean;
  disabled?: boolean;
  reason?: string;
  badge?: string;
  onOpen: () => void;
}) {
  return (
    <button
      type="button"
      className={`zb-tile tone-${tone}${wide ? " is-wide" : ""}`}
      disabled={disabled}
      aria-disabled={disabled || undefined}
      title={disabled ? reason : label}
      onClick={onOpen}
    >
      {badge ? (
        <i className={`zb-badge zb-badge-${badge}`} aria-hidden="true">
          <Icon />
        </i>
      ) : (
        <Icon aria-hidden="true" />
      )}
      <span>{label}</span>
    </button>
  );
}
