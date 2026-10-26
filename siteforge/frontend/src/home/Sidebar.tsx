import type { LucideIcon } from "lucide-react";

export function Sidebar({
  entries,
  nav,
  unread,
  onNavigate,
}: {
  entries: [string, string, LucideIcon][];
  nav: string;
  unread: number;
  onNavigate: (key: string) => void;
}) {
  return (
    <aside>
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 36 36" width="32" height="32">
            <polygon points="18,2 32,10 32,26 18,34 4,26 4,10" fill="#f5a018" />
            <path
              d="M12.5 15.2c1.6-2.4 6.2-2.6 8.2-.4 1.6 1.8.4 3.4-2.2 4.2-3.2 1-5.6 2-4.4 4.2 1.4 2.4 6.4 2.2 8.4-.2"
              fill="none"
              stroke="white"
              strokeWidth="2.3"
              strokeLinecap="round"
            />
          </svg>
        </span>
        <span>ZerroBuild</span>
      </div>
      <nav aria-label="Workspace">
        {entries.map(([key, label, Icon]) => (
          <button key={key} type="button" className={nav === key ? "active" : ""} onClick={() => onNavigate(key)}>
            <Icon size={18} strokeWidth={1.9} />
            {label}
            {key === "notifications" && unread > 0 ? <em>{unread}</em> : null}
          </button>
        ))}
      </nav>
      <div className="sidebar-foot">
        <button type="button" className={nav === "help" ? "active" : ""} onClick={() => onNavigate("help")}>
          <HelpMark /> Help
        </button>
        <button type="button" className={nav === "settings" ? "active" : ""} onClick={() => onNavigate("settings")}>
          <GearMark /> Settings
        </button>
      </div>
    </aside>
  );
}

function HelpMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.8.4-1.5.9-1.5 1.9" strokeLinecap="round" />
      <path d="M12 17h.01" strokeLinecap="round" />
    </svg>
  );
}

function GearMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6" strokeLinecap="round" />
    </svg>
  );
}
