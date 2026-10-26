import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  Download,
  Filter,
  Layers,
  Search,
  X,
} from "lucide-react";
import { api, downloadFile } from "./api";

type Counts = Record<string, number>;
type Overdue = { action: string; due_date: string; days: number; pending_with: string[] };
type Row = {
  id: number;
  number: string;
  title: string;
  discipline: string;
  drawing_type: string;
  area: string;
  responsible: string;
  current_revision: string | null;
  preparation_status: string;
  internal_status: string;
  client_status: string;
  open_comments: number;
  overall_status: string;
  released_revision: string | null;
  release_status: string;
  required_date: string | null;
  required_for: string;
  pending_with: string[];
  overdue: Overdue[];
  days_overdue: number;
  last_updated: string | null;
  work_packages: { id: number; code: string; blocking: boolean; withdrawn: boolean }[];
};
type Attention = {
  drawing_id: number;
  number: string;
  discipline: string;
  issue: string;
  severity: string;
  pending_with: string;
  due_date: string | null;
  work_packages: string;
  tab: string;
};
type Board = {
  project: { id: number; code: string; name: string };
  as_of: string;
  released_only: boolean;
  metrics: { key: string; label: string; definition: string }[];
  options: {
    disciplines: { id: number; name: string }[];
    areas: { id: number; name: string }[];
    drawing_types: string[];
    engineers: { id: number; name: string }[];
    internal_statuses: string[];
    client_statuses: string[];
    release_statuses: string[];
  };
  totals: Counts;
  disciplines: { id: number; name: string; [key: string]: number | string }[];
  lifecycle: { key: string; label: string; count: number }[];
  attention: Attention[];
  unavailable: { metric: string; reason: string }[];
  register: {
    items: Row[];
    total: number;
    page: number;
    pages: number;
    size: number;
    metric: string;
    discipline_id: number | null;
    sort: string;
    direction: string;
  };
};

const BLANK = {
  discipline_id: "",
  area_id: "",
  drawing_type: "",
  engineer_id: "",
  internal_status: "",
  client_status: "",
  release_status: "",
  required_from: "",
  required_to: "",
  overdue_only: false,
  q: "",
};
type Filters = typeof BLANK;

const CARD_METRICS = [
  "to_prepare",
  "preparing",
  "internal_review",
  "client_review",
  "open_comments",
  "returned",
  "approved",
  "released",
  "overdue",
];
const TABLE_METRICS = [
  "total",
  "to_prepare",
  "preparing",
  "internal_review",
  "client_review",
  "open_comments",
  "approved",
  "released",
  "overdue",
];
const TONE: Record<string, string> = {
  total: "navy",
  to_prepare: "grey",
  preparing: "blue",
  internal_review: "amber",
  client_review: "amber",
  open_comments: "orange",
  returned: "red",
  approved: "green",
  released: "teal",
  overdue: "red",
};
const LIFECYCLE_TONE: Record<string, string> = {
  to_prepare: "grey",
  in_preparation: "blue",
  under_review: "amber",
  accepted: "green",
  accepted_with_comments: "green",
  returned: "orange",
  rejected: "red",
  released: "teal",
};
const COLUMNS: [string, string, string | null][] = [
  ["number", "Drawing Number", "number"],
  ["title", "Title", "title"],
  ["discipline", "Discipline", "discipline"],
  ["type", "Drawing Type", null],
  ["area", "Unit/Area/Block", null],
  ["current", "Current Rev", null],
  ["prep", "Preparation", null],
  ["internal", "Internal Review", null],
  ["client", "Client Review", null],
  ["comments", "Open Comments", "open_comments"],
  ["overall", "Overall Approval", null],
  ["released", "Released Rev", null],
  ["release", "Construction Release", null],
  ["required", "Required Date", "required_date"],
  ["pending", "Pending With", null],
  ["overdue", "Days Overdue", "days_overdue"],
  ["updated", "Last Updated", "last_updated"],
  ["actions", "Actions", null],
];

function statusTone(text: string) {
  const value = text.toLowerCase();
  if (value.includes("reject") || value.includes("withdrawn")) return "red";
  if (value.includes("return") || value.includes("changes required") || value.includes("revise")) return "orange";
  if (value.startsWith("released")) return "teal";
  if (value.includes("eligible") || value.startsWith("approved") || value === "accepted" || value.includes("accepted with"))
    return "green";
  if (value.includes("pending") || value.includes("awaiting") || value.includes("client pending")) return "amber";
  if (value.includes("preparation") || value === "prepared") return "blue";
  return "grey";
}

export function Pill({ text }: { text: string }) {
  return <span className={`ed-pill ed-${statusTone(text)}`}>{text}</span>;
}

export function day(value: string | null) {
  if (!value) return "—";
  const [y, m, d] = value.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function stamp(value: string | null) {
  return value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—";
}

export type DashboardView = "dashboard" | "register" | "attention";

export function EngineeringDashboard({
  pid,
  view,
  refreshKey,
  onOpen,
  onView,
}: {
  pid: number;
  view: DashboardView;
  refreshKey: number;
  onOpen: (id: number, tab?: string) => void;
  onView: (view: DashboardView) => void;
}) {
  const [filters, setFilters] = useState<Filters>(BLANK);
  const [search, setSearch] = useState("");
  const [more, setMore] = useState(false);
  const [metric, setMetric] = useState("");
  const [drill, setDrill] = useState<number | null>(null);
  const [sort, setSort] = useState("number");
  const [direction, setDirection] = useState("asc");
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(25);
  const [board, setBoard] = useState<Board | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function params(withPage: boolean) {
    const query = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value === true) query.set(key, "true");
      else if (value) query.set(key, String(value));
    });
    if (metric) query.set("metric", metric);
    if (drill) query.set("drill_discipline", String(drill));
    if (withPage) {
      query.set("sort", sort);
      query.set("direction", direction);
      query.set("page", String(page));
      query.set("size", String(size));
    }
    return query.toString();
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setFilters((current) => (current.q === search ? current : { ...current, q: search }));
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let live = true;
    setLoading(true);
    api<Board>(`/projects/${pid}/engineering-dashboard?${params(true)}`)
      .then((data) => {
        if (!live) return;
        setBoard(data);
        setError("");
      })
      .catch((err) => live && setError((err as Error).message))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [pid, refreshKey, filters, metric, drill, sort, direction, page, size]);

  function setFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }
  function open(nextMetric: string, discipline: number | null) {
    setMetric(nextMetric === "total" ? "" : nextMetric);
    setDrill(discipline);
    setPage(1);
    onView("register");
  }
  function sortBy(key: string) {
    if (sort === key) setDirection(direction === "asc" ? "desc" : "asc");
    else {
      setSort(key);
      setDirection("asc");
    }
    setPage(1);
  }
  function exportCsv() {
    void downloadFile(`/projects/${pid}/engineering-dashboard/export?${params(false)}`, "drawing-register.csv").catch(
      (err) => setError((err as Error).message),
    );
  }

  const labels = Object.fromEntries((board?.metrics || []).map((row) => [row.key, row.label]));
  const definitions = Object.fromEntries((board?.metrics || []).map((row) => [row.key, row.definition]));
  const options = board?.options;
  const active = Object.entries(filters).filter(([, value]) => value).length;
  const drillName = drill ? board?.options.disciplines.find((row) => row.id === drill)?.name : "";
  const total = board?.totals.total ?? 0;

  return (
    <div className="ed-board">
      <div className="ed-toolbar">
        <p className="muted">
          Unique drawings from one snapshot{board ? ` taken ${stamp(board.as_of)}` : ""}. Every count opens the matching list in
          the register.
        </p>
        <button type="button" className="ed-export" onClick={exportCsv}>
          <Download size={16} /> Export filtered register
        </button>
      </div>
      {board?.released_only && (
        <p className="ed-note">Your role sees released drawings only. Counts cover the released revisions you can open.</p>
      )}

      <div className="ed-filters">
        <div className="ed-filter-title">
          <Filter size={15} /> Filters {active ? <span className="ed-pill ed-navy">{active} active</span> : null}
          <button type="button" className="ed-link" onClick={() => setMore(!more)}>
            {more ? "Hide filters" : "Show all filters"}
          </button>
          {active ? (
            <button
              type="button"
              className="ed-link"
              onClick={() => {
                setFilters(BLANK);
                setSearch("");
                setPage(1);
              }}
            >
              Clear all
            </button>
          ) : null}
        </div>
        <label className="ed-search">
          <Search size={15} />
          <input
            aria-label="Search number or title"
            placeholder="Search drawing number or title"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label>
          Discipline
          <select value={filters.discipline_id} onChange={(e) => setFilter("discipline_id", e.target.value)}>
            <option value="">All disciplines</option>
            {options?.disciplines.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </label>
        <label className="ed-check">
          <input
            type="checkbox"
            checked={filters.overdue_only}
            onChange={(e) => setFilter("overdue_only", e.target.checked)}
          />
          Overdue only
        </label>
        {more && (
        <>
        <label>
          Unit/Area/Block
          <select value={filters.area_id} onChange={(e) => setFilter("area_id", e.target.value)}>
            <option value="">All locations</option>
            {options?.areas.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Drawing type
          <select value={filters.drawing_type} onChange={(e) => setFilter("drawing_type", e.target.value)}>
            <option value="">All types</option>
            {options?.drawing_types.map((row) => (
              <option key={row}>{row}</option>
            ))}
          </select>
        </label>
        <label>
          Responsible engineer
          <select value={filters.engineer_id} onChange={(e) => setFilter("engineer_id", e.target.value)}>
            <option value="">All engineers</option>
            {options?.engineers.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Internal review
          <select value={filters.internal_status} onChange={(e) => setFilter("internal_status", e.target.value)}>
            <option value="">Any status</option>
            {options?.internal_statuses.map((row) => (
              <option key={row}>{row}</option>
            ))}
          </select>
        </label>
        <label>
          Client review
          <select value={filters.client_status} onChange={(e) => setFilter("client_status", e.target.value)}>
            <option value="">Any status</option>
            {options?.client_statuses.map((row) => (
              <option key={row}>{row}</option>
            ))}
          </select>
        </label>
        <label>
          Construction release
          <select value={filters.release_status} onChange={(e) => setFilter("release_status", e.target.value)}>
            <option value="">Any status</option>
            {options?.release_statuses.map((row) => (
              <option key={row}>{row}</option>
            ))}
          </select>
        </label>
        <label>
          Required from
          <input type="date" value={filters.required_from} onChange={(e) => setFilter("required_from", e.target.value)} />
        </label>
        <label>
          Required to
          <input type="date" value={filters.required_to} onChange={(e) => setFilter("required_to", e.target.value)} />
        </label>
        </>
        )}
      </div>

      {error && (
        <div role="alert" className="error">
          {error}
        </div>
      )}
      {loading && !board ? <p className="muted ed-loading">Loading the drawing dashboard…</p> : null}

      {board && (
        <>
          {view === "dashboard" && (
          <>
          <div className="ed-legend">
            {[
              ["grey", "Not started"],
              ["blue", "Preparation"],
              ["amber", "Pending review"],
              ["orange", "Action required"],
              ["green", "Approved"],
              ["teal", "Released"],
              ["red", "Overdue or rejected"],
            ].map(([tone, text]) => (
              <span key={tone} className={`ed-pill ed-${tone}`}>
                {text}
              </span>
            ))}
          </div>

          <div className="ed-cards">
            {board.disciplines.length === 0 && (
              <p className="muted">You do not have drawing access to any discipline on this project.</p>
            )}
            {board.disciplines.map((item) => (
              <article key={item.id} className="ed-card">
                <header>
                  <h3>{item.name}</h3>
                  <button type="button" className="ed-total" onClick={() => open("total", item.id)}>
                    <strong>{item.total}</strong>
                    <span>drawings</span>
                  </button>
                </header>
                <ul>
                  {CARD_METRICS.map((key) => (
                    <li key={key}>
                      <span className={`ed-dot ed-${TONE[key]}`} />
                      <span title={definitions[key]}>{labels[key]}</span>
                      <button
                        type="button"
                        className={`ed-count ed-${TONE[key]}`}
                        disabled={!item[key]}
                        onClick={() => open(key, item.id)}
                      >
                        {item[key]}
                      </button>
                    </li>
                  ))}
                </ul>
                <footer>
                  {item.open_comment_items} open comment{item.open_comment_items === 1 ? "" : "s"} across{" "}
                  {item.open_comments} drawing{item.open_comments === 1 ? "" : "s"}
                </footer>
              </article>
            ))}
          </div>

          <div className="ed-split">
            <div className="ed-block">
              <h3>
                <Layers size={16} /> Discipline comparison
              </h3>
              <p className="muted">Columns overlap: one drawing can be released and under review at the same time. Do not add across.</p>
              <div className="mp-table-wrap">
                <table className="mp-table ed-compare">
                  <thead>
                    <tr>
                      <th>Discipline</th>
                      {TABLE_METRICS.map((key) => (
                        <th key={key} title={definitions[key]}>
                          {key === "total" ? "Total" : labels[key]}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {board.disciplines.map((item) => (
                      <tr key={item.id}>
                        <td>{item.name}</td>
                        {TABLE_METRICS.map((key) => (
                          <td key={key}>
                            <button
                              type="button"
                              className={`ed-cell ed-${TONE[key]}`}
                              disabled={!item[key]}
                              onClick={() => open(key, item.id)}
                            >
                              {item[key]}
                            </button>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td>All shown</td>
                      {TABLE_METRICS.map((key) => (
                        <td key={key}>
                          <button
                            type="button"
                            className={`ed-cell ed-${TONE[key]}`}
                            disabled={!board.totals[key]}
                            onClick={() => open(key, null)}
                          >
                            {board.totals[key]}
                          </button>
                        </td>
                      ))}
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
            <div className="ed-block">
              <h3>Lifecycle of the current revision</h3>
              <p className="muted">Each drawing sits in exactly one stage, so these add up to {total}.</p>
              <div className="ed-stack" role="img" aria-label="Lifecycle breakdown">
                {board.lifecycle
                  .filter((row) => row.count)
                  .map((row) => (
                    <span
                      key={row.key}
                      className={`ed-seg ed-${LIFECYCLE_TONE[row.key]}`}
                      style={{ flexGrow: row.count }}
                      title={`${row.label}: ${row.count}`}
                    />
                  ))}
              </div>
              <ul className="ed-life">
                {board.lifecycle.map((row) => (
                  <li key={row.key}>
                    <span className={`ed-dot ed-${LIFECYCLE_TONE[row.key]}`} />
                    {row.label}
                    <strong>{row.count}</strong>
                  </li>
                ))}
              </ul>
              {board.unavailable.length > 0 && (
                <div className="ed-unavailable">
                  {board.unavailable.map((row) => (
                    <p key={row.metric}>
                      <strong>{row.metric}: Not available.</strong> {row.reason}
                    </p>
                  ))}
                </div>
              )}
            </div>
          </div>

          </>
          )}

          {view !== "register" && (
          <div className="ed-block ed-attention">
            <h3>
              <AlertTriangle size={16} /> Attention required{" "}
              <span className="ed-pill ed-red">{board.attention.length}</span>
              {view === "dashboard" && board.attention.length > 5 && (
                <button type="button" className="ed-link ed-more" onClick={() => onView("attention")}>
                  View all {board.attention.length}
                </button>
              )}
            </h3>
            {board.attention.length === 0 ? (
              <p className="mp-ok">Nothing needs attention for these filters.</p>
            ) : (
              <div className="mp-table-wrap">
                <table className="mp-table">
                  <thead>
                    <tr>
                      <th>Drawing</th>
                      <th>Discipline</th>
                      <th>Issue</th>
                      <th>Pending With</th>
                      <th>Due Date</th>
                      <th>Affected Work Package</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {board.attention.slice(0, view === "dashboard" ? 5 : 50).map((item, index) => (
                      <tr key={`${item.drawing_id}-${index}`}>
                        <td>{item.number}</td>
                        <td>{item.discipline}</td>
                        <td>
                          <span className={`ed-pill ed-${item.severity === "overdue" ? "red" : "orange"}`}>{item.issue}</span>
                        </td>
                        <td>{item.pending_with || "—"}</td>
                        <td>{day(item.due_date)}</td>
                        <td>{item.work_packages || "None linked"}</td>
                        <td>
                          <button type="button" className="ed-link" onClick={() => onOpen(item.drawing_id, item.tab)}>
                            Open
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {view === "attention" && board.attention.length > 50 && (
                  <p className="muted">Showing the first 50 of {board.attention.length}. Narrow the filters to see the rest.</p>
                )}
              </div>
            )}
          </div>
          )}

          {view === "register" && (
          <div className="ed-block" id="ed-register">
            <div className="ed-register-head">
              <h3>Drawing register</h3>
              {(metric || drill) && (
                <span className="ed-chip">
                  Showing {metric ? labels[metric] : "all"}
                  {drillName ? ` · ${drillName}` : ""}
                  <button
                    type="button"
                    aria-label="Clear drill-down"
                    onClick={() => {
                      setMetric("");
                      setDrill(null);
                      setPage(1);
                    }}
                  >
                    <X size={13} />
                  </button>
                </span>
              )}
              <span className="muted">
                {board.register.total} drawing{board.register.total === 1 ? "" : "s"}
                {loading ? " · refreshing…" : ""}
              </span>
            </div>
            {metric && <p className="muted">{definitions[metric]}</p>}
            <div className="mp-table-wrap">
              <table className="mp-table ed-register">
                <thead>
                  <tr>
                    {COLUMNS.map(([key, text, sortKey]) => (
                      <th key={key}>
                        {sortKey ? (
                          <button type="button" className="ed-sort" onClick={() => sortBy(sortKey)}>
                            {text}
                            {sort === sortKey ? (direction === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />) : null}
                          </button>
                        ) : (
                          text
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {board.register.items.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <button type="button" className="ed-link" onClick={() => onOpen(row.id)}>
                          {row.number}
                        </button>
                      </td>
                      <td className="ed-title">{row.title}</td>
                      <td>{row.discipline}</td>
                      <td>{row.drawing_type || "—"}</td>
                      <td>{row.area || "—"}</td>
                      <td>{row.current_revision ?? <span className="muted">No file yet</span>}</td>
                      <td>
                        <Pill text={row.preparation_status} />
                      </td>
                      <td>
                        <Pill text={row.internal_status} />
                      </td>
                      <td>
                        <Pill text={row.client_status} />
                      </td>
                      <td>{row.open_comments ? <span className="ed-pill ed-orange">{row.open_comments}</span> : "0"}</td>
                      <td>
                        <Pill text={row.overall_status} />
                      </td>
                      <td>{row.released_revision ?? "—"}</td>
                      <td>
                        <Pill text={row.release_status} />
                      </td>
                      <td>
                        {day(row.required_date)}
                        {row.required_for ? <small className="ed-sub">{row.required_for}</small> : null}
                      </td>
                      <td className="ed-pending">{row.pending_with.length ? row.pending_with.join(", ") : "—"}</td>
                      <td>
                        {row.days_overdue ? (
                          <span className="ed-pill ed-red" title={row.overdue.map((item) => `${item.action} due ${item.due_date}`).join("\n")}>
                            {row.days_overdue}d · {row.overdue.map((item) => item.action).join(", ")}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>{stamp(row.last_updated)}</td>
                      <td>
                        <button type="button" className="ed-link" onClick={() => onOpen(row.id)}>
                          Open
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {board.register.items.length === 0 && !loading && (
              <p className="muted ed-empty">No drawings match these filters. Clear a filter or the drill-down to see more.</p>
            )}
            <div className="ed-pager">
              <label>
                Rows
                <select
                  value={size}
                  onChange={(e) => {
                    setSize(Number(e.target.value));
                    setPage(1);
                  }}
                >
                  {[10, 25, 50, 100].map((n) => (
                    <option key={n}>{n}</option>
                  ))}
                </select>
              </label>
              <button type="button" disabled={board.register.page <= 1} onClick={() => setPage(board.register.page - 1)}>
                <ChevronLeft size={15} /> Previous
              </button>
              <span>
                Page {board.register.page} of {board.register.pages}
              </span>
              <button
                type="button"
                disabled={board.register.page >= board.register.pages}
                onClick={() => setPage(board.register.page + 1)}
              >
                Next <ChevronRight size={15} />
              </button>
            </div>
          </div>
          )}
        </>
      )}
    </div>
  );
}
