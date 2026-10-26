import { FormEvent, useEffect, useState } from "react";
import {
  AlertTriangle,
  BadgeCheck,
  ClipboardList,
  Download,
  FileSpreadsheet,
  Layers,
  PackageCheck,
  PenLine,
  Plus,
  RefreshCw,
  ScanLine,
  ShoppingCart,
  Trash2,
  Undo2,
} from "lucide-react";
import { api, downloadFile, fetchBlob, postForm } from "./api";
import { RequirementDetail, type Context, type Requirement } from "./procurement";
import type { Page, Project, Session } from "./types";

type MtoLine = {
  id: number;
  position: number;
  description: string;
  specification: string;
  quantity: string | null;
  unit: string;
  item_id: number | null;
  item_code: string;
  item_description: string;
  reference: string;
  page: number | null;
  table_ref: string;
  row_ref: string;
  bbox: number[] | null;
  confidence: string | null;
  flags: string[];
  origin: string;
  original: Record<string, unknown> | null;
  corrected: boolean;
  version: number;
};

type Change = { label: string; quantity?: string; unit?: string; specification?: string; old?: string; new?: string };

type ChangeSummary = {
  previous: string;
  text?: string;
  added: Change[];
  removed: Change[];
  quantity_changed: Change[];
  specification_changed: Change[];
  requirements?: { id: number; number: string; status: string }[];
  requisitions?: { id: number; number: string; status: string }[];
  orders?: { id: number; number: string; status: string }[];
  allocations?: number;
};

type Takeoff = {
  id: number;
  number: string;
  drawing_id: number;
  drawing_number: string;
  drawing_title: string;
  revision_id: number;
  revision_code: string;
  revision_release_state: string;
  discipline_id: number;
  discipline: string;
  source: string;
  pages: string;
  status: string;
  note: string;
  return_reason: string;
  change_state: string;
  change_summary: ChangeSummary | null;
  created_by_name: string;
  verified_by_name: string;
  verified_at: string;
  version: number;
  line_count: number;
  requirements: { id: number; number: string; status: string }[];
  job: { id: number; status: string; provider: string; message: string; attempt: number } | null;
  access: {
    edit: boolean;
    match: boolean;
    submit: boolean;
    verify: boolean;
    retry: boolean;
    requirement: boolean;
    apply: boolean;
    cancel: boolean;
  };
  lines?: MtoLine[];
  deleted_lines?: MtoLine[];
  history?: { id: number; kind: string; field: string; old: string; new: string; actor: string; at: string }[];
};

type Item = { id: number; code: string; description: string; base_unit: string; discipline_ids: number[]; active?: boolean };

type Setup = { ocr: { configured: boolean; provider: string; message: string }; supported: string[]; unsupported: string[] };

type RevisionChoice = { id: number; code: string; release_state: string };

function slug(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function Pill({ value }: { value: string }) {
  return <span className={`state-pill state-${slug(value)}`}>{value}</span>;
}

function when(value: string) {
  return value ? new Date(value).toLocaleString() : "";
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function originalText(line: MtoLine) {
  const source = line.original || {};
  const parts = ["description", "specification", "quantity", "unit"]
    .map((key) => `${key}: ${source[key] === null || source[key] === undefined ? "blank" : String(source[key])}`)
    .join(" · ");
  return line.origin === "Added" ? "Added on the review screen" : `Original ${line.origin.toLowerCase()} values: ${parts}`;
}

export function MaterialsTab({
  pid,
  drawingId,
  revisions,
  userId,
  onError,
}: {
  pid: number;
  drawingId: number;
  revisions: RevisionChoice[];
  userId: number;
  onError: (text: string) => void;
}) {
  const [rows, setRows] = useState<Takeoff[]>([]);
  const [setup, setSetup] = useState<Setup | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [revision, setRevision] = useState(revisions[revisions.length - 1]?.id || 0);
  const [pages, setPages] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Record<string, unknown>[] | null>(null);
  const [busy, setBusy] = useState(false);
  async function load() {
    setRows(await api<Takeoff[]>(`/projects/${pid}/takeoffs?drawing_id=${drawingId}`));
  }
  useEffect(() => {
    void load().catch((err) => onError((err as Error).message));
    void api<Setup>(`/projects/${pid}/takeoff-setup`).then(setSetup).catch(() => setSetup(null));
  }, [pid, drawingId]);
  async function act(work: () => Promise<Takeoff | { takeoff: Takeoff | null; rows: Record<string, unknown>[] }>) {
    if (busy) return;
    setBusy(true);
    try {
      const result = await work();
      onError("");
      if ("rows" in result && "takeoff" in result && !("number" in result)) {
        setPreview(result.rows);
        if (result.takeoff) {
          setOpenId(result.takeoff.id);
          setPreview(null);
          setFile(null);
        }
      } else {
        setOpenId((result as Takeoff).id);
      }
      await load();
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const base = `/projects/${pid}/drawings/${drawingId}/revisions/${revision}/takeoffs`;
  function importFile(mode: string) {
    if (!file) return;
    const data = new FormData();
    data.set("upload", file);
    void act(() => postForm<{ takeoff: Takeoff | null; rows: Record<string, unknown>[] }>(`${base}/import?mode=${mode}`, data));
  }
  if (!revisions.length) {
    return <p className="ed-note">Add a drawing revision first. Material take-off always belongs to an exact revision.</p>;
  }
  return (
    <div className="mto-wrap">
      <div className="mto-start">
        <div className="mto-start-head">
          <h3 className="section-mark">
            <Layers size={18} strokeWidth={2.4} /> Material take-off (MTO)
          </h3>
          <p className="muted">
            Lines are read only from explicit material tables or BOMs on the controlled drawing file, imported, or entered by hand. Quantities are never calculated from geometry or scale. Every MTO starts unverified.
          </p>
        </div>
        <div className="mto-start-grid">
          <label>
            Revision
            <select aria-label="MTO revision" value={revision} onChange={(e) => setRevision(Number(e.target.value))}>
              {revisions.map((row) => (
                <option key={row.id} value={row.id}>
                  Rev {row.code} · {row.release_state}
                </option>
              ))}
            </select>
          </label>
          <label>
            Pages
            <input aria-label="Pages" placeholder="All pages, or 1,3-4" value={pages} onChange={(e) => setPages(e.target.value)} />
          </label>
          <button type="button" className="tone-submit" disabled={busy || !revision} onClick={() => void act(() => api<Takeoff>(`${base}/extract`, "POST", { pages }))}>
            <ScanLine size={15} /> Extract Materials
          </button>
          <button type="button" className="tone-note" disabled={busy || !revision} onClick={() => void act(() => api<Takeoff>(`${base}/manual`, "POST"))}>
            <PenLine size={15} /> Enter lines by hand
          </button>
          <label>
            MTO file (CSV or Excel)
            <input aria-label="MTO file" type="file" accept=".csv,.xlsx" onChange={(e) => { setFile(e.target.files?.[0] || null); setPreview(null); }} />
          </label>
          <button type="button" className="tone-note" disabled={busy || !file} onClick={() => importFile("preview")}>
            <FileSpreadsheet size={15} /> Preview import
          </button>
        </div>
        {setup && (
          <p className={setup.ocr.configured ? "note-card note-good" : "note-card note-alert"}>
            {setup.ocr.configured ? <BadgeCheck size={15} /> : <AlertTriangle size={15} />} {setup.ocr.message}
          </p>
        )}
        {preview && (
          <div className="mto-preview">
            <table>
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Description</th>
                  <th>Specification</th>
                  <th>Quantity</th>
                  <th>Unit</th>
                  <th>Catalogue</th>
                  <th>Needs attention</th>
                </tr>
              </thead>
              <tbody>
                {preview.map((row) => (
                  <tr key={String(row.row)}>
                    <td>{String(row.row)}</td>
                    <td>{String(row.description || "")}</td>
                    <td>{String(row.specification || "")}</td>
                    <td>{row.quantity === null ? <em className="mto-missing">Not given</em> : String(row.quantity)}</td>
                    <td>{String(row.unit || "") || <em className="mto-missing">Not given</em>}</td>
                    <td>{String(row.item_code || "")}</td>
                    <td>{((row.flags as string[]) || []).map((flag) => <span key={flag} className="mto-flag">{flag}</span>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button type="button" className="tone-submit" disabled={busy} onClick={() => importFile("confirm")}>
              Import {preview.length} line(s) as an unverified MTO
            </button>
          </div>
        )}
      </div>
      {rows.length > 0 && (
        <table className="mto-list">
          <thead>
            <tr>
              <th>MTO</th>
              <th>Revision</th>
              <th>Source</th>
              <th>Status</th>
              <th>Lines</th>
              <th>Verified by</th>
              <th>Requirement</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className={openId === row.id ? "is-on" : ""}>
                <td>
                  <button type="button" className="ed-link" onClick={() => setOpenId(row.id)}>
                    {row.number}
                  </button>
                </td>
                <td>Rev {row.revision_code}</td>
                <td>{row.source}</td>
                <td>
                  <Pill value={row.status} />
                  {row.change_state === "Review required" && <Pill value="Revision change" />}
                </td>
                <td>{row.line_count}</td>
                <td>{row.verified_by_name || "-"}</td>
                <td>{row.requirements.map((item) => `${item.number} (${item.status})`).join(", ") || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {openId && (
        <TakeoffReview
          key={openId}
          pid={pid}
          id={openId}
          userId={userId}
          onError={onError}
          onChanged={() => void load()}
        />
      )}
    </div>
  );
}

export function TakeoffReview({
  pid,
  id,
  userId,
  onError,
  onChanged,
  onRequirement,
}: {
  pid: number;
  id: number;
  userId: number;
  onError: (text: string) => void;
  onChanged?: () => void;
  onRequirement?: (requirementId: number) => void;
}) {
  const [row, setRow] = useState<Takeoff | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [drafts, setDrafts] = useState<Record<number, Partial<MtoLine>>>({});
  const [source, setSource] = useState<{ url: string; type: string } | null>(null);
  const [showSource, setShowSource] = useState(true);
  const [page, setPage] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [adding, setAdding] = useState({ description: "", specification: "", quantity: "", unit: "", page: "" });
  const [showHistory, setShowHistory] = useState(false);
  const [form, setForm] = useState({ number: "", required_date: "", purpose: "", priority: "Normal" });
  const [busy, setBusy] = useState(false);
  async function load() {
    const fresh = await api<Takeoff>(`/projects/${pid}/takeoffs/${id}`);
    setRow(fresh);
    setDrafts({});
    setForm((value) => ({
      ...value,
      number: value.number || `MR-${fresh.number}`,
      purpose: value.purpose || `Materials for ${fresh.drawing_number} rev ${fresh.revision_code}`,
    }));
    return fresh;
  }
  useEffect(() => {
    void load().catch((err) => onError((err as Error).message));
    void api<Item[]>("/procurement/items").then((rows) => setItems(rows.filter((item) => item.active !== false))).catch(() => setItems([]));
  }, [pid, id]);
  useEffect(() => {
    if (!row || !(row.status === "Extracting" || row.job?.status === "Queued" || row.job?.status === "Running")) return;
    const timer = window.setTimeout(() => void load().catch(() => undefined), 3000);
    return () => window.clearTimeout(timer);
  }, [row]);
  useEffect(() => {
    if (!showSource) return;
    let url = "";
    void fetchBlob(`/projects/${pid}/takeoffs/${id}/source`)
      .then((blob) => {
        url = URL.createObjectURL(blob);
        setSource({ url, type: blob.type });
      })
      .catch(() => setSource(null));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [pid, id, showSource]);
  if (!row) return <p className="muted">Loading MTO…</p>;
  const lines = row.lines || [];
  const usable = items.filter((item) => item.discipline_ids.includes(row.discipline_id));
  const editable = row.access.edit;
  async function send(path: string, body?: unknown, method = "POST") {
    if (busy) return;
    setBusy(true);
    try {
      const fresh = await api<Takeoff>(`/projects/${pid}/takeoffs/${id}${path}`, method, body);
      setRow(fresh);
      setDrafts({});
      onError("");
      onChanged?.();
    } catch (err) {
      onError((err as Error).message);
      void load().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }
  function draft(line: MtoLine) {
    return { ...line, ...(drafts[line.id] || {}) };
  }
  function change(line: MtoLine, values: Partial<MtoLine>) {
    setDrafts((current) => ({ ...current, [line.id]: { ...(current[line.id] || {}), ...values } }));
  }
  function saveLine(line: MtoLine) {
    const values = drafts[line.id] || {};
    const body: Record<string, unknown> = { version: row!.version };
    for (const key of ["description", "specification", "quantity", "unit", "item_id", "reference"] as const) {
      if (key in values) body[key] = values[key] === "" && key === "quantity" ? null : values[key];
    }
    void send(`/lines/${line.id}`, body, "PUT");
  }
  async function createRequirement(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      const result = await api<{ created: boolean; requirement: Requirement }>(`/projects/${pid}/takeoffs/${id}/requirement`, "POST", {
        ...form,
        requested_by: userId,
        version: row!.version,
      });
      onError("");
      await load();
      onChanged?.();
      onRequirement?.(result.requirement.id);
      window.alert(
        result.created
          ? `Draft requirement ${result.requirement.number} created in Requirements & Requests. Submit it there for approval.`
          : `This MTO already has requirement ${result.requirement.number}. No duplicate was created.`,
      );
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const summary = row.change_summary;
  const jobRunning = row.status === "Extracting" || row.job?.status === "Queued" || row.job?.status === "Running";
  return (
    <section className="mto-review">
      <header className="mto-review-head">
        <div>
          <h3>
            {row.number} <Pill value={row.status} /> <span className="mto-tag">{row.source}</span>
          </h3>
          <p className="muted">
            {row.drawing_number} · {row.drawing_title} · Rev {row.revision_code} ({row.revision_release_state}) · {row.discipline}
            {row.pages ? ` · pages ${row.pages}` : ""} · prepared by {row.created_by_name}
            {row.verified_by_name ? ` · verified by ${row.verified_by_name} ${when(row.verified_at)}` : ""}
          </p>
        </div>
        <div className="mto-exports">
          <button type="button" onClick={() => void downloadFile(`/projects/${pid}/takeoffs/${id}/export?view=original&format=csv`, `${row.number}-original.csv`).catch((err) => onError((err as Error).message))}>
            <Download size={14} /> Unverified extraction CSV
          </button>
          <button type="button" onClick={() => void downloadFile(`/projects/${pid}/takeoffs/${id}/export?view=original&format=xlsx`, `${row.number}-original.xlsx`).catch((err) => onError((err as Error).message))}>
            <Download size={14} /> Unverified extraction Excel
          </button>
          <button type="button" onClick={() => void downloadFile(`/projects/${pid}/takeoffs/${id}/export?view=reviewed&format=csv`, `${row.number}-reviewed.csv`).catch((err) => onError((err as Error).message))}>
            <Download size={14} /> Reviewed CSV
          </button>
          <button type="button" onClick={() => void downloadFile(`/projects/${pid}/takeoffs/${id}/export?view=reviewed&format=xlsx`, `${row.number}-reviewed.xlsx`).catch((err) => onError((err as Error).message))}>
            <Download size={14} /> Reviewed Excel
          </button>
        </div>
      </header>
      {row.job && (
        <p className={`note-card ${row.job.status === "Succeeded" ? "note-good" : row.job.status === "Failed" || row.job.status === "Needs setup" || row.job.status === "Stalled" ? "note-bad" : "note-alert"}`}>
          {jobRunning ? <RefreshCw size={15} className="mto-spin" /> : null} Extraction {row.job.status.toLowerCase()} · attempt {row.job.attempt} · {row.job.provider}
          {row.job.message ? `. ${row.job.message}` : ""}
          {(row.status === "Extraction failed" || row.status === "Needs setup") && " You can still add lines by hand below, or import an MTO file on the drawing."}
        </p>
      )}
      {row.return_reason && row.status === "Returned" && <p className="note-card note-alert">Returned for correction: {row.return_reason}</p>}
      {summary && (
        <div className={`mto-change ${row.change_state === "Review required" ? "is-alert" : ""}`}>
          <h4>
            <AlertTriangle size={15} /> Compared with {summary.previous}
            {row.change_state ? ` · ${row.change_state}` : ""}
          </h4>
          <div className="mto-change-grid">
            {(["added", "removed", "quantity_changed", "specification_changed"] as const).map((key) => (
              <div key={key}>
                <strong>{key.replace("_", " ")}</strong>
                {summary[key].length === 0 ? (
                  <span className="muted">None</span>
                ) : (
                  <ul>
                    {summary[key].map((item) => (
                      <li key={item.label}>
                        {item.label}
                        {item.old !== undefined ? `: ${item.old || "blank"} → ${item.new || "blank"}` : ` ${item.quantity || ""} ${item.unit || ""}`}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
          {summary.requirements && summary.requirements.length > 0 && (
            <p className="muted">
              Affected: requirements {summary.requirements.map((item) => item.number).join(", ")}
              {summary.requisitions?.length ? ` · requisitions ${summary.requisitions.map((item) => `${item.number} (${item.status})`).join(", ")}` : ""}
              {summary.orders?.length ? ` · orders ${summary.orders.map((item) => `${item.number} (${item.status})`).join(", ")}` : ""}
              {summary.allocations ? ` · ${summary.allocations} stock allocation(s)` : ""}. The requirement reviewer records the impact decision before the change is applied.
            </p>
          )}
          {row.access.apply && (
            <button type="button" className="tone-submit" disabled={busy} onClick={() => void send("/apply", { version: row.version })}>
              Apply revision change to the requirement
            </button>
          )}
        </div>
      )}
      <div className={showSource ? "mto-split" : "mto-split is-single"}>
        {showSource && (
          <div className="mto-source">
            <div className="mto-source-bar">
              <strong>Controlled drawing · Rev {row.revision_code}</strong>
              <button type="button" onClick={() => setShowSource(false)}>Hide</button>
            </div>
            {!source ? (
              <p className="muted">The drawing file could not be shown here. Use Download file on Revisions & Files.</p>
            ) : source.type.startsWith("image/") ? (
              <img src={source.url} alt={`${row.drawing_number} rev ${row.revision_code}`} />
            ) : source.type === "application/pdf" ? (
              <iframe key={page || 0} title="Source drawing" src={`${source.url}${page ? `#page=${page}` : ""}`} />
            ) : (
              <p className="muted">This file type cannot be previewed. Download it from Revisions & Files.</p>
            )}
          </div>
        )}
        <div className="mto-lines">
          {!showSource && (
            <button type="button" className="tone-note" onClick={() => setShowSource(true)}>
              Show the source drawing
            </button>
          )}
          <div className="mto-table-wrap">
            <table className="mto-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Description</th>
                  <th>Specification</th>
                  <th>Qty</th>
                  <th>Unit</th>
                  <th>Catalogue item</th>
                  <th>Source evidence</th>
                  <th>Review flags</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {lines.map((line) => {
                  const value = draft(line);
                  const dirty = Boolean(drafts[line.id]);
                  return (
                    <tr key={line.id} className={line.flags.length ? "has-flags" : ""}>
                      <td>{line.position}</td>
                      <td>
                        {editable ? (
                          <input aria-label={`Description ${line.position}`} value={value.description} onChange={(e) => change(line, { description: e.target.value })} />
                        ) : (
                          line.description
                        )}
                      </td>
                      <td>
                        {editable ? (
                          <input aria-label={`Specification ${line.position}`} value={value.specification} onChange={(e) => change(line, { specification: e.target.value })} />
                        ) : (
                          line.specification
                        )}
                      </td>
                      <td className="mto-num">
                        {editable ? (
                          <input aria-label={`Quantity ${line.position}`} placeholder="Not given" value={value.quantity ?? ""} onChange={(e) => change(line, { quantity: e.target.value })} />
                        ) : (
                          line.quantity ?? <em className="mto-missing">Not given</em>
                        )}
                      </td>
                      <td className="mto-unit">
                        {editable ? (
                          <input aria-label={`Unit ${line.position}`} placeholder="Not given" value={value.unit} onChange={(e) => change(line, { unit: e.target.value })} />
                        ) : (
                          line.unit || <em className="mto-missing">Not given</em>
                        )}
                      </td>
                      <td>
                        {editable || row.access.match ? (
                          <select
                            aria-label={`Catalogue item ${line.position}`}
                            value={value.item_id || ""}
                            onChange={(e) => change(line, { item_id: e.target.value ? Number(e.target.value) : null })}
                          >
                            <option value="">Not matched</option>
                            {usable.map((item) => (
                              <option key={item.id} value={item.id}>
                                {item.code} · {item.description} ({item.base_unit})
                              </option>
                            ))}
                          </select>
                        ) : (
                          line.item_code || <em className="mto-missing">Not matched</em>
                        )}
                      </td>
                      <td className="mto-evidence" title={originalText(line)}>
                        <button type="button" className="ed-link" disabled={!line.page} onClick={() => setPage(line.page)}>
                          {line.page ? `p${line.page}` : "-"}
                        </button>
                        {line.table_ref ? ` ${line.table_ref}` : ""}
                        {line.row_ref ? ` · row ${line.row_ref}` : ""}
                        {line.confidence ? <span className="mto-conf">{Math.round(Number(line.confidence) * 100)}%</span> : null}
                        <small>{line.corrected ? "Corrected" : line.origin}</small>
                      </td>
                      <td>
                        {line.flags.length === 0 ? <span className="mto-ok">OK</span> : line.flags.map((flag) => <span key={flag} className="mto-flag">{flag}</span>)}
                      </td>
                      <td className="mto-row-actions">
                        {(editable || row.access.match) && dirty && (
                          <button type="button" className="tone-submit" disabled={busy} onClick={() => saveLine(line)}>
                            Save
                          </button>
                        )}
                        {editable && (
                          <button
                            type="button"
                            className="ed-danger"
                            aria-label={`Delete line ${line.position}`}
                            disabled={busy}
                            onClick={() => {
                              const why = window.prompt("Why is this line removed?") || "";
                              void send(`/lines/${line.id}/delete`, { reason: why, version: row.version });
                            }}
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {lines.length === 0 && (
                  <tr>
                    <td colSpan={9} className="muted">
                      {jobRunning ? "Extraction is running. This list refreshes on its own." : "No material lines yet."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {editable && (
            <form
              className="mto-add"
              onSubmit={(e) => {
                e.preventDefault();
                void send("/lines", {
                  description: adding.description,
                  specification: adding.specification,
                  quantity: adding.quantity || null,
                  unit: adding.unit,
                  page: adding.page ? Number(adding.page) : null,
                  version: row.version,
                }).then(() => setAdding({ description: "", specification: "", quantity: "", unit: "", page: "" }));
              }}
            >
              <input required aria-label="New line description" placeholder="Description" value={adding.description} onChange={(e) => setAdding({ ...adding, description: e.target.value })} />
              <input aria-label="New line specification" placeholder="Specification" value={adding.specification} onChange={(e) => setAdding({ ...adding, specification: e.target.value })} />
              <input aria-label="New line quantity" placeholder="Qty" value={adding.quantity} onChange={(e) => setAdding({ ...adding, quantity: e.target.value })} />
              <input aria-label="New line unit" placeholder="Unit" value={adding.unit} onChange={(e) => setAdding({ ...adding, unit: e.target.value })} />
              <input aria-label="New line page" placeholder="Page" value={adding.page} onChange={(e) => setAdding({ ...adding, page: e.target.value })} />
              <button type="submit" className="tone-note" disabled={busy}>
                <Plus size={14} /> Add line
              </button>
            </form>
          )}
          {(row.deleted_lines || []).length > 0 && (
            <p className="muted">Deleted lines kept for the record: {(row.deleted_lines || []).map((line) => `#${line.position} ${line.description}`).join(", ")}</p>
          )}
        </div>
      </div>
      <div className="mto-actions">
        {row.access.retry && (
          <button type="button" className="tone-note" disabled={busy} onClick={() => void send("/retry")}>
            <RefreshCw size={14} /> Retry extraction
          </button>
        )}
        {row.access.submit && (
          <button type="button" className="tone-submit" disabled={busy} onClick={() => void send("/submit", { version: row.version })}>
            Send for discipline verification
          </button>
        )}
        {row.access.verify && (
          <>
            <button type="button" className="tone-approve" disabled={busy} onClick={() => void send("/verify", { version: row.version })}>
              <BadgeCheck size={14} /> Verify MTO
            </button>
            <input aria-label="Correction note" placeholder="What needs correcting (for Return)" value={reason} onChange={(e) => setReason(e.target.value)} />
            <button
              type="button"
              className="tone-return"
              disabled={busy || !reason.trim()}
              onClick={() => void send("/return", { reason, version: row.version }).then(() => setReason(""))}
            >
              <Undo2 size={14} /> Return for correction
            </button>
          </>
        )}
        {row.status === "Pending Verification" && !row.access.verify && (
          <span className="muted">Waiting for a discipline reviewer with drawing review access. The person who prepared it cannot verify it.</span>
        )}
        {row.access.cancel && (
          <button
            type="button"
            className="ed-danger"
            disabled={busy}
            onClick={() => {
              const why = window.prompt("Cancellation reason");
              if (why) void send("/cancel", { reason: why, version: row.version });
            }}
          >
            Cancel MTO
          </button>
        )}
        <button type="button" className="ed-link" onClick={() => setShowHistory(!showHistory)}>
          {showHistory ? "Hide" : "Show"} correction history ({(row.history || []).length})
        </button>
      </div>
      {row.access.match && <p className="muted">This MTO is verified. Only catalogue matching can still change before the requirement is created.</p>}
      {row.access.requirement && (
        <form className="mto-requirement" onSubmit={(event) => void createRequirement(event)}>
          <h4>
            <ClipboardList size={16} /> Create Requirement from this verified MTO
          </h4>
          <p className="muted">One draft requirement is created in Requirements & Requests. Each line keeps its link to this MTO line and drawing revision. It then follows the requirement approval route.</p>
          <label>
            Requirement number
            <input required value={form.number} onChange={(e) => setForm({ ...form, number: e.target.value })} />
          </label>
          <label>
            Required at site
            <input required type="date" value={form.required_date} onChange={(e) => setForm({ ...form, required_date: e.target.value })} />
          </label>
          <label>
            Priority
            <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
              <option>Normal</option>
              <option>High</option>
              <option>Critical</option>
            </select>
          </label>
          <label className="mto-wide">
            Purpose
            <input required value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} />
          </label>
          <button type="submit" className="tone-submit" disabled={busy}>
            Create Requirement
          </button>
        </form>
      )}
      {row.requirements.length > 0 && (
        <p className="note-card note-good">
          Requirement {row.requirements.map((item) => `${item.number} (${item.status})`).join(", ")} uses this MTO.
          {onRequirement && (
            <button type="button" className="ed-link" onClick={() => onRequirement(row.requirements[0].id)}>
              Open requirement
            </button>
          )}
        </p>
      )}
      {showHistory && (
        <ol className="ed-timeline">
          {(row.history || []).map((item) => (
            <li key={item.id}>
              <div>
                <strong>{item.kind}</strong>
                {item.field && (
                  <p>
                    {item.field}: {item.old || "blank"} → {item.new || "blank"}
                  </p>
                )}
                {!item.field && item.new && <p>{item.new}</p>}
              </div>
              <small>
                {item.actor}
                <br />
                {when(item.at)}
              </small>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

type FulfilmentLine = {
  line_id: number;
  position: number;
  item_code: string;
  description: string;
  specification: string;
  unit: string;
  required: string;
  stock_allocated: string;
  on_requisitions: string;
  approved_requisitions: string;
  issued_orders: string;
  remaining_to_purchase: string;
  eligible_stock: { warehouse_id: number; warehouse: string; free: string; unit: string; note: string }[];
  suggested_allocations: { warehouse_id: number; quantity: string }[];
  allocations: { id: number; warehouse: string; quantity: string; unit: string; status: string; release_reason: string }[];
  drawing_number: string;
  drawing_revision_code: string;
  takeoff_number: string;
  takeoff_line_position: number | null;
  page: number | null;
};

type Fulfilment = {
  requirement_id: number;
  number: string;
  status: string;
  blocked: string;
  lines: FulfilmentLine[];
  can_allocate: boolean;
  can_requisition: boolean;
  note: string;
};

export function FulfilmentPanel({
  pid,
  requirementId,
  onError,
  onChanged,
}: {
  pid: number;
  requirementId: number;
  onError: (text: string) => void;
  onChanged?: () => void;
}) {
  const [data, setData] = useState<Fulfilment | null>(null);
  const [busy, setBusy] = useState(false);
  const [made, setMade] = useState("");
  const [pr, setPr] = useState({ number: "", request_date: today(), required_delivery: "", justification: "" });
  const base = `/projects/${pid}/procurement/requirements/${requirementId}`;
  async function load() {
    const fresh = await api<Fulfilment>(`${base}/fulfilment`);
    setData(fresh);
    setPr((value) => ({
      ...value,
      number: value.number || `PR-${fresh.number}`,
      justification: value.justification || `Uncovered quantity for ${fresh.number}`,
    }));
  }
  useEffect(() => {
    void load().catch((err) => onError((err as Error).message));
  }, [pid, requirementId]);
  if (!data) return null;
  async function run(work: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);
    try {
      await work();
      onError("");
      await load();
      onChanged?.();
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const suggestions = data.lines.flatMap((line) => line.suggested_allocations.map((item) => ({ line_id: line.line_id, ...item })));
  return (
    <div className="mto-fulfil">
      <h4>
        <PackageCheck size={16} /> Stock and purchase check
      </h4>
      {data.blocked ? <p className="note-card note-alert">{data.blocked}</p> : <p className="muted">{data.note}</p>}
      <div className="mto-table-wrap">
        <table className="mto-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Item</th>
              <th>Required</th>
              <th>Stock allocated</th>
              <th>On requisitions</th>
              <th>Issued orders</th>
              <th>Remaining to buy</th>
              <th>Free project stock</th>
              <th>Drawing / MTO trace</th>
            </tr>
          </thead>
          <tbody>
            {data.lines.map((line) => (
              <tr key={line.line_id}>
                <td>{line.position}</td>
                <td>
                  <strong>{line.item_code}</strong> {line.description}
                  {line.specification ? <small> · {line.specification}</small> : null}
                </td>
                <td className="mto-num">{line.required} {line.unit}</td>
                <td className="mto-num">
                  {line.stock_allocated}
                  {line.allocations.map((item) => (
                    <div key={item.id} className="mto-alloc">
                      {item.warehouse} {item.quantity} <Pill value={item.status} />
                      {item.status === "Active" && data.can_allocate && (
                        <button
                          type="button"
                          className="ed-link"
                          onClick={() => {
                            const why = window.prompt("Why is this stock released?");
                            if (why) void run(() => api(`${base}/allocations/${item.id}/release`, "POST", { reason: why }));
                          }}
                        >
                          Release
                        </button>
                      )}
                    </div>
                  ))}
                </td>
                <td className="mto-num">{line.on_requisitions}</td>
                <td className="mto-num">{line.issued_orders}</td>
                <td className="mto-num">
                  <strong>{line.remaining_to_purchase}</strong>
                </td>
                <td>
                  {line.eligible_stock.length === 0
                    ? "None"
                    : line.eligible_stock.map((item) => (
                        <div key={item.warehouse_id} title={item.note}>
                          {item.warehouse}: {item.free} {item.unit}
                        </div>
                      ))}
                </td>
                <td>
                  {line.drawing_number ? `${line.drawing_number} rev ${line.drawing_revision_code}` : "Manual"}
                  {line.takeoff_number ? <small> · {line.takeoff_number} line {line.takeoff_line_position}{line.page ? ` p${line.page}` : ""}</small> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mto-actions">
        {data.can_allocate && suggestions.length > 0 && (
          <button type="button" className="tone-note" disabled={busy} onClick={() => void run(() => api(`${base}/allocations`, "POST", { lines: suggestions }))}>
            Allocate free stock first ({suggestions.length})
          </button>
        )}
      </div>
      {data.can_requisition && (
        <form
          className="mto-requirement"
          onSubmit={(event) => {
            event.preventDefault();
            void run(async () => {
              const created = await api<{ number: string }>(`${base}/requisition`, "POST", pr);
              setMade(created.number);
            });
          }}
        >
          <h4>
            <ShoppingCart size={16} /> Purchase requisition for the uncovered quantity
          </h4>
          <label>
            PR number
            <input required value={pr.number} onChange={(e) => setPr({ ...pr, number: e.target.value })} />
          </label>
          <label>
            Request date
            <input required type="date" value={pr.request_date} onChange={(e) => setPr({ ...pr, request_date: e.target.value })} />
          </label>
          <label>
            Required delivery
            <input required type="date" value={pr.required_delivery} onChange={(e) => setPr({ ...pr, required_delivery: e.target.value })} />
          </label>
          <label className="mto-wide">
            Justification
            <input required value={pr.justification} onChange={(e) => setPr({ ...pr, justification: e.target.value })} />
          </label>
          <button type="submit" className="tone-submit" disabled={busy}>
            Create draft requisition
          </button>
        </form>
      )}
      {made && <p className="note-card note-good">Draft requisition {made} created. Submit it from Procurement → Requisitions. No purchase order is created automatically.</p>}
    </div>
  );
}

type NeedRow = {
  requirement_id: number;
  number: string;
  source: string;
  purpose: string;
  required_date: string;
  priority: string;
  impact_state: string;
  drawing_number: string;
  drawing_revision_code: string;
  takeoff_number: string;
  lines: FulfilmentLine[];
};

export function PurchaseNeeds({
  pid,
  onError,
  onOpen,
}: {
  pid: number;
  onError: (text: string) => void;
  onOpen: (requirementId: number) => void;
}) {
  const [data, setData] = useState<{ items: NeedRow[]; note: string } | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [checking, setChecking] = useState<number | null>(null);
  async function load() {
    setData(await api(`/projects/${pid}/procurement/purchase-needs?show_all=${showAll}`));
  }
  useEffect(() => {
    void load().catch((err) => onError((err as Error).message));
  }, [pid, showAll]);
  if (!data) return null;
  return (
    <section className="panel">
      <h3 className="section-mark">
        <ShoppingCart size={18} strokeWidth={2.4} /> Approved Purchase Needs
      </h3>
      <p className="muted">{data.note}</p>
      <label className="ed-check">
        <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> Include fully covered requirements
      </label>
      {data.items.length === 0 && <p className="muted">No approved requirement is waiting for purchase.</p>}
      {data.items.map((row) => (
        <article key={row.requirement_id} className="mto-need">
          <header>
            <button type="button" className="ed-link" onClick={() => onOpen(row.requirement_id)}>
              {row.number}
            </button>
            <Pill value={row.source} /> <Pill value={row.priority} />
            {row.impact_state === "Review required" && <Pill value="Drawing impact" />}
            <span className="muted">
              {row.purpose} · required {row.required_date}
              {row.drawing_number ? ` · ${row.drawing_number} rev ${row.drawing_revision_code}` : ""}
              {row.takeoff_number ? ` · ${row.takeoff_number}` : ""}
            </span>
          </header>
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th>Required</th>
                <th>Stock allocated</th>
                <th>On requisitions</th>
                <th>Remaining to buy</th>
              </tr>
            </thead>
            <tbody>
              {row.lines.map((line) => (
                <tr key={line.line_id}>
                  <td>
                    <strong>{line.item_code}</strong> {line.description}
                  </td>
                  <td>{line.required} {line.unit}</td>
                  <td>{line.stock_allocated}</td>
                  <td>{line.on_requisitions}</td>
                  <td>
                    <strong>{line.remaining_to_purchase}</strong>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button type="button" className="tone-note" onClick={() => setChecking(checking === row.requirement_id ? null : row.requirement_id)}>
            {checking === row.requirement_id ? "Hide stock check" : "Check stock and raise requisition"}
          </button>
          {checking === row.requirement_id && (
            <FulfilmentPanel pid={pid} requirementId={row.requirement_id} onError={onError} onChanged={() => void load()} />
          )}
        </article>
      ))}
    </section>
  );
}

const REQ_TABS = ["Requirements", "Manual Requirement", "From Drawing / MTO", "Import Material List"] as const;
const REQ_ICON = {
  Requirements: ClipboardList,
  "Manual Requirement": PenLine,
  "From Drawing / MTO": Layers,
  "Import Material List": FileSpreadsheet,
} as const;
const REQ_TONE = {
  Requirements: "tone-req",
  "Manual Requirement": "tone-pr",
  "From Drawing / MTO": "tone-quote",
  "Import Material List": "tone-master",
} as const;

export function RequirementsHome({ session, initialProjectId = null }: { session: Session; initialProjectId?: number | null }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [pid, setPid] = useState<number | null>(initialProjectId);
  const [error, setError] = useState("");
  useEffect(() => {
    void api<Page<Project>>("/projects?limit=100")
      .then((page) => setProjects(page.items))
      .catch((err) => setError((err as Error).message));
  }, []);
  if (pid) {
    return (
      <>
        <button className="back" onClick={() => setPid(null)}>
          ← Projects
        </button>
        <RequirementsBoard pid={pid} session={session} />
      </>
    );
  }
  return (
    <section className="panel">
      <h2>Requirements & Requests</h2>
      <p className="muted">Open a project to raise, approve and follow material requirements.</p>
      {error ? <div className="error">{error}</div> : null}
      {projects.map((project) => (
        <button key={project.id} onClick={() => setPid(project.id || null)}>
          {project.code} · {project.name}
        </button>
      ))}
    </section>
  );
}

function RequirementsBoard({ pid, session }: { pid: number; session: Session }) {
  const [tab, setTab] = useState<(typeof REQ_TABS)[number]>("Requirements");
  const [error, setError] = useState("");
  const [context, setContext] = useState<Context | null>(null);
  const [rows, setRows] = useState<Requirement[]>([]);
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<Requirement | null>(null);
  async function loadRows(next = status) {
    const params = new URLSearchParams();
    if (next) params.set("status", next);
    setRows((await api<{ items: Requirement[] }>(`/projects/${pid}/procurement/requirements?${params}`)).items);
  }
  async function open(id: number) {
    setSelected(await api<Requirement>(`/projects/${pid}/procurement/requirements/${id}`));
    setTab("Requirements");
  }
  useEffect(() => {
    void api<Context>(`/projects/${pid}/procurement/context`).then(setContext).catch((err) => setError((err as Error).message));
  }, [pid]);
  useEffect(() => {
    if (tab === "Requirements") void loadRows().catch((err) => setError((err as Error).message));
  }, [tab, status, pid]);
  return (
    <section className="panel ed-shell">
      <div>
        <h2>Requirements & Requests</h2>
        <p className="muted">
          One requirement record serves engineering and procurement. Manual entry, a verified drawing MTO, or a material list import all create the same draft requirement, which follows the saved requirement approval route. Procurement links to this record and never copies it.
        </p>
      </div>
      {error ? <div role="alert" className="error">{error}</div> : null}
      <div className="proc-nav ed-nav">
        {REQ_TABS.map((name) => {
          const Icon = REQ_ICON[name];
          return (
            <button key={name} type="button" className={`proc-tab ${REQ_TONE[name]}${tab === name ? " is-on" : ""}`} aria-pressed={tab === name} onClick={() => setTab(name)}>
              <Icon size={14} strokeWidth={2.4} />
              <span>{name}</span>
            </button>
          );
        })}
      </div>
      {tab === "Requirements" && (
        <>
          <label>
            Status
            <select aria-label="Requirement status" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              <option value="open">Open</option>
              <option>Draft</option>
              <option>Pending Approval</option>
              <option>Approved</option>
              <option>Returned for Correction</option>
              <option>Rejected</option>
              <option>Cancelled</option>
            </select>
          </label>
          <table>
            <thead>
              <tr>
                <th>Number</th>
                <th>Source</th>
                <th>Purpose</th>
                <th>Discipline</th>
                <th>Drawing</th>
                <th>Status</th>
                <th>Fulfilment</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className={selected?.id === row.id ? "is-on" : ""}>
                  <td>
                    <button type="button" className="ed-link" onClick={() => void open(row.id).catch((err) => setError((err as Error).message))}>
                      {row.number}
                    </button>
                  </td>
                  <td>{row.source}</td>
                  <td>{row.purpose}</td>
                  <td>{row.discipline}</td>
                  <td>
                    {row.drawing_number ? `${row.drawing_number} rev ${row.drawing_revision_code}` : "-"}
                    {row.takeoff_number ? <small> · {row.takeoff_number}</small> : null}
                  </td>
                  <td>
                    <Pill value={row.status} />
                    {row.impact_state === "Review required" && <Pill value="Drawing impact" />}
                  </td>
                  <td>
                    <Pill value={row.fulfillment} />
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="muted">No requirements match this filter.</td>
                </tr>
              )}
            </tbody>
          </table>
          {selected && context && (
            <RequirementDetail
              pid={pid}
              row={selected}
              context={context}
              onChange={(row) => {
                setSelected(row);
                void loadRows();
              }}
              onError={setError}
            />
          )}
        </>
      )}
      {tab === "Manual Requirement" && context && (
        <ManualRequirement pid={pid} context={context} userId={session.user.id || 0} onError={setError} onCreated={(id) => void open(id)} />
      )}
      {tab === "From Drawing / MTO" && <FromDrawing pid={pid} userId={session.user.id || 0} onError={setError} onRequirement={(id) => void open(id)} />}
      {tab === "Import Material List" && <ImportMaterialList pid={pid} onError={setError} onSaved={() => setTab("Requirements")} />}
    </section>
  );
}

type DraftLine = { item_id: number; quantity: string; unit: string; specification: string; tag: string };

function ManualRequirement({
  pid,
  context,
  userId,
  onError,
  onCreated,
}: {
  pid: number;
  context: Context;
  userId: number;
  onError: (text: string) => void;
  onCreated: (id: number) => void;
}) {
  const [head, setHead] = useState({
    number: "",
    company_id: context.companies[0]?.id || 0,
    discipline_id: context.disciplines[0]?.id || 0,
    requested_by: context.people.some((person) => person.id === userId) ? userId : context.people[0]?.id || 0,
    required_date: "",
    priority: "Normal",
    purpose: "",
    remarks: "",
  });
  const [lines, setLines] = useState<DraftLine[]>([{ item_id: 0, quantity: "", unit: "", specification: "", tag: "" }]);
  const [busy, setBusy] = useState(false);
  const items = context.items.filter((item) => item.discipline_ids.includes(head.discipline_id));
  function setLine(index: number, values: Partial<DraftLine>) {
    setLines((current) => current.map((line, at) => (at === index ? { ...line, ...values } : line)));
  }
  if (!context.access.requirement_edit) {
    return <p className="ed-note">Raising a requirement needs requirement edit access on this project.</p>;
  }
  return (
    <form
      className="mto-requirement"
      onSubmit={(event) => {
        event.preventDefault();
        if (busy) return;
        setBusy(true);
        void api<Requirement>(`/projects/${pid}/procurement/requirements`, "POST", {
          ...head,
          lines: lines.map((line) => ({ ...line, required_date: head.required_date })),
        })
          .then((row) => {
            onError("");
            onCreated(row.id);
          })
          .catch((err) => onError((err as Error).message))
          .finally(() => setBusy(false));
      }}
    >
      <h4>
        <PenLine size={16} /> Manual Requirement
      </h4>
      <p className="muted">Creates a draft requirement. Submit it from the Requirements tab to start approval.</p>
      <label>
        Number
        <input required value={head.number} onChange={(e) => setHead({ ...head, number: e.target.value })} />
      </label>
      <label>
        Company
        <select value={head.company_id} onChange={(e) => setHead({ ...head, company_id: Number(e.target.value) })}>
          {context.companies.map((row) => (
            <option key={row.id} value={row.id}>{row.name}</option>
          ))}
        </select>
      </label>
      <label>
        Discipline
        <select value={head.discipline_id} onChange={(e) => setHead({ ...head, discipline_id: Number(e.target.value) })}>
          {context.disciplines.map((row) => (
            <option key={row.id} value={row.id}>{row.name}</option>
          ))}
        </select>
      </label>
      <label>
        Requested by
        <select value={head.requested_by} onChange={(e) => setHead({ ...head, requested_by: Number(e.target.value) })}>
          {context.people.map((row) => (
            <option key={row.id} value={row.id}>{row.name}</option>
          ))}
        </select>
      </label>
      <label>
        Required at site
        <input required type="date" value={head.required_date} onChange={(e) => setHead({ ...head, required_date: e.target.value })} />
      </label>
      <label>
        Priority
        <select value={head.priority} onChange={(e) => setHead({ ...head, priority: e.target.value })}>
          <option>Normal</option>
          <option>High</option>
          <option>Critical</option>
        </select>
      </label>
      <label className="mto-wide">
        Purpose
        <input required value={head.purpose} onChange={(e) => setHead({ ...head, purpose: e.target.value })} />
      </label>
      <div className="mto-wide mto-table-wrap">
        <table className="mto-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Specification</th>
              <th>Qty</th>
              <th>Unit</th>
              <th>Tag</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => (
              <tr key={index}>
                <td>
                  <select
                    required
                    aria-label={`Item ${index + 1}`}
                    value={line.item_id || ""}
                    onChange={(e) => {
                      const item = items.find((row) => row.id === Number(e.target.value));
                      setLine(index, { item_id: Number(e.target.value), unit: line.unit || item?.base_unit || "" });
                    }}
                  >
                    <option value="">Choose item</option>
                    {items.map((item) => (
                      <option key={item.id} value={item.id}>{item.code} · {item.description}</option>
                    ))}
                  </select>
                </td>
                <td><input aria-label={`Specification ${index + 1}`} value={line.specification} onChange={(e) => setLine(index, { specification: e.target.value })} /></td>
                <td className="mto-num"><input required aria-label={`Quantity ${index + 1}`} value={line.quantity} onChange={(e) => setLine(index, { quantity: e.target.value })} /></td>
                <td className="mto-unit"><input required aria-label={`Unit ${index + 1}`} value={line.unit} onChange={(e) => setLine(index, { unit: e.target.value })} /></td>
                <td><input aria-label={`Tag ${index + 1}`} value={line.tag} onChange={(e) => setLine(index, { tag: e.target.value })} /></td>
                <td>
                  {lines.length > 1 && (
                    <button type="button" className="ed-danger" aria-label={`Remove line ${index + 1}`} onClick={() => setLines(lines.filter((_line, at) => at !== index))}>
                      <Trash2 size={14} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button type="button" className="tone-note" onClick={() => setLines([...lines, { item_id: 0, quantity: "", unit: "", specification: "", tag: "" }])}>
        <Plus size={14} /> Add line
      </button>
      <button type="submit" className="tone-submit" disabled={busy}>
        Create draft requirement
      </button>
    </form>
  );
}

function FromDrawing({
  pid,
  userId,
  onError,
  onRequirement,
}: {
  pid: number;
  userId: number;
  onError: (text: string) => void;
  onRequirement: (id: number) => void;
}) {
  const [rows, setRows] = useState<Takeoff[] | null>(null);
  const [denied, setDenied] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [filter, setFilter] = useState("Verified");
  useEffect(() => {
    void api<Takeoff[]>(`/projects/${pid}/takeoffs?status=${encodeURIComponent(filter)}`)
      .then((list) => {
        setRows(list);
        setDenied("");
      })
      .catch((err) => setDenied((err as Error).message));
  }, [pid, filter]);
  if (denied) {
    return <p className="ed-note">Drawing MTOs need drawing access on this project: {denied}</p>;
  }
  return (
    <div className="mto-wrap">
      <p className="muted">
        Choose a drawing MTO. Only a verified MTO becomes a requirement. MTOs are extracted, imported or entered on the drawing in Engineering & Drawings → Drawing detail → Materials.
      </p>
      <label>
        MTO status
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option>Verified</option>
          <option>Pending Verification</option>
          <option>Draft</option>
          <option>Returned</option>
          <option value="">All</option>
        </select>
      </label>
      <table className="mto-list">
        <thead>
          <tr>
            <th>MTO</th>
            <th>Drawing</th>
            <th>Revision</th>
            <th>Discipline</th>
            <th>Status</th>
            <th>Lines</th>
            <th>Requirement</th>
          </tr>
        </thead>
        <tbody>
          {(rows || []).map((row) => (
            <tr key={row.id} className={openId === row.id ? "is-on" : ""}>
              <td>
                <button type="button" className="ed-link" onClick={() => setOpenId(row.id)}>
                  {row.number}
                </button>
              </td>
              <td>{row.drawing_number} · {row.drawing_title}</td>
              <td>Rev {row.revision_code}</td>
              <td>{row.discipline}</td>
              <td><Pill value={row.status} /></td>
              <td>{row.line_count}</td>
              <td>{row.requirements.map((item) => item.number).join(", ") || "-"}</td>
            </tr>
          ))}
          {rows && rows.length === 0 && (
            <tr>
              <td colSpan={7} className="muted">No MTO with this status.</td>
            </tr>
          )}
        </tbody>
      </table>
      {openId && <TakeoffReview key={openId} pid={pid} id={openId} userId={userId} onError={onError} onRequirement={onRequirement} />}
    </div>
  );
}

function ImportMaterialList({ pid, onError, onSaved }: { pid: number; onError: (text: string) => void; onSaved: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<{ errors: { row: number; messages: string[] }[]; requirements: { number: string; lines: number }[]; saved: number } | null>(null);
  const [busy, setBusy] = useState(false);
  function send(mode: string) {
    if (!file || busy) return;
    const data = new FormData();
    data.set("upload", file);
    setBusy(true);
    void postForm<typeof result>(`/projects/${pid}/procurement/requirement-import?mode=${mode}`, data)
      .then((value) => {
        setResult(value);
        onError("");
        if (value && value.saved) onSaved();
      })
      .catch((err) => onError((err as Error).message))
      .finally(() => setBusy(false));
  }
  return (
    <div className="mto-requirement">
      <h4>
        <FileSpreadsheet size={16} /> Import Material List
      </h4>
      <p className="muted">
        An Excel list with one row per line. Rows that share a number become one draft requirement. A list taken from a drawing should be imported on that drawing revision as an MTO instead, so it is verified and stays linked to the revision.
      </p>
      <button type="button" className="tone-note" onClick={() => void downloadFile(`/projects/${pid}/procurement/requirement-template`, "requirement-template.xlsx").catch((err) => onError((err as Error).message))}>
        <Download size={14} /> Download template
      </button>
      <label className="mto-wide">
        Excel file
        <input type="file" accept=".xlsx" onChange={(e) => { setFile(e.target.files?.[0] || null); setResult(null); }} />
      </label>
      <button type="button" className="tone-note" disabled={!file || busy} onClick={() => send("preview")}>
        Preview
      </button>
      {result && result.errors.length > 0 && (
        <ul className="mto-wide error">
          {result.errors.map((item) => (
            <li key={item.row}>Row {item.row}: {item.messages.join(", ")}</li>
          ))}
        </ul>
      )}
      {result && result.errors.length === 0 && result.requirements.length > 0 && (
        <>
          <p className="mto-wide">{result.requirements.map((item) => `${item.number} (${item.lines} line(s))`).join(", ")}</p>
          <button type="button" className="tone-submit" disabled={busy} onClick={() => send("confirm")}>
            Create {result.requirements.length} draft requirement(s)
          </button>
        </>
      )}
      {result && result.saved > 0 && <p className="note-card note-good mto-wide">{result.saved} draft requirement(s) created.</p>}
    </div>
  );
}
