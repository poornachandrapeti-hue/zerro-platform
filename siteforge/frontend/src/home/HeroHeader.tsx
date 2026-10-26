import type { ReactNode } from "react";
import { Bell, Building2, ChevronDown, Search, User } from "lucide-react";

export function HeroHeader({
  projects,
  projectId,
  query,
  unread,
  userName,
  role,
  menu,
  onProject,
  onQuery,
  onNotifications,
  onToggleMenu,
  menuContent,
}: {
  projects: { id?: number; name: string }[];
  projectId: number | null;
  query: string;
  unread: number;
  userName: string;
  role: string;
  menu: boolean;
  onProject: (value: string) => void;
  onQuery: (value: string) => void;
  onNotifications: () => void;
  onToggleMenu: () => void;
  menuContent: ReactNode;
}) {
  return (
    <div className="hero-bar">
      <label className="hero-project">
        <Building2 size={16} />
        <select aria-label="Project" value={projectId || ""} onChange={(event) => onProject(event.target.value)}>
          {projects.length === 0 ? <option value="">No projects</option> : null}
          {projects.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      </label>
      <label className="hero-search">
        <Search size={16} />
        <input
          aria-label="Search your workspace"
          placeholder="Search your workspace"
          value={query}
          onChange={(event) => onQuery(event.target.value)}
        />
      </label>
      <button className="icon-button hero-bell" type="button" aria-label="Notifications" onClick={onNotifications}>
        <Bell size={18} />
        {unread > 0 ? <span className="dot-count">{unread}</span> : null}
      </button>
      <div className="user-menu">
        <button className="user-chip" type="button" aria-expanded={menu} aria-label={`Account menu for ${userName}`} onClick={onToggleMenu}>
          <span className="avatar hero-avatar">
            <User size={16} />
          </span>
          <span>{role}</span>
          <ChevronDown size={16} />
        </button>
        {menu ? <div className="menu-card">{menuContent}</div> : null}
      </div>
    </div>
  );
}
