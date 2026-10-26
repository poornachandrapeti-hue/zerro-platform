import { AlertTriangle, Building2, FileText, ListChecks } from "lucide-react";

export function ProjectStats({
  projectName,
  approvals,
  tasks,
  alerts,
  onProject,
  onApprovals,
  onTasks,
}: {
  projectName: string;
  approvals: number;
  tasks: number;
  alerts: number;
  onProject: () => void;
  onApprovals: () => void;
  onTasks: () => void;
}) {
  return (
    <div className="hero-stats">
      <button className="stat" type="button" onClick={onProject}>
        <span className="stat-label">
          <Building2 size={15} />
          Project
        </span>
        <strong>{projectName}</strong>
      </button>
      <button className="stat" type="button" onClick={onApprovals}>
        <span className="stat-label">
          <FileText size={15} />
          Approvals
        </span>
        <strong>{approvals}</strong>
      </button>
      <button className="stat" type="button" onClick={onTasks}>
        <span className="stat-label">
          <ListChecks size={15} />
          Open tasks
        </span>
        <strong>{tasks}</strong>
      </button>
      <button className="stat" type="button" onClick={onTasks}>
        <span className="stat-label">
          <AlertTriangle size={15} />
          Alerts
        </span>
        <strong className={alerts > 0 ? "bad" : ""}>{alerts}</strong>
      </button>
    </div>
  );
}
