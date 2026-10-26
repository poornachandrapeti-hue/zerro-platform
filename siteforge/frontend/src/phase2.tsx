import { FormEvent, useEffect, useState } from "react";
import { api, downloadFile, upload } from "./api";
import { RouteLockNotice, routeLocked, useSavedRoutes } from "./approval_levels";
import type { Project, Session, User } from "./types";

function Err({ text }: { text: string }) {
  return text ? (
    <div role="alert" className="error">
      {text}
    </div>
  ) : null;
}

type Review = {
  id: number;
  project_id?: number;
  state: string;
  attempt: number;
  version: number;
  subject?: string;
  actions: string[];
  decisions: {
    id: number;
    action: string;
    reason: string;
    attempt: number;
    reviewed_revision: number;
  }[];
};
type TaskRow = {
  id: number;
  project_id: number;
  title: string;
  status: string;
  evidence: string;
  priority: string;
  due_date: string | null;
  version: number;
  owner_id: number;
};
type Note = {
  id: number;
  title: string;
  body: string;
  read: boolean;
  project_id: number | null;
};
type FileRow = {
  id: number;
  name: string;
  title?: string;
  description?: string;
  category: string;
  active: boolean;
  size: number;
  uploaded_by?: string;
  created_at?: string;
};
const FILE_CATEGORIES = [
  "Contract/PO",
  "Scope of Work",
  "Site Layout",
  "Project Schedule",
  "Other Supporting Documents",
];

export function StatusPanel({
  project,
  reload,
}: {
  project: Project;
  reload: () => Promise<void>;
}) {
  const [target, setTarget] = useState("Planned");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api(`/projects/${project.id}/transitions`, "POST", {
        target,
        reason,
        version: project.version,
      });
      setError("");
      await reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <h3>Status change</h3>
      <p className="muted">
        Active is not chosen here. Submit an activation review after setup is
        complete.
      </p>
      <form className="toolbar" onSubmit={submit}>
        <select
          aria-label="Next status"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        >
          {["Planned", "On Hold", "Completed", "Cancelled"].map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
        <input
          aria-label="Status reason"
          placeholder="Reason when required"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <button className="primary">Apply status</button>
      </form>
      <Err text={error} />
    </section>
  );
}

export function AttachmentsPanel({
  pid,
  canUpload,
  canDelete,
  canCommercial,
}: {
  pid: number;
  canUpload: boolean;
  canDelete: boolean;
  canCommercial: boolean;
}) {
  const [items, setItems] = useState<FileRow[]>([]);
  const [category, setCategory] = useState("Scope of Work");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const categories = FILE_CATEGORIES.filter(
    (item) => item !== "Contract/PO" || canCommercial,
  );
  async function load() {
    setLoading(true);
    try {
      setItems(await api<FileRow[]>(`/projects/${pid}/files`));
      setError("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, [pid]);
  async function send(e: { preventDefault(): void }) {
    e.preventDefault();
    if (!file) return;
    try {
      await upload(`/projects/${pid}/files`, file, category, {
        title: title || file.name,
        description,
      });
      setFile(null);
      setTitle("");
      setDescription("");
      setNotice("Document uploaded.");
      setError("");
      await load();
    } catch (err) {
      setNotice("");
      setError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <h2>Documents</h2>
      <p className="muted">PDF, PNG, JPEG, or plain text up to 5 MB. Files stay private.</p>
      {canUpload && (
        <div className="toolbar">
          <input
            aria-label="Document title"
            placeholder="Document title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <select
            aria-label="Document category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            {categories.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <input
            aria-label="Document description"
            placeholder="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <input
            aria-label="Project file"
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <button className="primary" type="button" disabled={!file} onClick={(e) => void send(e)}>
            Upload
          </button>
        </div>
      )}
      <Err text={error} />
      {notice ? <div className="success">{notice}</div> : null}
      {loading ? <p className="muted">Loading documents…</p> : null}
      {!loading && items.length === 0 ? (
        <p className="muted">No documents yet.</p>
      ) : null}
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Category</th>
            <th>File</th>
            <th>Uploaded by</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                {item.title || item.name}
                {item.description ? <small>{item.description}</small> : null}
              </td>
              <td>{item.category}</td>
              <td>
                {item.name}
                <small>{item.active ? "Available" : "Removed"}</small>
              </td>
              <td>
                {item.uploaded_by || "—"}
                <small>{item.created_at ? item.created_at.slice(0, 10) : ""}</small>
              </td>
              <td>
                {item.active && (
                  <button
                    onClick={() =>
                      void downloadFile(`/projects/${pid}/files/${item.id}`, item.name).catch(
                        (err) => setError((err as Error).message),
                      )
                    }
                  >
                    Download
                  </button>
                )}
                {canDelete && item.active && (
                  <button
                    onClick={() =>
                      void api(`/projects/${pid}/files/${item.id}`, "DELETE")
                        .then(load)
                        .catch((err) => setError((err as Error).message))
                    }
                  >
                    Remove
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function ReviewsPanel({
  pid,
  session,
  reloadProject,
  canSubmit,
}: {
  pid: number;
  session: Session;
  reloadProject: () => Promise<void>;
  canSubmit: boolean;
}) {
  const [items, setItems] = useState<Review[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [reviewer, setReviewer] = useState(0);
  const [parallel, setParallel] = useState(0);
  const [nextStage, setNextStage] = useState(0);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const admin = session.user.organization_admin;
  const activationRoutes = useSavedRoutes(pid, "project.activation", admin);
  const activationLocked = routeLocked(activationRoutes, null, [2, 1]);
  async function load() {
    try {
      setItems(await api<Review[]>(`/projects/${pid}/reviews`));
      if (admin)
        setUsers(
          (await api<{ items: User[] }>("/users?offset=0&limit=100")).items,
        );
      setError("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, [pid]);
  async function savePolicy(e: FormEvent) {
    e.preventDefault();
    try {
      await api(`/projects/${pid}/approval-policies`, "POST", {
        record_type: "project.activation",
        allow_self_approval: false,
        stages: [
          {
            name: "Activation",
            rule: "all",
            reviewer_ids: [reviewer, parallel].filter((id) => id > 0),
          },
          ...(nextStage
            ? [{ name: "Second review", rule: "all", reviewer_ids: [nextStage] }]
            : []),
        ],
      });
      setError("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  async function act(review: Review, action: string) {
    try {
      if (action === "resubmit") {
        await api(`/reviews/${review.id}/resubmit`, "POST", { version: review.version });
      } else {
        await api(`/reviews/${review.id}/decisions`, "POST", {
          action,
          reason,
          version: review.version,
        });
      }
      setReason("");
      await load();
      await reloadProject();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <h2>Activation review</h2>
      <p className="muted">
        Approval activates the project only when setup is complete. A reviewer
        cannot approve their own submission.
      </p>
      {admin && activationLocked && (
        <RouteLockNotice target={{ projectId: pid, recordType: "project.activation", disciplineId: null }} />
      )}
      {admin && !activationLocked && (
        <form className="toolbar" onSubmit={savePolicy}>
          <select
            required
            aria-label="Reviewer"
            value={reviewer || ""}
            onChange={(e) => setReviewer(Number(e.target.value))}
          >
            <option value="">Choose reviewer</option>
            {users
              .filter((person) => person.active)
              .map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name}
                </option>
              ))}
          </select>
          <select
            aria-label="Parallel reviewer"
            value={parallel || ""}
            onChange={(e) => setParallel(Number(e.target.value))}
          >
            <option value="">No parallel reviewer</option>
            {users
              .filter((person) => person.active)
              .map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name}
                </option>
              ))}
          </select>
          <select
            aria-label="Second stage reviewer"
            value={nextStage || ""}
            onChange={(e) => setNextStage(Number(e.target.value))}
          >
            <option value="">No second stage</option>
            {users
              .filter((person) => person.active)
              .map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name}
                </option>
              ))}
          </select>
          <button className="primary">Save reviewer</button>
        </form>
      )}
      {canSubmit && (
        <button
          type="button"
          onClick={() =>
            void api(`/projects/${pid}/activation-reviews`, "POST")
              .then(() => load())
              .catch((err) => setError((err as Error).message))
          }
        >
          Submit activation
        </button>
      )}
      <Err text={error} />
      {loading ? <p className="muted">Loading reviews…</p> : null}
      {!loading && items.length === 0 ? <p className="muted">No reviews yet.</p> : null}
      {items.map((review) => (
        <article key={review.id}>
          <strong>
            {review.state} · attempt {review.attempt}
          </strong>
          <ul>
            {review.decisions.map((decision) => (
              <li key={decision.id}>
                {decision.action}
                {decision.reason ? `: ${decision.reason}` : ""}
              </li>
            ))}
          </ul>
          {review.actions.length > 0 && (
            <>
              <input
                aria-label="Decision reason"
                placeholder="Reason for return or rejection"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
              <div className="inline">
                {review.actions.map((action) => (
                  <button key={action} onClick={() => void act(review, action)}>
                    {action}
                  </button>
                ))}
              </div>
            </>
          )}
        </article>
      ))}
    </section>
  );
}

export function TasksPanel({ pid, admin }: { pid: number; admin: boolean }) {
  const [items, setItems] = useState<TaskRow[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [title, setTitle] = useState("");
  const [owner, setOwner] = useState(0);
  const [priority, setPriority] = useState("Normal");
  const [due, setDue] = useState("");
  const [recordType, setRecordType] = useState("task");
  const [hours, setHours] = useState(24);
  const [escalate, setEscalate] = useState(48);
  const [recipient, setRecipient] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  async function load() {
    try {
      setItems(await api<TaskRow[]>(`/projects/${pid}/tasks`));
      if (admin)
        setUsers((await api<{ items: User[] }>("/users?offset=0&limit=100")).items);
      setError("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, [pid]);
  return (
    <section className="panel">
      <h2>Project tasks</h2>
      {admin && (
        <>
          <form
            className="toolbar"
            onSubmit={(e) => {
              e.preventDefault();
              void api(`/projects/${pid}/tasks`, "POST", {
                title,
                owner_id: owner,
                priority,
                due_date: due || null,
              })
                .then(() => {
                  setTitle("");
                  return load();
                })
                .catch((err) => setError((err as Error).message));
            }}
          >
            <input
              required
              aria-label="Task title"
              placeholder="Task title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <select
              required
              aria-label="Task owner"
              value={owner || ""}
              onChange={(e) => setOwner(Number(e.target.value))}
            >
              <option value="">Owner</option>
              {users
                .filter((person) => person.active)
                .map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.name}
                  </option>
                ))}
            </select>
            <select
              aria-label="Priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
            >
              {["Low", "Normal", "High"].map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
            <input
              aria-label="Due date"
              type="date"
              value={due}
              onChange={(e) => setDue(e.target.value)}
            />
            <button className="primary">Add task</button>
          </form>
          <form
            className="toolbar"
            onSubmit={(e) => {
              e.preventDefault();
              void api(`/projects/${pid}/reminder-policies`, "POST", {
                record_type: recordType,
                reminder_hours: hours,
                escalate_after_hours: escalate,
                recipient_ids: recipient ? [recipient] : [],
              })
                .then(() => setError(""))
                .catch((err) => setError((err as Error).message));
            }}
          >
            <select
              aria-label="Reminder record type"
              value={recordType}
              onChange={(e) => setRecordType(e.target.value)}
            >
              <option value="task">Tasks</option>
              <option value="project.activation">Activation reviews</option>
            </select>
            <input
              aria-label="Reminder hours"
              type="number"
              min={0}
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
            />
            <input
              aria-label="Escalation hours"
              type="number"
              min={0}
              value={escalate}
              onChange={(e) => setEscalate(Number(e.target.value))}
            />
            <select
              aria-label="Escalation recipient"
              value={recipient || ""}
              onChange={(e) => setRecipient(Number(e.target.value))}
            >
              <option value="">Escalation recipient</option>
              {users
                .filter((person) => person.active)
                .map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.name}
                  </option>
                ))}
            </select>
            <button>Save reminder timing</button>
          </form>
        </>
      )}
      <Err text={error} />
      {loading ? <p className="muted">Loading tasks…</p> : null}
      {!loading && items.length === 0 ? <p className="muted">No tasks yet.</p> : null}
      <TaskTable items={items} reload={load} />
    </section>
  );
}

export function MyTasksPage() {
  const [items, setItems] = useState<TaskRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  async function load() {
    try {
      setItems(await api<TaskRow[]>("/tasks"));
      setError("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  return (
    <section className="panel">
      <h2>My tasks</h2>
      <Err text={error} />
      {loading ? <p className="muted">Loading tasks…</p> : null}
      {!loading && items.length === 0 ? <p className="muted">No tasks assigned to you.</p> : null}
      <TaskTable items={items} reload={load} />
    </section>
  );
}

function TaskTable({ items, reload }: { items: TaskRow[]; reload: () => Promise<void> }) {
  const [evidence, setEvidence] = useState("");
  return (
    <table>
      <thead>
        <tr>
          <th>Task</th>
          <th>Status</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {items.map((task) => (
          <tr key={task.id}>
            <td>
              {task.title}
              <small>{task.evidence}</small>
            </td>
            <td>{task.status}</td>
            <td>
              {task.status !== "Completed" && task.status !== "Cancelled" && (
                <div className="inline">
                  <input
                    aria-label="Completion evidence"
                    placeholder="Evidence"
                    value={evidence}
                    onChange={(e) => setEvidence(e.target.value)}
                  />
                  {["In Progress", "Blocked", "Completed", "Cancelled"].map((status) => (
                    <button
                      key={status}
                      onClick={() =>
                        void api(`/tasks/${task.id}`, "POST", {
                          status,
                          evidence,
                          version: task.version,
                        })
                          .then(reload)
                          .catch((err) => alert((err as Error).message))
                      }
                    >
                      {status}
                    </button>
                  ))}
                </div>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function HistoryPanel({ pid }: { pid: number }) {
  const [data, setData] = useState<{
    audits: {
      id: number;
      action: string;
      resource: string;
      actor?: string;
      created_at?: string;
      details?: { before?: Record<string, string>; after?: Record<string, string> };
    }[];
    decisions: { action: string; reason: string; attempt: number }[];
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    void api<NonNullable<typeof data>>(`/projects/${pid}/history`)
      .then(setData)
      .catch((err) => {
        setData({ audits: [], decisions: [] });
        setError((err as Error).message);
      });
  }, [pid]);
  return (
    <section className="panel">
      <h2>History</h2>
      <Err text={error} />
      {!data ? <p className="muted">Loading history…</p> : null}
      {data && data.audits.length === 0 && data.decisions.length === 0 ? (
        <p className="muted">No history yet.</p>
      ) : null}
      <ul>
        {data?.decisions.map((row, index) => (
          <li key={`d${index}`}>
            Review {row.action} on attempt {row.attempt}
            {row.reason ? `: ${row.reason}` : ""}
          </li>
        ))}
        {data?.audits.map((row) => {
          const before = row.details?.before || {};
          const after = row.details?.after || {};
          const changed = Object.keys(after).filter((key) => before[key] !== after[key]);
          return (
            <li key={row.id}>
              {row.action} · {row.resource}
              {row.actor ? ` · ${row.actor}` : ""}
              {row.created_at ? ` · ${row.created_at.slice(0, 16).replace("T", " ")}` : ""}
              {changed.length ? ` · ${changed.join(", ")}` : ""}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function decisionClass(action: string) {
  if (action === "approve") return "tone-approve";
  if (action === "approve_with_comments") return "tone-comments";
  if (action === "return") return "tone-return";
  if (action === "reject") return "tone-reject";
  return "tone-note";
}

function decisionLabel(action: string) {
  if (action === "approve") return "Approve";
  if (action === "approve_with_comments") return "Approve with comments";
  if (action === "return") return "Return";
  if (action === "reject") return "Reject";
  if (action === "resubmit") return "Resubmit";
  return action;
}

function InboxReview({
  review,
  onDone,
  onOpen,
}: {
  review: Review;
  onDone: () => void;
  onOpen: (id: number) => void;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const choices = review.actions.filter((action) => action !== "comment");
  async function act(action: string) {
    if ((action === "reject" || action === "return" || action === "approve_with_comments") && !reason.trim()) {
      setError("Type the reason, then choose Return, Reject, or Approve with comments.");
      return;
    }
    try {
      if (action === "resubmit") {
        await api(`/reviews/${review.id}/resubmit`, "POST", { version: review.version });
      } else {
        await api(`/reviews/${review.id}/decisions`, "POST", { action, reason, version: review.version });
      }
      setError("");
      setReason("");
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <article className="comment-card">
      <strong>
        {review.subject || `Project ${review.project_id}`} · {review.state}
      </strong>
      <Err text={error} />
      {choices.length > 0 ? (
        <>
          <input
            aria-label="Decision reason"
            placeholder="Reason, required for Return and Reject"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <div className="inline decision-actions">
            {choices.map((action) => (
              <button key={action} type="button" className={decisionClass(action)} onClick={() => void act(action)}>
                {decisionLabel(action)}
              </button>
            ))}
          </div>
        </>
      ) : (
        <p className="muted">No decision is waiting for you on this review.</p>
      )}
      {review.project_id ? (
        <button type="button" onClick={() => onOpen(review.project_id as number)}>
          Open project
        </button>
      ) : null}
    </article>
  );
}

export function InboxPage({ openProject }: { openProject: (id: number) => void }) {
  const [items, setItems] = useState<Review[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  function load() {
    setLoading(true);
    void api<Review[]>("/reviews")
      .then((rows) => {
        setItems(rows);
        setError("");
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }
  useEffect(() => {
    load();
  }, []);
  return (
    <section className="panel">
      <h2>Approval inbox</h2>
      <Err text={error} />
      {loading ? <p className="muted">Loading reviews…</p> : null}
      {!loading && items.length === 0 ? <p className="muted">No reviews need attention.</p> : null}
      {items.map((review) => (
        <InboxReview key={review.id} review={review} onDone={load} onOpen={openProject} />
      ))}
    </section>
  );
}

function noteTone(title: string) {
  const text = title.toLowerCase();
  if (text.includes("reject") || text.includes("return")) return "note-bad";
  if (text.includes("approved") || text.includes("accepted") || text.includes("moved")) return "note-good";
  if (text.includes("required") || text.includes("waiting") || text.includes("assigned")) return "note-alert";
  return "";
}

export function NotificationsPage({
  openProject,
  onChange,
}: {
  openProject: (id: number) => void;
  onChange?: () => void;
}) {
  const [items, setItems] = useState<Note[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  async function load() {
    try {
      setItems(await api<Note[]>("/notifications"));
      setError("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  return (
    <section className="panel">
      <h2>Notifications</h2>
      <p className="muted">Email delivery stays off until it is configured.</p>
      <Err text={error} />
      {loading ? <p className="muted">Loading notifications…</p> : null}
      {!loading && items.length === 0 ? <p className="muted">No notifications.</p> : null}
      {items.map((note) => (
        <article key={note.id} className={`note-card ${noteTone(note.title)} ${note.read ? "" : "unread"}`}>
          <strong>{note.title}</strong>
          <p>{note.body}</p>
          {note.project_id ? (
            <button onClick={() => openProject(note.project_id as number)}>
              Open project
            </button>
          ) : null}
          {!note.read && (
            <button
              onClick={() =>
                void api(`/notifications/${note.id}/read`, "POST").then(() => {
                  onChange?.();
                  return load();
                })
              }
            >
              Mark read
            </button>
          )}
        </article>
      ))}
    </section>
  );
}
