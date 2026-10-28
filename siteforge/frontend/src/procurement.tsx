import { FormEvent, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowLeftRight,
  Building2,
  ClipboardCheck,
  ClipboardList,
  BadgeCheck,
  PackageSearch,
  FileSearch,
  FileSpreadsheet,
  Pencil,
  ScrollText,
  Send,
  LayoutDashboard,
  Lock,
  Package,
  Receipt,
  Scale,
  ShoppingCart,
  Truck,
  Warehouse,
} from "lucide-react";
import { api, postForm } from "./api";
import { RouteLockNotice, routeLocked } from "./approval_levels";
import { FulfilmentPanel, PurchaseNeeds } from "./materials";
import type { Catalog, Page, Project, Session } from "./types";

function Err({ text }: { text: string }) {
  return text ? (
    <div role="alert" className="error">
      {text}
    </div>
  ) : null;
}

function actionClass(action: string) {
  if (action === "approve") return "tone-approve";
  if (action === "return") return "tone-return";
  if (action === "reject") return "tone-reject";
  return "tone-note";
}

function slug(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function Pill({ value }: { value: string }) {
  return <span className={`state-pill state-${slug(value)}`}>{value}</span>;
}

const RFQ_FLOW = [
  { name: "Draft", hint: "Save lines and vendors", icon: Pencil, tone: "stage-draft" },
  { name: "Awaiting quotations", hint: "Record each price", icon: Send, tone: "stage-awaiting" },
  { name: "Technical review", hint: "Saved reviewer decides", icon: ClipboardCheck, tone: "stage-technical" },
  { name: "Commercial comparison", hint: "Compare, do not auto-pick", icon: Scale, tone: "stage-commercial" },
  { name: "Awarded", hint: "Chosen by hand", icon: BadgeCheck, tone: "stage-awarded" },
] as const;

function rfqStepLabel(status: string) {
  if (status === "current") return "This step";
  if (status === "done") return "Complete";
  if (status === "stopped") return "Stopped";
  return "Later";
}

function stepLabel(status: string) {
  if (status === "current") return "Now";
  if (status === "done") return "Approved";
  if (status === "stopped") return "Stopped";
  return "Not started";
}

const TAB_ICON = {
  Dashboard: LayoutDashboard,
  Requirements: ClipboardList,
  "Approved Purchase Needs": PackageSearch,
  Requisitions: ShoppingCart,
  Quotations: FileSearch,
  "Purchase orders": ScrollText,
  "Goods receipts": Truck,
  Stock: Warehouse,
  Invoices: Receipt,
  "Master data": Package,
  "Later steps": Lock,
} as const;

const TAB_TONE = {
  Dashboard: "tone-dash",
  Requirements: "tone-req",
  "Approved Purchase Needs": "tone-needs",
  Requisitions: "tone-pr",
  Quotations: "tone-quote",
  "Purchase orders": "tone-po",
  "Goods receipts": "tone-receipt",
  Stock: "tone-stock",
  Invoices: "tone-invoice",
  "Master data": "tone-master",
  "Later steps": "tone-later",
} as const;

type Line = {
  id?: number;
  item_id: number;
  quantity: string;
  unit: string;
  required_date: string;
  tag: string;
  engineering_reference?: string;
  item_code?: string;
  description?: string;
  remaining_for_requisition?: string;
  reserved_quantity?: string;
  approved_requisition_quantity?: string;
  outstanding_quantity?: string;
  accepted_stock_quantity?: string;
  estimated_price?: string | null;
  requirement_line_id?: number;
  specification?: string;
  planning_wbs_id?: number | null;
  requirement_number?: string;
  wbs_code?: string;
  wbs_name?: string;
};

type Review = {
  id: number;
  state: string;
  version: number;
  subject?: string;
  actions: string[];
  chain?: { name: string; purpose: string; status: string; reviewers: { name: string }[] }[];
  decisions: { id: number; action: string; reason: string; reviewer_name?: string }[];
};

export type Requirement = {
  id: number;
  number: string;
  status: string;
  source: string;
  drawing_number: string;
  drawing_revision_code: string;
  takeoff_id: number | null;
  takeoff_number: string;
  fulfillment: string;
  purpose: string;
  priority: string;
  company: string;
  discipline: string;
  company_id: number;
  discipline_id: number;
  requested_by: number;
  required_date: string;
  remarks: string;
  drawing_id: number | null;
  drawing_revision_id: number | null;
  version: number;
  impact_state: string;
  impact_detail: string;
  impact_decision: string;
  cancellation_reason: string;
  work_packages?: { id: number; code: string; name: string; status: string }[];
  lines: Line[];
  review: Review | null;
};

type Requisition = {
  id: number;
  number: string;
  status: string;
  ordering: string;
  ordering_note: string;
  justification: string;
  currency: string;
  company: string;
  discipline: string;
  version: number;
  lines: Line[];
  review: Review | null;
};

export type Context = {
  disciplines: { id: number; name: string }[];
  companies: { id: number; name: string }[];
  people: { id: number; name: string; company_id: number }[];
  requirement_reviewers: { id: number; name: string }[];
  requisition_reviewers: { id: number; name: string }[];
  areas: { id: number; code: string; name: string }[];
  warehouses: { id: number; code: string; name: string }[];
  drawings: { id: number; number: string; revisions: { id: number; code: string }[] }[];
  wbs?: { id: number; code: string; name: string }[];
  work_packages?: { id: number; code: string; name: string; status: string; editable: boolean }[];
  items: { id: number; code: string; description: string; base_unit: string; discipline_ids: number[] }[];
  access: {
    requirement_edit: boolean;
    requirement_review: boolean;
    requisition_edit: boolean;
    requisition_review: boolean;
    rfq_edit: boolean;
    po_edit: boolean;
    receipt_edit: boolean;
    stock_edit: boolean;
    invoice_edit: boolean;
    commercial: boolean;
    master: boolean;
    admin: boolean;
  };
};

type Dash = {
  open_requirements: number;
  requisitions_pending: number;
  approved_lines_not_ordered: number;
  drawing_impacts: number;
  rfqs_awaiting: number;
  orders_pending: number;
  orders_awaiting_receipt: number;
  stock_on_hand: number;
  invoices_recorded: number;
  ordering_note: string;
  unavailable: { name: string; reason: string }[];
};

const TABS = ["Dashboard", "Requirements", "Approved Purchase Needs", "Requisitions", "Quotations", "Purchase orders", "Goods receipts", "Stock", "Invoices", "Master data", "Later steps"] as const;

export function ProcurementHome({
  session,
  catalog,
  initialProjectId = null,
}: {
  session: Session;
  catalog: Catalog;
  initialProjectId?: number | null;
}) {
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
        <ProcurementBoard pid={pid} session={session} catalog={catalog} />
      </>
    );
  }
  return (
    <section className="panel">
      <h2>Procurement</h2>
      <p className="muted">Open a project to manage its material requirements and purchase requisitions.</p>
      <Err text={error} />
      {projects.map((project) => (
        <button key={project.id} onClick={() => setPid(project.id || null)}>
          {project.code} · {project.name}
        </button>
      ))}
    </section>
  );
}

export function ProcurementBoard({
  pid,
  session,
  catalog,
}: {
  pid: number;
  session: Session;
  catalog: Catalog;
}) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Dashboard");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [dash, setDash] = useState<Dash | null>(null);
  const [context, setContext] = useState<Context | null>(null);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [selected, setSelected] = useState<Requirement | null>(null);
  const [selectedPr, setSelectedPr] = useState<Requisition | null>(null);
  const [status, setStatus] = useState("");
  const [prStatus, setPrStatus] = useState("");
  const [rfqStatus, setRfqStatus] = useState("");
  const [poStatus, setPoStatus] = useState("");
  const [receiptStatus, setReceiptStatus] = useState("");
  const [invoiceStatus, setInvoiceStatus] = useState("");

  async function load() {
    const [board, ctx] = await Promise.all([
      api<Dash>(`/projects/${pid}/procurement/dashboard`),
      api<Context>(`/projects/${pid}/procurement/context`),
    ]);
    setDash(board);
    setContext(ctx);
  }

  async function loadRequirements(next = status) {
    const params = new URLSearchParams();
    if (next) params.set("status", next);
    const page = await api<{ items: Requirement[] }>(`/projects/${pid}/procurement/requirements?${params}`);
    setRequirements(page.items);
  }

  async function loadRequisitions(next = prStatus) {
    const params = new URLSearchParams();
    if (next) params.set("status", next);
    const page = await api<{ items: Requisition[] }>(`/projects/${pid}/procurement/requisitions?${params}`);
    setRequisitions(page.items);
  }

  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);

  useEffect(() => {
    if (tab === "Requirements") void loadRequirements().catch((err) => setError((err as Error).message));
    if (tab === "Requisitions") void loadRequisitions().catch((err) => setError((err as Error).message));
  }, [tab, status, prStatus]);

  function openCard(nextTab: (typeof TABS)[number], nextStatus: string) {
    setTab(nextTab);
    if (nextTab === "Requirements") setStatus(nextStatus);
    if (nextTab === "Requisitions") setPrStatus(nextStatus);
    if (nextTab === "Quotations") setRfqStatus(nextStatus);
    if (nextTab === "Purchase orders") setPoStatus(nextStatus);
    if (nextTab === "Goods receipts") setReceiptStatus(nextStatus);
    if (nextTab === "Invoices") setInvoiceStatus(nextStatus);
  }

  return (
    <>
      <h2>Procurement</h2>
      <p className="muted">
        Requirements and requisitions use the saved review route. An award can become a purchase order. Goods receipts record what arrived. Stock changes only when that receipt is accepted into a warehouse. A vendor invoice records the supplier bill. Matching and payment stay closed.
      </p>
      <Err text={error} />
      {note ? <p className="note-card note-good">{note}</p> : null}
      <div className="proc-nav">
        {TABS.map((name) => {
          const Icon = TAB_ICON[name];
          return (
            <button
              key={name}
              className={`proc-tab ${TAB_TONE[name]}${tab === name ? " is-on" : ""}`}
              aria-pressed={tab === name}
              onClick={() => setTab(name)}
              type="button"
            >
              <Icon size={14} strokeWidth={2.4} />
              <span>{name}</span>
            </button>
          );
        })}
      </div>
      {tab === "Dashboard" && dash && (
        <section className="panel">
          <h3 className="section-mark">
            <LayoutDashboard size={18} strokeWidth={2.4} /> Dashboard
          </h3>
          <div className="dash-grid">
            <button type="button" className="dash-card" onClick={() => openCard("Requirements", "open")}>
              <span className="dash-mark"><ClipboardList size={15} strokeWidth={2.4} /></span>
              <strong>{dash.open_requirements}</strong>
              <span className="dash-label">Open requirements</span>
            </button>
            <button type="button" className="dash-card wait" onClick={() => openCard("Requisitions", "Pending Approval")}>
              <span className="dash-mark"><ShoppingCart size={15} strokeWidth={2.4} /></span>
              <strong>{dash.requisitions_pending}</strong>
              <span className="dash-label">Requisitions to approve</span>
            </button>
            <button type="button" className="dash-card order" onClick={() => openCard("Requisitions", "Approved")}>
              <span className="dash-mark"><Package size={15} strokeWidth={2.4} /></span>
              <strong>{dash.approved_lines_not_ordered}</strong>
              <span className="dash-label">Lines not ordered</span>
            </button>
            <button type="button" className="dash-card po" onClick={() => openCard("Purchase orders", "Pending Approval")}>
              <span className="dash-mark"><ScrollText size={15} strokeWidth={2.4} /></span>
              <strong>{dash.orders_pending}</strong>
              <span className="dash-label">Orders to approve</span>
            </button>
            <button type="button" className="dash-card stock" onClick={() => openCard("Stock", "")}>
              <span className="dash-mark"><Warehouse size={15} strokeWidth={2.4} /></span>
              <strong>{dash.stock_on_hand}</strong>
              <span className="dash-label">Items on hand</span>
            </button>
            <button type="button" className="dash-card invoice" onClick={() => openCard("Invoices", "Recorded")}>
              <span className="dash-mark"><Receipt size={15} strokeWidth={2.4} /></span>
              <strong>{dash.invoices_recorded}</strong>
              <span className="dash-label">Bills recorded</span>
            </button>
            <button type="button" className="dash-card receipt" onClick={() => openCard("Goods receipts", "")}>
              <span className="dash-mark"><Truck size={15} strokeWidth={2.4} /></span>
              <strong>{dash.orders_awaiting_receipt}</strong>
              <span className="dash-label">Awaiting receipt</span>
            </button>
            <button type="button" className="dash-card quote" onClick={() => openCard("Quotations", "Awaiting quotations")}>
              <span className="dash-mark"><FileSearch size={15} strokeWidth={2.4} /></span>
              <strong>{dash.rfqs_awaiting}</strong>
              <span className="dash-label">Quotes waiting</span>
            </button>
            <button
              type="button"
              className={dash.drawing_impacts > 0 ? "dash-card impact" : "dash-card quiet"}
              onClick={() => openCard("Requirements", "Approved")}
            >
              <span className="dash-mark"><AlertTriangle size={15} strokeWidth={2.4} /></span>
              <strong>{dash.drawing_impacts}</strong>
              <span className="dash-label">Drawing impacts</span>
            </button>
          </div>
          <p className="note-card">{dash.ordering_note}</p>
          {context?.access.admin && <PolicyForms pid={pid} context={context} catalog={catalog} onSaved={setNote} onError={setError} />}
        </section>
      )}
      {tab === "Requirements" && context && (
        <Requirements
          pid={pid}
          context={context}
          rows={requirements}
          status={status}
          selected={selected}
          onStatus={setStatus}
          onOpen={async (id) => {
            const row = await api<Requirement>(`/projects/${pid}/procurement/requirements/${id}`);
            setSelected(row);
          }}
          onChange={(row) => {
            setSelected(row);
            void loadRequirements();
            void load();
          }}
          onError={setError}
        />
      )}
      {tab === "Approved Purchase Needs" && (
        <PurchaseNeeds
          pid={pid}
          onError={setError}
          onOpen={async (id) => {
            const row = await api<Requirement>(`/projects/${pid}/procurement/requirements/${id}`);
            setSelected(row);
            setTab("Requirements");
          }}
        />
      )}
      {tab === "Requisitions" && context && (
        <Requisitions
          pid={pid}
          context={context}
          rows={requisitions}
          status={prStatus}
          selected={selectedPr}
          requirements={requirements}
          onStatus={setPrStatus}
          onOpen={async (id) => {
            const row = await api<Requisition>(`/projects/${pid}/procurement/requisitions/${id}`);
            setSelectedPr(row);
          }}
          onNeedRequirements={() => void loadRequirements("Approved")}
          onChange={(row) => {
            setSelectedPr(row);
            void loadRequisitions();
            void load();
          }}
          onError={setError}
        />
      )}
      {tab === "Quotations" && context && (
        <Rfqs
          pid={pid}
          context={context}
          status={rfqStatus}
          onStatus={setRfqStatus}
          onError={setError}
        />
      )}
      {tab === "Purchase orders" && context && (
        <Orders
          pid={pid}
          context={context}
          status={poStatus}
          onStatus={setPoStatus}
          onError={setError}
        />
      )}
      {tab === "Goods receipts" && context && (
        <Receipts pid={pid} context={context} status={receiptStatus} onStatus={setReceiptStatus} onError={setError} />
      )}
      {tab === "Stock" && context && <Stock pid={pid} context={context} onError={setError} />}
      {tab === "Invoices" && context && (
        <Invoices pid={pid} context={context} status={invoiceStatus} onStatus={setInvoiceStatus} onError={setError} />
      )}
      {tab === "Master data" && context && (
        <Masters pid={pid} session={session} catalog={catalog} context={context} onSaved={() => void load()} onError={setError} />
      )}
      {tab === "Later steps" && dash && (
        <section className="panel">
          <h3 className="section-mark">
            <Lock size={18} strokeWidth={2.4} /> Not open yet
          </h3>
          <p>These steps stay closed. Matching and payment are not open.</p>
          <ul className="closed-list">
            {dash.unavailable.map((item) => (
              <li key={item.name} className="closed-step">
                <Lock size={16} strokeWidth={2.4} />
                <div>
                  <strong>{item.name}</strong>
                  <p>{item.reason}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

type SavedRoute = {
  id: number;
  discipline_id: number | null;
  stages: { name: string; reviewers: { id: number; name: string }[] }[];
};

function PolicyForms({
  pid,
  context,
  catalog,
  onSaved,
  onError,
}: {
  pid: number;
  context: Context;
  catalog: Catalog;
  onSaved: (text: string) => void;
  onError: (text: string) => void;
}) {
  const [requirementReviewer, setRequirementReviewer] = useState(0);
  const [requisitionReviewer, setRequisitionReviewer] = useState(0);
  const [orderReviewer, setOrderReviewer] = useState(0);
  const [discipline, setDiscipline] = useState("");
  const [savedTick, setSavedTick] = useState(0);
  const [requirementRoutes, setRequirementRoutes] = useState<SavedRoute[]>([]);
  const [requisitionRoutes, setRequisitionRoutes] = useState<SavedRoute[]>([]);
  const [orderRoutes, setOrderRoutes] = useState<SavedRoute[]>([]);
  useEffect(() => {
    void Promise.all([
      api<SavedRoute[]>(`/projects/${pid}/approval-policies?record_type=procurement.requirement`),
      api<SavedRoute[]>(`/projects/${pid}/approval-policies?record_type=procurement.requisition`),
      api<SavedRoute[]>(`/projects/${pid}/approval-policies?record_type=procurement.purchase_order`),
    ])
      .then(([requirements, requisitions, purchaseOrders]) => {
        setRequirementRoutes(requirements);
        setRequisitionRoutes(requisitions);
        setOrderRoutes(purchaseOrders);
      })
      .catch(() => {
        setRequirementRoutes([]);
        setRequisitionRoutes([]);
        setOrderRoutes([]);
      });
  }, [pid, savedTick]);
  function savedReviewerId(rows: SavedRoute[]) {
    const wanted = discipline ? Number(discipline) : null;
    const match = rows.find((row) => row.discipline_id === wanted) || rows.find((row) => row.discipline_id == null) || rows[0];
    return match?.stages.flatMap((stage) => stage.reviewers)[0]?.id || context.people[0]?.id || 0;
  }
  useEffect(() => {
    setRequirementReviewer(savedReviewerId(requirementRoutes));
  }, [requirementRoutes, discipline]);
  useEffect(() => {
    setRequisitionReviewer(savedReviewerId(requisitionRoutes));
  }, [requisitionRoutes, discipline]);
  useEffect(() => {
    setOrderReviewer(savedReviewerId(orderRoutes));
  }, [orderRoutes, discipline]);
  function routeText(rows: SavedRoute[]) {
    if (!rows.length) return "Not set";
    return rows
      .map((row) => {
        const people = row.stages.flatMap((stage) => stage.reviewers.map((person) => person.name)).join(", ") || "Not set";
        const scope = context.disciplines.find((item) => item.id === row.discipline_id)?.name || "All disciplines";
        return `${people} · ${scope}`;
      })
      .join("; ");
  }
  const disciplineId = discipline ? Number(discipline) : null;
  const requirementLocked = routeLocked(requirementRoutes, disciplineId);
  const requisitionLocked = routeLocked(requisitionRoutes, disciplineId);
  const orderLocked = routeLocked(orderRoutes, disciplineId);
  async function save(recordType: string, reviewer: number) {
    try {
      await api(`/projects/${pid}/approval-policies`, "POST", {
        record_type: recordType,
        discipline_id: discipline ? Number(discipline) : null,
        allow_self_approval: false,
        stages: [{ name: recordType.endsWith("requirement") && !recordType.endsWith("purchase_order") ? "Discipline review" : recordType.endsWith("purchase_order") ? "Order approval" : "Procurement review", rule: "all", reviewer_ids: [reviewer] }],
      });
      onError("");
      setSavedTick((value) => value + 1);
      onSaved("Review route saved. The saved route above is the one in use. Only that assigned person can approve, and they cannot approve their own submission.");
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <div className="option-grid">
      <h3 className="section-mark">
        <Lock size={18} strokeWidth={2.4} /> Review route
      </h3>
      <div className="policy-saved">
        <h3>Saved route</h3>
        <dl>
          <dt>Requirement reviewer</dt>
          <dd>{routeText(requirementRoutes)}</dd>
          <dt>Requisition reviewer</dt>
          <dd>{routeText(requisitionRoutes)}</dd>
          <dt>Purchase order reviewer</dt>
          <dd>{routeText(orderRoutes)}</dd>
        </dl>
      </div>
      <p className="muted">Pick a project member and save. That saved person is the one who can approve.</p>
      <label>
        Discipline
        <select aria-label="Policy discipline" value={discipline} onChange={(e) => setDiscipline(e.target.value)}>
          <option value="">All disciplines</option>
          {context.disciplines.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Requirement reviewer
        <select aria-label="Requirement reviewer" disabled={requirementLocked} value={requirementReviewer} onChange={(e) => setRequirementReviewer(Number(e.target.value))}>
          {context.people.map((person) => (
            <option key={person.id} value={person.id}>
              {person.name}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="tone-submit" disabled={requirementLocked || !requirementReviewer} onClick={() => void save("procurement.requirement", requirementReviewer)}>
        Save requirement route
      </button>
      {requirementLocked ? <RouteLockNotice target={{ projectId: pid, recordType: "procurement.requirement", disciplineId }} /> : null}
      <label>
        Requisition reviewer
        <select aria-label="Requisition reviewer" disabled={requisitionLocked} value={requisitionReviewer} onChange={(e) => setRequisitionReviewer(Number(e.target.value))}>
          {context.people.map((person) => (
            <option key={person.id} value={person.id}>
              {person.name}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="tone-submit" disabled={requisitionLocked || !requisitionReviewer} onClick={() => void save("procurement.requisition", requisitionReviewer)}>
        Save requisition route
      </button>
      {requisitionLocked ? <RouteLockNotice target={{ projectId: pid, recordType: "procurement.requisition", disciplineId }} /> : null}
      <label>
        Purchase order reviewer
        <select aria-label="Purchase order reviewer" disabled={orderLocked} value={orderReviewer} onChange={(e) => setOrderReviewer(Number(e.target.value))}>
          {context.people.map((person) => (
            <option key={person.id} value={person.id}>
              {person.name}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="tone-submit" disabled={orderLocked || !orderReviewer} onClick={() => void save("procurement.purchase_order", orderReviewer)}>
        Save purchase order route
      </button>
      {orderLocked ? <RouteLockNotice target={{ projectId: pid, recordType: "procurement.purchase_order", disciplineId }} /> : null}
    </div>
  );
}

function Requirements({
  pid,
  context,
  rows,
  status,
  selected,
  onStatus,
  onOpen,
  onChange,
  onError,
}: {
  pid: number;
  context: Context;
  rows: Requirement[];
  status: string;
  selected: Requirement | null;
  onStatus: (value: string) => void;
  onOpen: (id: number) => Promise<void>;
  onChange: (row: Requirement) => void;
  onError: (text: string) => void;
}) {
  return (
    <>
      <label>
        Status
        <select aria-label="Requirement status" value={status} onChange={(e) => onStatus(e.target.value)}>
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
            <th>Status</th>
            <th>Fulfillment</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                <button type="button" onClick={() => void onOpen(row.id).catch((err) => onError((err as Error).message))}>
                  {row.number}
                </button>
              </td>
              <td>
                {row.source}
                {row.drawing_number ? <small> · {row.drawing_number} rev {row.drawing_revision_code}</small> : null}
              </td>
              <td>{row.purpose}</td>
              <td>{row.discipline}</td>
              <td><Pill value={row.status} /></td>
              <td><Pill value={row.fulfillment} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      {context.access.requirement_edit && <RequirementForm pid={pid} context={context} onChange={onChange} onError={onError} />}
      {selected && <RequirementDetail pid={pid} row={selected} context={context} onChange={onChange} onError={onError} />}
    </>
  );
}

function RequirementForm({
  pid,
  context,
  onChange,
  onError,
}: {
  pid: number;
  context: Context;
  onChange: (row: Requirement) => void;
  onError: (text: string) => void;
}) {
  const [number, setNumber] = useState("");
  const [company, setCompany] = useState(context.companies[0]?.id || 0);
  const [discipline, setDiscipline] = useState(context.disciplines[0]?.id || 0);
  const [person, setPerson] = useState(context.people[0]?.id || 0);
  const [required, setRequired] = useState("");
  const [priority, setPriority] = useState("Normal");
  const [purpose, setPurpose] = useState("");
  const [item, setItem] = useState(0);
  const [quantity, setQuantity] = useState("");
  const [drawing, setDrawing] = useState("");
  const [revision, setRevision] = useState("");
  const [wbs, setWbs] = useState("");
  const [workPackage, setWorkPackage] = useState("");
  const chosen = context.drawings.find((row) => String(row.id) === drawing);
  const items = context.items.filter((row) => !discipline || row.discipline_ids.includes(discipline));
  const unit = items.find((row) => row.id === item)?.base_unit || "";
  const packages = (context.work_packages || []).filter((row) => row.editable);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const row = await api<Requirement>(`/projects/${pid}/procurement/requirements`, "POST", {
        number,
        company_id: company,
        discipline_id: discipline,
        requested_by: person,
        required_date: required,
        priority,
        purpose,
        drawing_id: drawing ? Number(drawing) : null,
        drawing_revision_id: revision ? Number(revision) : null,
        work_package_ids: workPackage ? [Number(workPackage)] : [],
        lines: [{ item_id: item, quantity, unit, required_date: required, tag: "", planning_wbs_id: wbs ? Number(wbs) : null }],
      });
      onError("");
      onChange(row);
      setNumber("");
      setPurpose("");
      setQuantity("");
      setWbs("");
      setWorkPackage("");
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <form className="option-grid" onSubmit={(event) => void submit(event)}>
      <h3>New requirement</h3>
      <p>A quick one-line requirement. Multi-line manual entry, drawing MTOs and material list imports are in Requirements & Requests. A drawing revision from this project can be linked here as a reference.</p>
      <label>
        Number
        <input aria-label="Requirement number" value={number} onChange={(e) => setNumber(e.target.value)} required />
      </label>
      <label>
        Company
        <select aria-label="Requesting company" value={company} onChange={(e) => setCompany(Number(e.target.value))}>
          {context.companies.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Discipline
        <select aria-label="Requirement discipline" value={discipline} onChange={(e) => { setDiscipline(Number(e.target.value)); setItem(0); }} required>
          <option value={0}>Select discipline</option>
          {context.disciplines.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Requested by
        <select aria-label="Requested by" value={person} onChange={(e) => setPerson(Number(e.target.value))}>
          {context.people.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Required at site
        <input aria-label="Required date" type="date" value={required} onChange={(e) => setRequired(e.target.value)} required />
      </label>
      <label>
        Priority
        <select aria-label="Priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option>Normal</option>
          <option>High</option>
          <option>Critical</option>
        </select>
      </label>
      <label>
        Purpose
        <input aria-label="Purpose" value={purpose} onChange={(e) => setPurpose(e.target.value)} required />
      </label>
      <label>
        Item
        <select aria-label="Requirement item" value={item || ""} onChange={(e) => setItem(Number(e.target.value))} required>
          <option value="">{items.length ? "Select item" : "No items for this discipline"}</option>
          {items.map((row) => (
            <option key={row.id} value={row.id}>
              {row.code} · {row.description}
            </option>
          ))}
        </select>
        {!items.length && <small className="muted">Add the item in Master data with this discipline first.</small>}
      </label>
      <label>
        Quantity ({unit})
        <input aria-label="Required quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
      </label>
      <label>
        WBS
        <select aria-label="Requirement WBS" value={wbs} onChange={(e) => setWbs(e.target.value)}>
          <option value="">No WBS</option>
          {(context.wbs || []).map((row) => (
            <option key={row.id} value={row.id}>
              {row.code} · {row.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Work package
        <select aria-label="Requirement work package" value={workPackage} onChange={(e) => setWorkPackage(e.target.value)}>
          <option value="">No work package</option>
          {packages.map((row) => (
            <option key={row.id} value={row.id}>
              {row.code} · {row.name}
            </option>
          ))}
        </select>
        <small className="muted">Only draft work packages can be linked here.</small>
      </label>
      <label>
        Drawing
        <select aria-label="Linked drawing" value={drawing} onChange={(e) => { setDrawing(e.target.value); setRevision(""); }}>
          <option value="">No drawing</option>
          {context.drawings.map((row) => (
            <option key={row.id} value={row.id}>
              {row.number}
            </option>
          ))}
        </select>
      </label>
      <label>
        Revision
        <select aria-label="Linked revision" value={revision} onChange={(e) => setRevision(e.target.value)}>
          <option value="">No revision</option>
          {(chosen?.revisions || []).map((row) => (
            <option key={row.id} value={row.id}>
              {row.code}
            </option>
          ))}
        </select>
      </label>
      <button type="submit" className="tone-submit">Create requirement</button>
    </form>
  );
}

export function RequirementDetail({
  pid,
  row,
  context,
  onChange,
  onError,
}: {
  pid: number;
  row: Requirement;
  context: Context;
  onChange: (row: Requirement) => void;
  onError: (text: string) => void;
}) {
  const [reason, setReason] = useState("");
  async function run(path: string, body: unknown) {
    try {
      onChange(await api<Requirement>(`/projects/${pid}/procurement/requirements/${row.id}${path}`, "POST", body));
      onError("");
      setReason("");
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <h3 className="title-row">
        {row.number} <Pill value={row.status} /> <Pill value={row.priority} />
      </h3>
      <p>
        {row.discipline} · {row.company} · {row.source || "Manual"}
        {row.drawing_number ? ` · ${row.drawing_number} rev ${row.drawing_revision_code}` : ""}
        {row.takeoff_number ? ` · ${row.takeoff_number}` : ""}. Fulfillment <Pill value={row.fulfillment} />. Covered quantity counts stock allocated to this requirement and approved requisitions.
      </p>
      {!!row.work_packages?.length && (
        <p>Work package {row.work_packages.map((wp) => `${wp.code} · ${wp.name} (${wp.status})`).join(", ")}</p>
      )}
      {row.impact_state === "Review required" && (
        <p className="note-card note-alert">
          <AlertTriangle size={16} strokeWidth={2.4} /> Drawing impact: {row.impact_detail} Purchasing more of this requirement waits until the discipline reviewer records a decision. The quantity is unchanged.
        </p>
      )}
      {row.impact_state === "Reviewed" && (
        <p className="note-card note-good">Impact decision: {row.impact_decision}</p>
      )}
      {row.cancellation_reason && <p className="note-card note-bad">Cancelled: {row.cancellation_reason}</p>}
      <ul className="fact-row">
        {row.lines.map((line) => (
          <li key={line.id} className="fact">
            <strong>{line.item_code}</strong>
            <em>{line.quantity} {line.unit}</em>
            {line.wbs_code && <em>WBS {line.wbs_code} · {line.wbs_name}</em>}
            <div className="fact-row">
              <span className="fact hold"><strong>On requisitions</strong><em>{line.reserved_quantity}</em></span>
              <span className="fact good"><strong>Approved</strong><em>{line.approved_requisition_quantity}</em></span>
              <span className="fact warn"><strong>Outstanding</strong><em>{line.outstanding_quantity}</em></span>
              <span className="fact"><strong>Stock allocated</strong><em>{line.accepted_stock_quantity}</em></span>
            </div>
          </li>
        ))}
      </ul>
      {row.review && (
        <ReviewBox
          review={row.review}
          reason={reason}
          setReason={setReason}
          onError={onError}
          onDone={async () => onChange(await api<Requirement>(`/projects/${pid}/procurement/requirements/${row.id}`))}
        />
      )}
      <div className="inline">
        {row.status === "Draft" && context.access.requirement_edit && (
          <button type="button" className="tone-submit" onClick={() => void run("/submit", { version: row.version })}>
            Submit for review
          </button>
        )}
        {row.status === "Returned for Correction" && context.access.requirement_edit && row.review && (
          <button
            type="button"
            className="tone-submit"
            onClick={() => void run("/resubmit", { version: row.version, review_version: row.review!.version })}
          >
            Resubmit
          </button>
        )}
        {row.status === "Approved" && context.access.requirement_edit && (
          <button type="button" className="tone-return" onClick={() => void run("/amend", { reason: reason || "Amend quantities", version: row.version })}>
            Amend
          </button>
        )}
        {["Draft", "Returned for Correction", "Approved"].includes(row.status) && context.access.requirement_edit && (
          <button type="button" className="tone-withdraw" onClick={() => void run("/cancel", { reason: reason.trim() || "Cancelled", version: row.version })}>
            Cancel requirement
          </button>
        )}
        {row.impact_state === "Review required" && context.access.requirement_review && (
          <button
            type="button"
            className="tone-note"
            onClick={() => void run("/impact", { decision: reason, affected_quantity: row.lines[0]?.quantity || "0", version: row.version })}
          >
            Record impact decision
          </button>
        )}
      </div>
      {row.status === "Approved" && (
        <FulfilmentPanel
          key={`${row.id}-${row.version}`}
          pid={pid}
          requirementId={row.id}
          onError={onError}
          onChanged={() =>
            void api<Requirement>(`/projects/${pid}/procurement/requirements/${row.id}`)
              .then(onChange)
              .catch((err) => onError((err as Error).message))
          }
        />
      )}
    </section>
  );
}

function ReviewBox({
  review,
  reason,
  setReason,
  onError,
  onDone,
}: {
  review: Review;
  reason: string;
  setReason: (value: string) => void;
  onError: (text: string) => void;
  onDone: () => Promise<void>;
}) {
  return (
    <>
      <p>{review.subject}. Review {review.state}.</p>
      <ol className="review-chain">
        {(review.chain || []).map((step) => (
          <li key={step.name} className={`review-step ${step.status}`}>
            <strong>{step.name}</strong>
            <span>{step.reviewers.map((person) => person.name).join(", ")}</span>
            <em>{stepLabel(step.status)}</em>
          </li>
        ))}
      </ol>
      <ul className="decisions">
        {review.decisions.map((decision) => (
          <li key={decision.id} className={`decision decision-${decision.action}`}>
            {decision.reviewer_name ? `${decision.reviewer_name}: ` : ""}
            {decision.action === "approve" ? "Approve" : decision.action === "return" ? "Return" : decision.action === "reject" ? "Reject" : decision.action}
            {decision.reason ? `: ${decision.reason}` : ""}
          </li>
        ))}
      </ul>
      {review.actions.length === 0 && review.state === "In Review" && (
        <p className="note-card note-alert">
          Approve and Reject are with{" "}
          {(review.chain || []).find((step) => step.status === "current")?.reviewers.map((person) => person.name).join(", ") || "the saved reviewer"}.
          They appear only for that person.
        </p>
      )}
      {review.actions.length > 0 && (
        <>
          <input aria-label="Decision reason" placeholder="Reason, required for Return and Reject" value={reason} onChange={(e) => setReason(e.target.value)} />
          <div className="inline">
            {review.actions.filter((action) => action !== "comment" && action !== "resubmit").map((action) => (
              <button
                key={action}
                type="button"
                className={actionClass(action)}
                onClick={() => {
                  if ((action === "reject" || action === "return") && !reason.trim()) {
                    onError("Type the reason, then choose Return or Reject.");
                    return;
                  }
                  void api(`/reviews/${review.id}/decisions`, "POST", { action, reason, version: review.version })
                    .then(() => onDone())
                    .catch((err) => onError((err as Error).message));
                }}
              >
                {action === "approve" ? "Approve" : action === "return" ? "Return" : "Reject"}
              </button>
            ))}
          </div>
        </>
      )}
    </>
  );
}

function Requisitions({
  pid,
  context,
  rows,
  status,
  selected,
  requirements,
  onStatus,
  onOpen,
  onNeedRequirements,
  onChange,
  onError,
}: {
  pid: number;
  context: Context;
  rows: Requisition[];
  status: string;
  selected: Requisition | null;
  requirements: Requirement[];
  onStatus: (value: string) => void;
  onOpen: (id: number) => Promise<void>;
  onNeedRequirements: () => void;
  onChange: (row: Requisition) => void;
  onError: (text: string) => void;
}) {
  const [reason, setReason] = useState("");
  useEffect(() => {
    onNeedRequirements();
  }, []);
  const approved = requirements.filter((row) => row.status === "Approved");
  return (
    <>
      <label>
        Status
        <select aria-label="Requisition status" value={status} onChange={(e) => onStatus(e.target.value)}>
          <option value="">All statuses</option>
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
            <th>Status</th>
            <th>Ordering</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                <button type="button" onClick={() => void onOpen(row.id).catch((err) => onError((err as Error).message))}>
                  {row.number}
                </button>
              </td>
              <td><Pill value={row.status} /></td>
              <td><Pill value={row.ordering} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      {context.access.requisition_edit && (
        <RequisitionForm pid={pid} requirements={approved} commercial={context.access.commercial} onChange={onChange} onError={onError} />
      )}
      {selected && (
        <section className="panel">
          <h3 className="title-row">
            {selected.number} <Pill value={selected.status} /> <Pill value={selected.ordering} />
          </h3>
          <p className="note-card">{selected.ordering_note}</p>
          <ul>
            {selected.lines.map((line) => (
              <li key={line.id}>
                {line.item_code} {line.quantity} {line.unit}
                {line.requirement_number ? ` · from requirement ${line.requirement_number}` : ""}
                {line.wbs_code ? ` · WBS ${line.wbs_code} ${line.wbs_name}` : ""}
                {context.access.commercial && line.estimated_price ? ` · ${selected.currency} ${line.estimated_price}` : ""}
              </li>
            ))}
          </ul>
          {selected.review && (
            <ReviewBox
              review={selected.review}
              reason={reason}
              setReason={setReason}
              onError={onError}
              onDone={async () => onChange(await api<Requisition>(`/projects/${pid}/procurement/requisitions/${selected.id}`))}
            />
          )}
          {selected.status === "Draft" && context.access.requisition_edit && (
            <button
              type="button"
              className="tone-submit"
              onClick={() =>
                void api<Requisition>(`/projects/${pid}/procurement/requisitions/${selected.id}/submit`, "POST", {
                  version: selected.version,
                })
                  .then(onChange)
                  .catch((err) => onError((err as Error).message))
              }
            >
              Submit for review
            </button>
          )}
        </section>
      )}
    </>
  );
}

function RequisitionForm({
  pid,
  requirements,
  commercial,
  onChange,
  onError,
}: {
  pid: number;
  requirements: Requirement[];
  commercial: boolean;
  onChange: (row: Requisition) => void;
  onError: (text: string) => void;
}) {
  const [number, setNumber] = useState("");
  const [requestDate, setRequestDate] = useState("");
  const [delivery, setDelivery] = useState("");
  const [justification, setJustification] = useState("");
  const [lineId, setLineId] = useState(0);
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState("");
  const lines = requirements.flatMap((row) => row.lines.map((line) => ({ ...line, requirement: row.number })));
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const row = await api<Requisition>(`/projects/${pid}/procurement/requisitions`, "POST", {
        number,
        request_date: requestDate,
        required_delivery: delivery,
        justification,
        currency: price ? currency : "",
        lines: [
          {
            requirement_line_id: lineId,
            quantity,
            estimated_price: price || null,
          },
        ],
      });
      onError("");
      onChange(row);
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <form className="option-grid" onSubmit={(event) => void submit(event)}>
      <h3>New requisition</h3>
      <p>Quantity cannot exceed the remaining approved requirement. Estimated prices are stored only for people with commercial access.</p>
      <label>
        Number
        <input aria-label="Requisition number" value={number} onChange={(e) => setNumber(e.target.value)} required />
      </label>
      <label>
        Request date
        <input aria-label="Request date" type="date" value={requestDate} onChange={(e) => setRequestDate(e.target.value)} required />
      </label>
      <label>
        Required delivery
        <input aria-label="Required delivery" type="date" value={delivery} onChange={(e) => setDelivery(e.target.value)} required />
      </label>
      <label>
        Justification
        <input aria-label="Justification" value={justification} onChange={(e) => setJustification(e.target.value)} required />
      </label>
      <label>
        Approved line
        <select aria-label="Approved requirement line" value={lineId} onChange={(e) => setLineId(Number(e.target.value))}>
          <option value={0}>Select line</option>
          {lines.map((line) => (
            <option key={line.id} value={line.id}>
              {line.requirement} · {line.item_code}{line.wbs_code ? ` · WBS ${line.wbs_code}` : ""} remaining {line.remaining_for_requisition} {line.unit}
            </option>
          ))}
        </select>
      </label>
      <label>
        Quantity
        <input aria-label="Requisition quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
      </label>
      {commercial && (
        <>
          <label>
            Estimated price
            <input aria-label="Estimated price" value={price} onChange={(e) => setPrice(e.target.value)} />
          </label>
          <label>
            Currency
            <input aria-label="Currency" value={currency} onChange={(e) => setCurrency(e.target.value)} />
          </label>
        </>
      )}
      <button type="submit" className="tone-submit">Create requisition</button>
    </form>
  );
}

function Masters({
  pid,
  catalog,
  context,
  onSaved,
  onError,
}: {
  pid: number;
  session: Session;
  catalog: Catalog;
  context: Context;
  onSaved: () => void;
  onError: (text: string) => void;
}) {
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [itemType, setItemType] = useState("Material");
  const [category, setCategory] = useState("");
  const [discipline, setDiscipline] = useState(catalog.disciplines[0]?.id || 0);
  const [unit, setUnit] = useState("");
  const [inspection, setInspection] = useState(false);
  const [fromUnit, setFromUnit] = useState("");
  const [toUnit, setToUnit] = useState("");
  const [factor, setFactor] = useState("");
  const [vendorCode, setVendorCode] = useState("");
  const [vendorCompany, setVendorCompany] = useState(context.companies[0]?.id || 0);
  const [vendorRows, setVendorRows] = useState<
    { id: number; code: string; company: string; company_id: number; approval_status: string; active: boolean; version: number }[]
  >([]);
  async function loadVendors() {
    setVendorRows(await api("/procurement/vendors"));
  }
  useEffect(() => {
    void loadVendors().catch((err) => onError((err as Error).message));
  }, []);
  async function setVendorStatus(
    row: { id: number; code: string; company_id: number; active: boolean; version: number },
    approval_status: string,
  ) {
    try {
      await api(`/procurement/vendors/${row.id}`, "PUT", {
        code: row.code,
        company_id: row.company_id,
        approval_status,
        active: row.active,
        version: row.version,
      });
      onError("");
      await loadVendors();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  const [warehouseCode, setWarehouseCode] = useState("");
  const [warehouseName, setWarehouseName] = useState("");
  const [officer, setOfficer] = useState(context.people[0]?.id || 0);
  type SpecificationField = { key: string; label: string; type: "text" | "number" | "boolean" | "select"; required: boolean; options: string[] };
  type SpecificationGroup = { discipline: string; categories: Array<{ name: string; fields: SpecificationField[] }> };
  const [specTemplates, setSpecTemplates] = useState<SpecificationGroup[]>([]);
  const [templateCategory, setTemplateCategory] = useState("");
  const [editableFields, setEditableFields] = useState<SpecificationField[]>([]);
  const [templateSaving, setTemplateSaving] = useState(false);
  const [specAttributes, setSpecAttributes] = useState<Record<string, string>>({});
  const disciplineName = catalog.disciplines.find((row) => row.id === discipline)?.name || "";
  const specCategories = specTemplates.find((x) => x.discipline === disciplineName)?.categories || [];
  const specFields = specCategories.find((x) => x.name === category)?.fields || [];
  async function reloadTemplates(): Promise<SpecificationGroup[]> {
    const rows = await api<SpecificationGroup[]>(
      "/procurement/items/specification-templates"
    );

    setSpecTemplates(rows);
    return rows;
  }
  useEffect(() => { void reloadTemplates().catch(() => { }); }, []);
  function loadTemplate(categoryName: string) {
    setTemplateCategory(categoryName);
    const matching = specCategories.find((x) => x.name === categoryName);
    setEditableFields(matching?.fields.map((field) => ({ ...field, options: [...(field.options || [])] })) || []);
  }
  async function saveTemplate(event: FormEvent) {
    event.preventDefault();
    if (!context.access.admin || !templateCategory.trim()) return;
    setTemplateSaving(true);
    try {
      await api(`/procurement/items/specification-templates/${encodeURIComponent(disciplineName)}/${encodeURIComponent(templateCategory.trim())}`, "PUT", { fields: editableFields });
      await reloadTemplates();
      onError("");
      onSaved();
    } catch (err) {
      onError((err as Error).message);
    } finally { setTemplateSaving(false); }
  }
  type CatalogueReviewItem = { id: number; code: string; description: string; approval_status: string; active: boolean; version: number };
  type CatalogueReviewEvent = { action: string; reason: string; actor_id: number; item_version: number; created_at: string };
  const [catalogueReviewItems, setCatalogueReviewItems] = useState<CatalogueReviewItem[]>([]);
  const [reviewItemId, setReviewItemId] = useState<number>(0);
  const [reviewHistory, setReviewHistory] = useState<CatalogueReviewEvent[]>([]);
  type CatalogueSpecHistory = {
    sequence: number;
    item_version: number;
    event: string;
    reason: string;
    actor_id: number;
    created_at: string | null;
    snapshot: Record<string, unknown>;
  };
  const [specHistory, setSpecHistory] = useState<CatalogueSpecHistory[]>([]);
  const [specHistoryBusy, setSpecHistoryBusy] = useState(false);
  const [specHistoryError, setSpecHistoryError] = useState("");
  const [showSpecHistory, setShowSpecHistory] = useState(false);
  const [expandedSpecSnapshot, setExpandedSpecSnapshot] = useState<number | null>(null);
  async function loadCatalogueSpecHistory(itemId: number) {
    if (!itemId) { setSpecHistory([]); return; }
    setSpecHistoryBusy(true);
    setSpecHistoryError("");
    try {
      const history = await api<CatalogueSpecHistory[]>(`/procurement/items/${itemId}/specification-history`);
      setSpecHistory(history);
    } catch (error) {
      setSpecHistoryError((error as Error).message);
      setSpecHistory([]);
    } finally { setSpecHistoryBusy(false); }
  }
  useEffect(() => {
    // Prevent showing an old item's snapshots when the catalogue selection changes.
    setSpecHistory([]);
    setShowSpecHistory(false);
    setExpandedSpecSnapshot(null);
    setSpecHistoryError("");
  }, [reviewItemId]);

  type CatalogueAmendment = { id: number; status: string; base_version: number; changes: Record<string, unknown>; reason: string; submitted_by: number; decided_by: number | null; decision_reason: string | null };
  const [amendments, setAmendments] = useState<CatalogueAmendment[]>([]);
  const [amendmentBusy, setAmendmentBusy] = useState(false);
  const [amendmentMessage, setAmendmentMessage] = useState("");
  const [amendmentReason, setAmendmentReason] = useState("");
  const [amendmentField, setAmendmentField] = useState("specification");
  const [amendmentValue, setAmendmentValue] = useState("");
  const [amendmentDecisionReason, setAmendmentDecisionReason] = useState("");
  async function loadAmendments(itemId: number) {
    if (!itemId) { setAmendments([]); return; }
    setAmendments(await api<CatalogueAmendment[]>(`/procurement/items/${itemId}/amendments`));
  }
  useEffect(() => {
    setAmendments([]);
    setAmendmentMessage("");
    setAmendmentReason("");
    setAmendmentValue("");
    setAmendmentDecisionReason("");
    if (!reviewItemId) return;
    let active = true;
    void api<CatalogueAmendment[]>(`/procurement/items/${reviewItemId}/amendments`)
      .then((rows) => { if (active) setAmendments(rows); })
      .catch((error) => { if (active) setAmendmentMessage((error as Error).message); });
    return () => { active = false; };
  }, [reviewItemId]);
  const pendingAmendment = amendments.find((row) => row.status === "Pending Approval");
  async function requestAmendment() {
    if (!selectedReviewItem || amendmentBusy || selectedReviewItem.approval_status !== "Approved") return;
    if (!amendmentReason.trim() || !amendmentValue.trim()) { setAmendmentMessage("Enter a change and amendment reason."); return; }
    let proposedValue: unknown = amendmentValue.trim();
    if (amendmentField === "specification_attributes") {
      try {
        proposedValue = JSON.parse(amendmentValue);
        if (typeof proposedValue !== "object" || proposedValue === null || Array.isArray(proposedValue)) throw Error();
      } catch { setAmendmentMessage("Specifications must be a valid JSON object."); return; }
    } else if (amendmentField === "inspection_required" || amendmentField === "tracking_required") {
      if (!["true", "false"].includes(amendmentValue.trim().toLowerCase())) { setAmendmentMessage("Use true or false."); return; }
      proposedValue = amendmentValue.trim().toLowerCase() === "true";
    }
    setAmendmentBusy(true); setAmendmentMessage("");
    try {
      await api(`/procurement/items/${selectedReviewItem.id}/amendments`, "POST", { changes: { [amendmentField]: proposedValue }, reason: amendmentReason.trim() });
      await loadAmendments(selectedReviewItem.id);
      setAmendmentValue(""); setAmendmentReason(""); setAmendmentMessage("Amendment submitted for review. The approved item remains unchanged.");
    } catch (error) { setAmendmentMessage((error as Error).message); }
    finally { setAmendmentBusy(false); }
  }
  async function decideAmendment(amendmentId: number, action: "Approve" | "Reject") {
    if (!selectedReviewItem || !catalogueApprovalAllowed || amendmentBusy || amendmentDecisionReason.trim().length < 3) return;
    setAmendmentBusy(true); setAmendmentMessage("");
    try {
      await api(`/procurement/items/${selectedReviewItem.id}/amendments/${amendmentId}/decision`, "POST", { action, reason: amendmentDecisionReason.trim() });
      await Promise.all([loadAmendments(selectedReviewItem.id), refreshCatalogueReviewItems(), loadCatalogueSpecHistory(selectedReviewItem.id)]);
      setAmendmentDecisionReason(""); setAmendmentMessage(`Amendment ${action.toLowerCase()} recorded.`);
      onSaved();
    } catch (error) { setAmendmentMessage((error as Error).message); }
    finally { setAmendmentBusy(false); }
  }
  const [decisionReason, setDecisionReason] = useState("");
  const [reviewBusy, setReviewBusy] = useState(false);
  const [reviewMessage, setReviewMessage] = useState("");
  const [catalogueApprovalAllowed, setCatalogueApprovalAllowed] = useState(false);
  const selectedReviewItem = catalogueReviewItems.find((item) => item.id === reviewItemId);
  async function refreshCatalogueReviewItems() {
    const rows = await api<CatalogueReviewItem[]>("/procurement/items");
    setCatalogueReviewItems(rows);
    setReviewItemId((current) => current && rows.some((item) => item.id === current) ? current : (rows[0]?.id || 0));
  }
  useEffect(() => {
    let active = true;
    void api<{ can_approve: boolean }>("/procurement/items/approval-capability")
      .then((result) => { if (active) setCatalogueApprovalAllowed(result.can_approve); })
      .catch(() => { if (active) setCatalogueApprovalAllowed(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    void refreshCatalogueReviewItems().catch((error) => onError((error as Error).message));
  }, []);
  useEffect(() => {
    if (!reviewItemId) { setReviewHistory([]); return; }
    let active = true;
    void api<CatalogueReviewEvent[]>(`/procurement/items/${reviewItemId}/review-history`)
      .then((rows) => { if (active) setReviewHistory(rows); })
      .catch((error) => { if (active) onError((error as Error).message); });
    return () => { active = false; };
  }, [reviewItemId]);
  async function catalogueReviewAction(action: "Submit" | "Approve" | "Reject") {
    if (!selectedReviewItem || reviewBusy) return;
    if (action !== "Submit" && decisionReason.trim().length < 3) {
      setReviewMessage("Enter a reason containing at least 3 characters.");
      return;
    }
    setReviewBusy(true);
    setReviewMessage("");
    try {
      const endpoint = action === "Submit" ? "submit" : "decision";
      await api(`/procurement/items/${selectedReviewItem.id}/${endpoint}`, "POST",
        action === "Submit" ? {} : { action, reason: decisionReason.trim() });
      await refreshCatalogueReviewItems();
      setReviewHistory(await api<CatalogueReviewEvent[]>(`/procurement/items/${selectedReviewItem.id}/review-history`));
      setDecisionReason("");
      setReviewMessage(`${action} recorded successfully.`);
      onError("");
      onSaved();
    } catch (error) {
      setReviewMessage((error as Error).message);
    } finally {
      setReviewBusy(false);
    }
  }
  const canMaster = context.access.master || context.access.admin;
  async function createItem(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/procurement/items", "POST", {
        code,
        description,
        item_type: itemType,
        category,
        discipline_ids: [discipline],
        base_unit: unit,
        specification_discipline: disciplineName,
        specification_attributes: Object.fromEntries(specFields.filter((field) => {
          const value = specAttributes[field.key];
          return value !== undefined && (field.type === "boolean" || String(value).trim() !== "");
        }).map((field) => [field.key, field.type === "boolean" ? specAttributes[field.key] === "true" : field.type === "number" ? Number(specAttributes[field.key]) : specAttributes[field.key]])),
        inspection_required: inspection,
      });
      onError("");
      onSaved();
      setCode("");
      setDescription("");
      await refreshCatalogueReviewItems();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  if (!canMaster) {
    return (
      <section className="panel">
        <h3>Master data</h3>
        <p>Item, vendor, and warehouse setup is limited to a procurement manager or the organization administrator.</p>
        <ul>
          {context.items.map((item) => (
            <li key={item.id}>
              {item.code} · {item.description} · {item.base_unit}
            </li>
          ))}
        </ul>
      </section>
    );
  }
  return (
    <>
      <form className="option-grid" onSubmit={(event) => void createItem(event)}>
        <h3 className="section-mark"><Package size={18} strokeWidth={2.4} /> Item</h3>
        <label>
          Code
          <input aria-label="Item code" value={code} onChange={(e) => setCode(e.target.value)} required />
        </label>
        <label>
          Description
          <input aria-label="Item description" value={description} onChange={(e) => setDescription(e.target.value)} required />
        </label>
        <label>
          Type
          <select aria-label="Item type" value={itemType} onChange={(e) => setItemType(e.target.value)}>
            <option>Material</option>
            <option>Equipment</option>
            <option>Consumable</option>
            <option>Spare</option>
          </select>
        </label>
        <label>
          Category
          <input aria-label="Item category" list="item-category-options" value={category} onChange={(e) => { setCategory(e.target.value); setSpecAttributes({}); }} required />
          <datalist id="item-category-options">{specCategories.map((c) => <option key={c.name} value={c.name} />)}</datalist>
        </label>
        <label>
          Discipline
          <select aria-label="Item discipline" value={discipline} onChange={(e) => setDiscipline(Number(e.target.value))}>
            {catalog.disciplines.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          UOM (base unit)
          <input aria-label="Base unit" value={unit} onChange={(e) => setUnit(e.target.value)} required />
        </label>
        <label>
          <input type="checkbox" checked={inspection} onChange={(e) => setInspection(e.target.checked)} /> Inspection required
        </label>
        {specFields.length > 0 && <fieldset><legend>Technical specifications — {category}</legend>
          {specFields.map((field) => <label key={field.key}>{field.label}{field.required ? " *" : ""}
            {field.type === "select" ? <select aria-label={field.label} required={field.required} value={specAttributes[field.key] || ""} onChange={(e) => setSpecAttributes((old) => ({ ...old, [field.key]: e.target.value }))}><option value="">Select an option</option>{(field.options || []).map((choice) => <option key={choice} value={choice}>{choice}</option>)}</select>
              : field.type === "boolean" ? <select aria-label={field.label} required={field.required} value={specAttributes[field.key] || ""} onChange={(e) => setSpecAttributes((old) => ({ ...old, [field.key]: e.target.value }))}><option value="">Select</option><option value="true">Yes</option><option value="false">No</option></select>
                : <input type={field.type === "number" ? "number" : "text"} step={field.type === "number" ? "any" : undefined} required={field.required} aria-label={field.label} value={specAttributes[field.key] || ""} onChange={(e) => setSpecAttributes((old) => ({ ...old, [field.key]: e.target.value }))} />}
          </label>)}
        </fieldset>}
        <button type="submit" className="tone-submit">Save item</button>
      </form>
      <section className="option-grid" aria-label="Catalogue item approval">
        <h3 className="section-mark">Catalogue Item Review</h3>
        <p>Draft items must be submitted before use. Only authorized reviewers can approve or reject. Decisions are enforced by the backend and cannot be made by the creator or submitter.</p>
        <label>Catalogue item
          <select aria-label="Review catalogue item" value={reviewItemId} onChange={(event) => { setReviewItemId(Number(event.target.value)); setReviewMessage(""); setDecisionReason(""); }}>
            {catalogueReviewItems.length === 0 && <option value={0}>No catalogue items</option>}
            {catalogueReviewItems.map((item) => <option key={item.id} value={item.id}>{item.code} — {item.description} ({item.approval_status})</option>)}
          </select>
        </label>
        {selectedReviewItem && <>
          <p><strong>Approval status:</strong> {selectedReviewItem.approval_status} · <strong>Active:</strong> {selectedReviewItem.active ? "Yes" : "No"} · <strong>Version:</strong> {selectedReviewItem.version}</p>
          {(["Draft", "Rejected"].includes(selectedReviewItem.approval_status)) &&
            <button type="button" disabled={reviewBusy} onClick={() => void catalogueReviewAction("Submit")}>Submit item for approval</button>}
          {selectedReviewItem.approval_status === "Pending Approval" && catalogueApprovalAllowed && <>
            <label>Decision reason (required)
              <textarea aria-label="Catalogue decision reason" required minLength={3} maxLength={2000} value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} />
            </label>
            <button type="button" disabled={reviewBusy || decisionReason.trim().length < 3} onClick={() => void catalogueReviewAction("Approve")}>Approve item</button>
            <button type="button" disabled={reviewBusy || decisionReason.trim().length < 3} onClick={() => void catalogueReviewAction("Reject")}>Reject item</button>
          </>}
        </>}
        {reviewMessage && <p role="status">{reviewMessage}</p>}
        <button type="button" disabled={reviewBusy} onClick={() => void refreshCatalogueReviewItems().catch((error) => onError((error as Error).message))}>Refresh catalogue review</button>
        <h4>Review history</h4>
        {reviewHistory.length === 0 ? <p>No review decisions recorded.</p> : <table><thead><tr><th>When</th><th>Action</th><th>Reviewer ID</th><th>Reason</th><th>Version</th></tr></thead><tbody>
          {reviewHistory.map((event, index) => <tr key={`${event.created_at}-${index}`}><td>{new Date(event.created_at).toLocaleString()}</td><td>{event.action}</td><td>{event.actor_id}</td><td>{event.reason}</td><td>{event.item_version}</td></tr>)}
        </tbody></table>}
        <h4>Controlled catalogue amendments</h4>
        <p>Approved items remain unchanged while amendments are pending. Item code, UOM and category cannot be amended here.</p>
        {selectedReviewItem?.approval_status === "Approved" && !pendingAmendment && <fieldset disabled={amendmentBusy}>
          <legend>Request technical change</legend>
          <label>Field to change
            <select aria-label="Amendment field" value={amendmentField} onChange={(event) => { setAmendmentField(event.target.value); setAmendmentValue(""); }}>
              <option value="specification">Specification description</option>
              <option value="specification_attributes">Structured specifications (JSON)</option>
              <option value="size_rating">Size / rating</option>
              <option value="approved_make">Approved make</option>
              <option value="inspection_required">Inspection required (true/false)</option>
              <option value="tracking_required">Tracking required (true/false)</option>
            </select>
          </label>
          <label>Proposed value
            <textarea aria-label="Proposed amendment value" value={amendmentValue} onChange={(event) => setAmendmentValue(event.target.value)} maxLength={amendmentField === "specification_attributes" ? undefined : 2000} placeholder={amendmentField === "specification_attributes" ? '{"flow_capacity":60}' : "Enter proposed value"} />
          </label>
          <label>Reason for amendment (required)
            <textarea aria-label="Amendment request reason" value={amendmentReason} onChange={(event) => setAmendmentReason(event.target.value)} maxLength={2000} />
          </label>
          <button type="button" disabled={!amendmentReason.trim() || !amendmentValue.trim()} onClick={() => void requestAmendment()}>Submit amendment request</button>
        </fieldset>}
        {pendingAmendment && <p role="status">Amendment #{pendingAmendment.id} is pending approval. The active item remains unchanged.</p>}
        {pendingAmendment && catalogueApprovalAllowed && <fieldset disabled={amendmentBusy}>
          <legend>Decide pending amendment #{pendingAmendment.id}</legend>
          <label>Decision reason (required)
            <textarea aria-label="Amendment decision reason" minLength={3} maxLength={2000} value={amendmentDecisionReason} onChange={(event) => setAmendmentDecisionReason(event.target.value)} />
          </label>
          <button type="button" disabled={amendmentDecisionReason.trim().length < 3} onClick={() => void decideAmendment(pendingAmendment.id, "Approve")}>Approve amendment</button>
          <button type="button" disabled={amendmentDecisionReason.trim().length < 3} onClick={() => void decideAmendment(pendingAmendment.id, "Reject")}>Reject amendment</button>
          <p>Approvers cannot approve amendments they created or submitted. The server enforces this restriction.</p>
        </fieldset>}
        {amendmentMessage && <p role="status">{amendmentMessage}</p>}
        <button type="button" disabled={!reviewItemId || amendmentBusy} onClick={() => void loadAmendments(reviewItemId).catch((error) => setAmendmentMessage((error as Error).message))}>Refresh amendments</button>
        {amendments.length === 0 ? <p>No amendment requests for this item.</p> : <table><thead><tr><th>ID</th><th>Status</th><th>Base version</th><th>Proposed changes</th><th>Request reason</th><th>Submitted by</th><th>Decision</th></tr></thead><tbody>
          {amendments.map((row) => <tr key={row.id}><td>{row.id}</td><td>{row.status}</td><td>{row.base_version}</td><td><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxWidth: "300px" }}>{JSON.stringify(row.changes, null, 2)}</pre></td><td>{row.reason}</td><td>{row.submitted_by}</td><td>{row.decided_by == null ? "Pending" : `${row.decided_by}: ${row.decision_reason || "—"}`}</td></tr>)}
        </tbody></table>}
        <h4>Technical specification history</h4>
        <p>Read-only item snapshots. Prior approved specifications remain visible; modifying an approved item requires a separately authorized amendment workflow.</p>
        <button type="button" disabled={!reviewItemId || specHistoryBusy} onClick={() => {
          if (!showSpecHistory) {
            setShowSpecHistory(true);
            void loadCatalogueSpecHistory(reviewItemId);
          } else { setShowSpecHistory(false); }
        }}>{showSpecHistory ? "Hide specification history" : "View specification history"}</button>
        {showSpecHistory && <>
          <button type="button" disabled={specHistoryBusy} onClick={() => void loadCatalogueSpecHistory(reviewItemId)}>Refresh specification history</button>
          {specHistoryBusy && <p role="status">Loading specification history...</p>}
          {specHistoryError && <p role="alert">Unable to load specification history: {specHistoryError}</p>}
          {!specHistoryBusy && !specHistoryError && specHistory.length === 0 && <p>No specification history recorded for this item.</p>}
          {specHistory.length > 0 && <table><thead><tr><th>Sequence</th><th>When</th><th>Event</th><th>Item version</th><th>Actor ID</th><th>Reason</th><th>Snapshot</th></tr></thead><tbody>
            {specHistory.map((entry) => <tr key={entry.sequence}>
              <td>{entry.sequence}</td><td>{entry.created_at ? new Date(entry.created_at).toLocaleString() : "—"}</td>
              <td>{entry.event}</td><td>{entry.item_version}</td><td>{entry.actor_id}</td><td>{entry.reason || "—"}</td>
              <td><button type="button" aria-label={`Toggle specification snapshot ${entry.sequence}`} onClick={() => setExpandedSpecSnapshot((old) => old === entry.sequence ? null : entry.sequence)}>{expandedSpecSnapshot === entry.sequence ? "Hide" : "View"}</button>
                {expandedSpecSnapshot === entry.sequence && <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxWidth: "460px" }}>{JSON.stringify(entry.snapshot, null, 2)}</pre>}</td>
            </tr>)}
          </tbody></table>}
        </>}
      </section>
      {context.access.admin && <form className="option-grid" onSubmit={(event) => void saveTemplate(event)}>
        <h3 className="section-mark">Specification Template Master (Organization Admin)</h3>
        <p>Configure specification fields for your organization. Existing built-in templates remain as fallbacks. Changes to a live template can affect future item validation; review carefully before saving.</p>
        <label>Discipline
          <select aria-label="Template discipline" value={discipline} onChange={(e) => { setDiscipline(Number(e.target.value)); setTemplateCategory(""); setEditableFields([]); }}>
            {catalog.disciplines.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label>Category
          <input aria-label="Template category" list="spec-template-category-options" value={templateCategory} onChange={(e) => loadTemplate(e.target.value)} required maxLength={120} />
          <datalist id="spec-template-category-options">{specCategories.map((c) => <option key={c.name} value={c.name} />)}</datalist>
        </label>
        {editableFields.map((field, index) => <fieldset key={`${index}-${field.key}`}>
          <legend>Field {index + 1}</legend>
          <label>Key <input aria-label={`Specification field ${index + 1} key`} pattern="[a-z][a-z0-9_]*" required value={field.key} onChange={(e) => setEditableFields((old) => old.map((f, i) => i === index ? { ...f, key: e.target.value } : f))} /></label>
          <label>Label <input aria-label={`Specification field ${index + 1} label`} required value={field.label} onChange={(e) => setEditableFields((old) => old.map((f, i) => i === index ? { ...f, label: e.target.value } : f))} /></label>
          <label>Type <select aria-label={`Specification field ${index + 1} type`} value={field.type} onChange={(e) => setEditableFields((old) => old.map((f, i) => i === index ? { ...f, type: e.target.value as SpecificationField["type"], options: e.target.value === "select" ? f.options : [] } : f))}>{["text", "number", "boolean", "select"].map((t) => <option key={t}>{t}</option>)}</select></label>
          <label><input type="checkbox" checked={field.required} onChange={(e) => setEditableFields((old) => old.map((f, i) => i === index ? { ...f, required: e.target.checked } : f))} /> Required</label>
          {field.type === "select" && <label>Options (one per line)<textarea aria-label={`Specification field ${index + 1} options`} value={field.options.join("\n")} onChange={(e) => setEditableFields((old) => old.map((f, i) => i === index ? { ...f, options: e.target.value.split("\n").map((v) => v.trim()).filter(Boolean) } : f))} /></label>}
          <button type="button" onClick={() => setEditableFields((old) => old.filter((_, i) => i !== index))}>Remove field</button>
        </fieldset>)}
        <button type="button" onClick={() => setEditableFields((old) => [...old, { key: "", label: "", type: "text", required: false, options: [] }])}>Add specification field</button>
        <button type="submit" className="tone-submit" disabled={templateSaving || !templateCategory.trim() || editableFields.length === 0}>{templateSaving ? "Saving..." : "Save organization template"}</button>
      </form>}
      <form
        className="option-grid"
        onSubmit={(event) => {
          event.preventDefault();
          void api("/procurement/conversions", "POST", { from_unit: fromUnit, to_unit: toUnit, factor })
            .then(() => {
              onError("");
              onSaved();
            })
            .catch((err) => onError((err as Error).message));
        }}
      >
        <h3 className="section-mark"><ArrowLeftRight size={18} strokeWidth={2.4} /> Unit conversion</h3>
        <p>Use this when a purchase unit differs from the stock unit. Quantities on one requirement line stay in one unit.</p>
        <label>
          From
          <input aria-label="From unit" value={fromUnit} onChange={(e) => setFromUnit(e.target.value)} required />
        </label>
        <label>
          To
          <input aria-label="To unit" value={toUnit} onChange={(e) => setToUnit(e.target.value)} required />
        </label>
        <label>
          Factor
          <input aria-label="Conversion factor" value={factor} onChange={(e) => setFactor(e.target.value)} required />
        </label>
        <button type="submit" className="tone-submit">Save conversion</button>
      </form>
      <form
        className="option-grid"
        onSubmit={(event) => {
          event.preventDefault();
          void api("/procurement/vendors", "POST", { code: vendorCode, company_id: vendorCompany, approval_status: "Pending" })
            .then(() => {
              setVendorCode("");
              onError("");
              return loadVendors();
            })
            .catch((err) => onError((err as Error).message));
        }}
      >
        <h3 className="section-mark"><Building2 size={18} strokeWidth={2.4} /> Vendor</h3>
        <p>Tax details stay hidden from people without commercial access. Vendor approval starts at Pending.</p>
        <label>
          Code
          <input aria-label="Vendor code" value={vendorCode} onChange={(e) => setVendorCode(e.target.value)} required />
        </label>
        <label>
          Company
          <select aria-label="Vendor company" value={vendorCompany} onChange={(e) => setVendorCompany(Number(e.target.value))}>
            {context.companies.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="tone-submit">Save vendor</button>
        {vendorRows.map((row) => (
          <article key={row.id} className="note-card">
            <strong>{row.code}</strong> · {row.company} <Pill value={row.approval_status} />
            <div className="inline">
              {row.approval_status !== "Approved" && (
                <button type="button" className="tone-approve" onClick={() => void setVendorStatus(row, "Approved")}>
                  Approve vendor
                </button>
              )}
              {row.approval_status !== "Suspended" && (
                <button type="button" className="tone-reject" onClick={() => void setVendorStatus(row, "Suspended")}>
                  Suspend vendor
                </button>
              )}
            </div>
          </article>
        ))}
      </form>
      <form
        className="option-grid"
        onSubmit={(event) => {
          event.preventDefault();
          void api(`/projects/${pid}/procurement/warehouses`, "POST", {
            code: warehouseCode,
            name: warehouseName,
            officer_id: officer,
          })
            .then(() => onSaved())
            .catch((err) => onError((err as Error).message));
        }}
      >
        <h3 className="section-mark"><Warehouse size={18} strokeWidth={2.4} /> Warehouse</h3>
        <label>
          Code
          <input aria-label="Warehouse code" value={warehouseCode} onChange={(e) => setWarehouseCode(e.target.value)} required />
        </label>
        <label>
          Name
          <input aria-label="Warehouse name" value={warehouseName} onChange={(e) => setWarehouseName(e.target.value)} required />
        </label>
        <label>
          Stores officer
          <select aria-label="Stores officer" value={officer} onChange={(e) => setOfficer(Number(e.target.value))}>
            {context.people.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="tone-submit">Save warehouse</button>
      </form>
      <ItemImport onError={onError} onSaved={onSaved} />
    </>
  );
}

function ItemImport({ onError, onSaved }: { onError: (text: string) => void; onSaved: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  async function send(mode: string) {
    if (!file) return;
    const body = new FormData();
    body.set("upload", file);
    try {
      const result = await postForm<{ errors: { row: number; messages: string[] }[]; saved: number }>(
        `/procurement/items/import?mode=${mode}`,
        body,
      );
      if (result.errors.length) {
        setPreview(result.errors.map((row) => `Row ${row.row}: ${row.messages.join(", ")}`).join(" "));
        return;
      }
      setPreview(mode === "preview" ? `${result.saved === 0 ? "Preview found no errors." : ""}` : `Saved ${result.saved}.`);
      if (mode !== "preview") onSaved();
      onError("");
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <h3 className="section-mark"><FileSpreadsheet size={18} strokeWidth={2.4} /> Import items</h3>
      <p>Preview checks the workbook before anything is saved. An existing item code is rejected unless you choose update. Import does not approve a requirement or post stock.</p>
      <input
        aria-label="Item import file"
        type="file"
        accept=".xlsx"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
      />
      <div className="inline">
        <button type="button" className="tone-note" onClick={() => void send("preview")}>
          Preview
        </button>
        <button type="button" className="tone-approve" onClick={() => void send("confirm")}>
          Confirm new items
        </button>
      </div>
      {preview ? <p>{preview}</p> : null}
    </section>
  );
}

type RfqSource = {
  id: number;
  number: string;
  discipline: string;
  lines: { id: number; item_code: string; remaining: string; unit: string }[];
};
type RfqQuote = {
  id: number;
  vendor_id: number;
  vendor: string;
  company: string;
  reference: string;
  currency: string;
  technical_deviations: string;
  technical_decision: string;
  technical_reason: string;
  technical_by_name: string;
  commercial_note: string;
  original_total: string | null;
  compared_total: string | null;
  lowest_quoted: boolean;
  lines: { id: number; rfq_line_id: number; item_code: string; quantity: string; unit_price: string | null }[];
};
type RfqRow = {
  id: number;
  number: string;
  requisition_number: string;
  discipline: string;
  status: string;
  due_date: string;
  version: number;
  prices_visible: boolean;
  hint: string;
  technical_reviewers: { id: number; name: string }[];
  steps: { name: string; status: string }[];
  lines: { id: number; item_code: string; quantity: string; unit: string }[];
  vendors: { vendor_id: number; code: string; company: string }[];
  quotations: RfqQuote[];
  awards: { vendor: string; quantity: string }[];
  award_reason: string;
  ordering_note: string;
  can_issue: boolean;
  can_quote: boolean;
  can_start_technical: boolean;
  can_technical: boolean;
  can_commercial: boolean;
  can_award: boolean;
  can_cancel: boolean;
};

function Rfqs({
  pid,
  context,
  status,
  onStatus,
  onError,
}: {
  pid: number;
  context: Context;
  status: string;
  onStatus: (value: string) => void;
  onError: (text: string) => void;
}) {
  const [rows, setRows] = useState<RfqRow[]>([]);
  const [selected, setSelected] = useState<RfqRow | null>(null);
  const [sources, setSources] = useState<RfqSource[]>([]);
  const [vendors, setVendors] = useState<{ id: number; code: string; company: string; approval_status: string }[]>([]);
  const [number, setNumber] = useState("");
  const [requisitionId, setRequisitionId] = useState(0);
  const [due, setDue] = useState("");
  const [location, setLocation] = useState("");
  const [technicalText, setTechnicalText] = useState("");
  const [commercialText, setCommercialText] = useState("");
  const [vendorIds, setVendorIds] = useState<number[]>([]);
  const [quantities, setQuantities] = useState<Record<number, string>>({});
  const [reason, setReason] = useState("");
  const [quoteVendor, setQuoteVendor] = useState(0);
  const [quoteRef, setQuoteRef] = useState("");
  const [quoteDate, setQuoteDate] = useState("");
  const [validDate, setValidDate] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [price, setPrice] = useState("");
  const [compareCurrency, setCompareCurrency] = useState("INR");
  const [rateDate, setRateDate] = useState("");
  const [rate, setRate] = useState("1");
  const [note, setNote] = useState("");
  const [awardQty, setAwardQty] = useState<Record<number, string>>({});
  const source = sources.find((row) => row.id === requisitionId);
  async function reload(id?: number) {
    const list = await api<RfqRow[]>(`/projects/${pid}/procurement/rfqs${status ? `?status=${encodeURIComponent(status)}` : ""}`);
    setRows(list);
    if (id) setSelected(await api<RfqRow>(`/projects/${pid}/procurement/rfqs/${id}`));
  }
  useEffect(() => {
    void reload().catch((err) => onError((err as Error).message));
    void api<RfqSource[]>(`/projects/${pid}/procurement/rfq-sources`).then(setSources).catch(() => setSources([]));
    void api<{ id: number; code: string; company: string; approval_status: string }[]>("/procurement/vendors")
      .then(setVendors)
      .catch(() => setVendors([]));
  }, [pid, status]);
  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      const row = await api<RfqRow>(`/projects/${pid}/procurement/rfqs`, "POST", {
        number,
        requisition_id: requisitionId,
        due_date: due,
        delivery_location: location,
        technical_requirements: technicalText,
        commercial_requirements: commercialText,
        vendor_ids: vendorIds,
        lines: (source?.lines || [])
          .filter((line) => quantities[line.id])
          .map((line) => ({ requisition_line_id: line.id, quantity: quantities[line.id] })),
      });
      setSelected(row);
      setNumber("");
      onError("");
      await reload(row.id);
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function act(path: string, body: unknown) {
    if (!selected) return;
    try {
      const row = await api<RfqRow>(`/projects/${pid}/procurement/rfqs/${selected.id}${path}`, "POST", body);
      setSelected(row);
      onError("");
      await reload(row.id);
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <h3 className="section-mark">
        <FileSearch size={18} strokeWidth={2.4} /> Quotations
      </h3>
      <ol className="review-chain">
        {RFQ_FLOW.map((step) => {
          const Icon = step.icon;
          return (
            <li key={step.name} className={`review-step ${step.tone}`}>
              <Icon size={16} strokeWidth={2.4} />
              <strong>{step.name}</strong>
              <em>{step.hint}</em>
            </li>
          );
        })}
      </ol>
      <p className="note-card note-alert">The lowest quotation is never selected automatically. Purchase orders stay closed after the award.</p>
      <label>
        Status
        <select aria-label="RFQ status" value={status} onChange={(e) => onStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["Draft", "Awaiting quotations", "Technical review", "Commercial comparison", "Awarded", "Cancelled"].map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
      </label>
      <div className="inline">
        {rows.map((row) => (
          <button key={row.id} type="button" onClick={() => void reload(row.id)}>
            {row.number} <Pill value={row.status} />
          </button>
        ))}
      </div>
      {context.access.rfq_edit && (
        <form className="option-grid" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark"><Scale size={18} strokeWidth={2.4} /> New RFQ</h3>
          <label>
            RFQ number
            <input aria-label="RFQ number" value={number} onChange={(e) => setNumber(e.target.value)} required />
          </label>
          <label>
            Approved requisition
            <select aria-label="RFQ requisition" value={requisitionId || ""} onChange={(e) => setRequisitionId(Number(e.target.value))} required>
              <option value="">Select requisition</option>
              {sources.map((row) => (
                <option key={row.id} value={row.id}>{row.number} · {row.discipline}</option>
              ))}
            </select>
          </label>
          {sources.length === 0 && rows.some((row) => row.status !== "Cancelled") && (
            <p className="note-card note-alert">
              An approved requisition is hidden while another RFQ still uses its quantity:{" "}
              {rows.filter((row) => row.status !== "Cancelled").map((row) => `${row.number} (${row.status})`).join(", ")}.
              Cancel that RFQ, or finish it, and the requisition is listed again.
            </p>
          )}
          {sources.length === 0 && rows.every((row) => row.status === "Cancelled") && (
            <p className="note-card note-alert">No approved requisition has quantity left. Approve a requisition first.</p>
          )}
          <label>
            Quotation due date
            <input aria-label="Quotation due date" type="date" value={due} onChange={(e) => setDue(e.target.value)} required />
          </label>
          <label>
            Delivery location
            <input aria-label="Delivery location" value={location} onChange={(e) => setLocation(e.target.value)} />
          </label>
          <label>
            Technical requirements
            <input aria-label="Technical requirements" value={technicalText} onChange={(e) => setTechnicalText(e.target.value)} required />
          </label>
          <label>
            Commercial requirements
            <input aria-label="Commercial requirements" value={commercialText} onChange={(e) => setCommercialText(e.target.value)} />
          </label>
          <fieldset>
            <legend>Approved vendors</legend>
            {vendors.filter((vendor) => vendor.approval_status === "Approved").length === 0 && (
              <p className="note-card note-alert">Approve a vendor in Master data before this RFQ can be saved.</p>
            )}
            {vendors.filter((vendor) => vendor.approval_status === "Approved").map((vendor) => (
              <label key={vendor.id}>
                <input
                  type="checkbox"
                  checked={vendorIds.includes(vendor.id)}
                  onChange={(e) =>
                    setVendorIds((current) =>
                      e.target.checked ? [...current, vendor.id] : current.filter((id) => id !== vendor.id),
                    )
                  }
                />
                {vendor.code} · {vendor.company}
              </label>
            ))}
          </fieldset>
          {source?.lines.map((line) => (
            <label key={line.id}>
              {line.item_code} remaining {line.remaining} {line.unit}
              <input
                aria-label={`RFQ quantity ${line.item_code}`}
                value={quantities[line.id] || ""}
                onChange={(e) => setQuantities((current) => ({ ...current, [line.id]: e.target.value }))}
              />
            </label>
          ))}
          <button type="submit" className="tone-submit">Save draft RFQ</button>
        </form>
      )}
      {selected && (
        <article className="comment-card">
          <div className="title-row">
            <h3>{selected.number}</h3>
            <Pill value={selected.status} />
          </div>
          <p>Requisition {selected.requisition_number} · {selected.discipline} · due {selected.due_date}</p>
          <p className="note-card note-alert">{selected.hint}</p>
          <p>Technical reviewer: {selected.technical_reviewers.map((person) => person.name).join(", ") || "Not set"}</p>
          <ol className="review-chain">
            {selected.steps.map((step) => {
              const Icon = RFQ_FLOW.find((item) => item.name === step.name)?.icon;
              return (
                <li key={step.name} className={`review-step ${step.status}`}>
                  {Icon ? <Icon size={16} strokeWidth={2.4} /> : null}
                  <strong>{step.name}</strong>
                  <em>{rfqStepLabel(step.status)}</em>
                </li>
              );
            })}
          </ol>
          <ul>
            {selected.lines.map((line) => (
              <li key={line.id}>{line.item_code} {line.quantity} {line.unit}</li>
            ))}
          </ul>
          <p>Invited: {selected.vendors.map((vendor) => `${vendor.code} · ${vendor.company}`).join("; ") || "None"}</p>
          <div className="inline">
            {selected.can_issue && (
              <button type="button" className="tone-submit" onClick={() => void act("/issue", { version: selected.version })}>
                Issue RFQ
              </button>
            )}
            {selected.can_start_technical && (
              <button type="button" className="tone-return" onClick={() => void act("/technical-review", { version: selected.version })}>
                Start technical review
              </button>
            )}
            {selected.can_cancel && (
              <button type="button" className="tone-withdraw" onClick={() => void act("/cancel", { reason, version: selected.version })}>
                Cancel RFQ
              </button>
            )}
          </div>
          {selected.can_cancel && (
            <input aria-label="RFQ cancel reason" placeholder="Reason, required to cancel" value={reason} onChange={(e) => setReason(e.target.value)} />
          )}
          {selected.quotations.map((quote) => (
            <article key={quote.id} className="note-card">
              <strong>{quote.vendor} · {quote.company}</strong> {quote.reference}
              {quote.technical_decision ? <Pill value={quote.technical_decision} /> : <Pill value="Awaiting technical review" />}
              {quote.lowest_quoted ? <Pill value="Lowest quoted" /> : null}
              <p>{quote.technical_deviations || "No technical deviation recorded."}</p>
              {selected.prices_visible && (
                <p>{quote.currency} total {quote.original_total}{quote.compared_total ? ` · compared ${quote.compared_total}` : ""}</p>
              )}
              {quote.technical_reason ? <p>{quote.technical_by_name}: {quote.technical_reason}</p> : null}
              {quote.commercial_note ? <p>Commercial: {quote.commercial_note}</p> : null}
              {selected.can_technical && (
                <div className="inline">
                  {["Compliant", "Deviation accepted", "Not compliant"].map((decision) => (
                    <button
                      key={decision}
                      type="button"
                      className={decision === "Not compliant" ? "tone-reject" : decision === "Compliant" ? "tone-approve" : "tone-return"}
                      onClick={() => void act("/technical", { quotation_id: quote.id, decision, reason, version: selected.version })}
                    >
                      {decision}
                    </button>
                  ))}
                </div>
              )}
            </article>
          ))}
          {selected.can_technical && (
            <input aria-label="Technical reason" placeholder="Reason, required for a deviation or non-compliant quotation" value={reason} onChange={(e) => setReason(e.target.value)} />
          )}
          {selected.can_quote && (
            <form
              className="option-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void act("/quotations", {
                  vendor_id: quoteVendor,
                  reference: quoteRef,
                  quotation_date: quoteDate,
                  validity_date: validDate,
                  currency,
                  freight: "0",
                  lines: selected.lines.map((line) => ({
                    rfq_line_id: line.id,
                    quantity: line.quantity,
                    unit_price: price,
                    discount: "0",
                    tax: "0",
                    lead_time_days: 0,
                  })),
                  version: selected.version,
                });
              }}
            >
              <h3>Record quotation</h3>
              <label>
                Invited vendor
                <select aria-label="Quotation vendor" value={quoteVendor || ""} onChange={(e) => setQuoteVendor(Number(e.target.value))} required>
                  <option value="">Select vendor</option>
                  {selected.vendors.map((vendor) => (
                    <option key={vendor.vendor_id} value={vendor.vendor_id}>{vendor.code}</option>
                  ))}
                </select>
              </label>
              <label>
                Quotation reference
                <input aria-label="Quotation reference" value={quoteRef} onChange={(e) => setQuoteRef(e.target.value)} required />
              </label>
              <label>
                Quotation date
                <input aria-label="Quotation date" type="date" value={quoteDate} onChange={(e) => setQuoteDate(e.target.value)} required />
              </label>
              <label>
                Validity date
                <input aria-label="Validity date" type="date" value={validDate} onChange={(e) => setValidDate(e.target.value)} required />
              </label>
              <label>
                Currency
                <input aria-label="Quotation currency" value={currency} onChange={(e) => setCurrency(e.target.value)} required />
              </label>
              <label>
                Unit price
                <input aria-label="Unit price" value={price} onChange={(e) => setPrice(e.target.value)} required />
              </label>
              <button type="submit" className="tone-submit">Save quotation</button>
            </form>
          )}
          {selected.can_commercial && (
            <form
              className="option-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void act("/commercial", {
                  comparison_currency: compareCurrency,
                  rate_date: rateDate,
                  notes: selected.quotations
                    .filter((quote) => quote.technical_decision !== "Not compliant")
                    .map((quote) => ({ quotation_id: quote.id, commercial_note: note, conversion_rate: rate })),
                  version: selected.version,
                });
              }}
            >
              <h3 className="section-mark"><Scale size={18} strokeWidth={2.4} /> Commercial comparison</h3>
              <label>
                Comparison currency
                <input aria-label="Comparison currency" value={compareCurrency} onChange={(e) => setCompareCurrency(e.target.value)} required />
              </label>
              <label>
                Rate date
                <input aria-label="Rate date" type="date" value={rateDate} onChange={(e) => setRateDate(e.target.value)} required />
              </label>
              <label>
                Conversion rate
                <input aria-label="Conversion rate" value={rate} onChange={(e) => setRate(e.target.value)} required />
              </label>
              <label>
                Commercial note
                <input aria-label="Commercial note" value={note} onChange={(e) => setNote(e.target.value)} required />
              </label>
              <button type="submit" className="tone-note">Save comparison</button>
            </form>
          )}
          {selected.can_award && (
            <form
              className="option-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void act("/award", {
                  reason,
                  lines: Object.entries(awardQty)
                    .filter(([, quantity]) => quantity)
                    .map(([id, quantity]) => ({ quotation_line_id: Number(id), quantity })),
                  version: selected.version,
                });
              }}
            >
              <h3 className="section-mark"><BadgeCheck size={18} strokeWidth={2.4} /> Award</h3>
              {selected.quotations.filter((quote) => quote.technical_decision === "Compliant" || quote.technical_decision === "Deviation accepted").map((quote) =>
                quote.lines.map((line) => (
                  <label key={line.id}>
                    {quote.vendor} · {line.item_code} quoted {line.quantity}
                    <input
                      aria-label={`Award quantity ${quote.vendor}`}
                      value={awardQty[line.id] || ""}
                      onChange={(e) => setAwardQty((current) => ({ ...current, [line.id]: e.target.value }))}
                    />
                  </label>
                )),
              )}
              <label>
                Selection reason
                <input aria-label="Award reason" value={reason} onChange={(e) => setReason(e.target.value)} required />
              </label>
              <button type="submit" className="tone-approve">Record award</button>
            </form>
          )}
          {selected.awards.length > 0 && (
            <p className="note-card note-good">
              Awarded {selected.awards.map((row) => `${row.vendor} ${row.quantity}`).join(", ")}. {selected.award_reason} {selected.ordering_note}
            </p>
          )}
        </article>
      )}
    </section>
  );
}

const PO_FLOW = [
  { name: "Draft", hint: "Buyer prepares", icon: Pencil, tone: "stage-draft" },
  { name: "Pending Approval", hint: "Saved reviewer", icon: ClipboardCheck, tone: "stage-technical" },
  { name: "Approved", hint: "Ready to issue", icon: BadgeCheck, tone: "stage-awarded" },
  { name: "Issued", hint: "Commitment", icon: Send, tone: "stage-commercial" },
  { name: "Acknowledged", hint: "Supplier reply", icon: ScrollText, tone: "stage-awaiting" },
  { name: "Partially Received", hint: "Some arrived", icon: Truck, tone: "stage-awaiting" },
  { name: "Received", hint: "Full quantity", icon: Package, tone: "stage-commercial" },
  { name: "Closed", hint: "Delivery finished", icon: BadgeCheck, tone: "stage-awarded" },
] as const;

type OrderSource = {
  rfq_id: number;
  rfq_number: string;
  vendor_id: number;
  vendor: string;
  company: string;
  requisition_number: string;
  discipline: string;
  lines: { award_id: number; item_code: string; remaining: string; unit: string }[];
};

type OrderRow = {
  id: number;
  number: string;
  status: string;
  rfq_number: string;
  vendor: string;
  company: string;
  discipline: string;
  currency: string;
  prices_visible: boolean;
  terms: string;
  delivery_location: string;
  promised_date: string;
  issue_date: string;
  acknowledgment_note: string;
  amendment_reason: string;
  cancellation_reason: string;
  closure_reason: string;
  supersedes_number: string;
  successor_number: string;
  version: number;
  approvers: { id: number; name: string }[];
  steps: { name: string; status: string }[];
  hint: string;
  lines: { id: number; award_id: number; item_code: string; quantity: string; received: string; remaining: string; unit: string; unit_price: string | null }[];
  receipts: { id: number; number: string; status: string; receipt_date: string }[];
  review: Review | null;
  ordering_note: string;
  can_submit: boolean;
  can_resubmit: boolean;
  can_issue: boolean;
  can_acknowledge: boolean;
  can_cancel: boolean;
  can_amend: boolean;
  can_close: boolean;
};

function Orders({
  pid,
  context,
  status,
  onStatus,
  onError,
}: {
  pid: number;
  context: Context;
  status: string;
  onStatus: (value: string) => void;
  onError: (text: string) => void;
}) {
  const [rows, setRows] = useState<OrderRow[]>([]);
  const [selected, setSelected] = useState<OrderRow | null>(null);
  const [sources, setSources] = useState<OrderSource[]>([]);
  const [sourcesReady, setSourcesReady] = useState(false);
  const [sourceKey, setSourceKey] = useState("");
  const [number, setNumber] = useState("");
  const [promised, setPromised] = useState("");
  const [location, setLocation] = useState("");
  const [terms, setTerms] = useState("");
  const [quantities, setQuantities] = useState<Record<number, string>>({});
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [amendNumber, setAmendNumber] = useState("");
  const [amendQty, setAmendQty] = useState<Record<number, string>>({});
  const source = sources.find((row) => `${row.rfq_id}:${row.vendor_id}` === sourceKey);
  async function reload(id?: number) {
    const list = await api<OrderRow[]>(`/projects/${pid}/procurement/orders${status ? `?status=${encodeURIComponent(status)}` : ""}`);
    setRows(list);
    if (id) setSelected(await api<OrderRow>(`/projects/${pid}/procurement/orders/${id}`));
  }
  useEffect(() => {
    void reload().catch((err) => onError((err as Error).message));
    setSourcesReady(false);
    void api<OrderSource[]>(`/projects/${pid}/procurement/order-sources`)
      .then((rows) => {
        setSources(rows);
        setSourcesReady(true);
      })
      .catch(() => {
        setSources([]);
        setSourcesReady(true);
      });
  }, [pid, status]);
  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      const row = await api<OrderRow>(`/projects/${pid}/procurement/orders`, "POST", {
        number,
        promised_date: promised,
        delivery_location: location,
        terms,
        lines: (source?.lines || [])
          .filter((line) => quantities[line.award_id])
          .map((line) => ({ award_id: line.award_id, quantity: quantities[line.award_id] })),
      });
      setNumber("");
      onError("");
      await reload(row.id);
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function act(path: string, body: unknown) {
    if (!selected) return;
    try {
      const row = await api<OrderRow>(`/projects/${pid}/procurement/orders/${selected.id}${path}`, "POST", body);
      setSelected(row);
      onError("");
      await reload(row.id);
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <h3 className="section-mark">
        <ScrollText size={18} strokeWidth={2.4} /> Purchase orders
      </h3>
      <ol className="review-chain">
        {PO_FLOW.map((step) => {
          const Icon = step.icon;
          return (
            <li key={step.name} className={`review-step ${step.tone}`}>
              <Icon size={16} strokeWidth={2.4} />
              <strong>{step.name}</strong>
              <em>{step.hint}</em>
            </li>
          );
        })}
      </ol>
      <p className="note-card note-alert">The buyer prepares the order from an award. The saved reviewer approves it. The buyer then issues it. Goods receipts records what arrived. Stock is not posted.</p>
      <label>
        Status
        <select aria-label="Purchase order status" value={status} onChange={(e) => onStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["Draft", "Pending Approval", "Returned for Correction", "Approved", "Issued", "Acknowledged", "Partially Received", "Received", "Closed", "Superseded", "Rejected", "Cancelled"].map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
      </label>
      <div className="inline">
        {rows.map((row) => (
          <button key={row.id} type="button" onClick={() => void reload(row.id)}>
            {row.number} <Pill value={row.status} />
          </button>
        ))}
      </div>
      {context.access.po_edit && (
        <form className="option-grid" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark"><Send size={18} strokeWidth={2.4} /> New purchase order</h3>
          <label>
            Order number
            <input aria-label="Purchase order number" value={number} onChange={(e) => setNumber(e.target.value)} required />
          </label>
          <label>
            Awarded vendor
            <select aria-label="Awarded vendor" value={sourceKey} onChange={(e) => setSourceKey(e.target.value)} required>
              <option value="">Select award</option>
              {sources.map((row) => (
                <option key={`${row.rfq_id}:${row.vendor_id}`} value={`${row.rfq_id}:${row.vendor_id}`}>
                  RFQ {row.rfq_number} · {row.vendor} · requisition {row.requisition_number}
                </option>
              ))}
            </select>
          </label>
          <label>
            Promised date
            <input aria-label="Promised date" type="date" value={promised} onChange={(e) => setPromised(e.target.value)} required />
          </label>
          <label>
            Delivery location
            <input aria-label="Order delivery location" value={location} onChange={(e) => setLocation(e.target.value)} />
          </label>
          <label>
            Terms
            <input aria-label="Order terms" value={terms} onChange={(e) => setTerms(e.target.value)} />
          </label>
          {sourcesReady && sources.length === 0 && <p className="note-card note-alert">No awarded quantity is waiting. Finish a quotation award before creating an order.</p>}
          {source?.lines.map((line) => (
            <label key={line.award_id}>
              {line.item_code} remaining {line.remaining} {line.unit}
              <input
                aria-label={`Order quantity ${line.item_code}`}
                value={quantities[line.award_id] || ""}
                onChange={(e) => setQuantities((current) => ({ ...current, [line.award_id]: e.target.value }))}
              />
            </label>
          ))}
          <button type="submit" className="tone-submit">Save draft order</button>
        </form>
      )}
      {selected && (
        <article className="comment-card">
          <div className="title-row">
            <h3>{selected.number}</h3>
            <Pill value={selected.status} />
          </div>
          <p>RFQ {selected.rfq_number} · {selected.vendor} · {selected.company} · {selected.discipline}</p>
          <p>Promised {selected.promised_date}{selected.issue_date ? ` · issued ${selected.issue_date}` : ""}</p>
          {selected.supersedes_number ? <p>Amends {selected.supersedes_number}. {selected.amendment_reason}</p> : null}
          {selected.successor_number ? <p>Current revision {selected.successor_number}</p> : null}
          <p className="note-card note-alert">{selected.hint}</p>
          <p>Approver: {selected.approvers.map((person) => person.name).join(", ") || "Not set"}</p>
          <ol className="review-chain">
            {selected.steps.map((step) => {
              const Icon = PO_FLOW.find((item) => item.name === step.name)?.icon;
              return (
                <li key={step.name} className={`review-step ${step.status}`}>
                  {Icon ? <Icon size={16} strokeWidth={2.4} /> : null}
                  <strong>{step.name}</strong>
                  <em>{rfqStepLabel(step.status)}</em>
                </li>
              );
            })}
          </ol>
          <ul>
            {selected.lines.map((line) => (
              <li key={line.id}>
                {line.item_code} {line.quantity} {line.unit}
                {selected.prices_visible && line.unit_price ? ` · ${selected.currency} ${line.unit_price}` : ""}
                {["Issued", "Acknowledged", "Partially Received", "Received", "Closed", "Superseded"].includes(selected.status)
                  ? ` · received ${line.received} · still to receive ${line.remaining}`
                  : ""}
              </li>
            ))}
          </ul>
          <p className="note-card">{selected.ordering_note}</p>
          {selected.acknowledgment_note ? <p>Acknowledgement: {selected.acknowledgment_note}</p> : null}
          {selected.cancellation_reason ? <p>Cancelled: {selected.cancellation_reason}</p> : null}
          {selected.closure_reason ? <p>Closed: {selected.closure_reason}</p> : null}
          {selected.receipts.length > 0 && (
            <p>Receipts: {selected.receipts.map((row) => `${row.number} (${row.status})`).join(", ")}</p>
          )}
          {selected.review && (
            <>
              <p>{selected.review.subject}. Review {selected.review.state}.</p>
              {selected.review.actions.length === 0 && selected.review.state === "In Review" && (
                <p className="note-card note-alert">Approve and Reject are with the saved purchase order reviewer.</p>
              )}
              {selected.review.actions.some((action) => action === "approve" || action === "reject" || action === "return") && (
                <div className="inline">
                  {selected.review.actions.filter((action) => action === "approve" || action === "reject" || action === "return").map((action) => (
                    <button
                      key={action}
                      type="button"
                      className={actionClass(action)}
                      onClick={() => {
                        if ((action === "reject" || action === "return") && !reason.trim()) {
                          onError("Type the reason, then choose Return or Reject.");
                          return;
                        }
                        void api(`/reviews/${selected.review!.id}/decisions`, "POST", {
                          action,
                          reason,
                          version: selected.review!.version,
                        })
                          .then(() => reload(selected.id))
                          .catch((err) => onError((err as Error).message));
                      }}
                    >
                      {action === "approve" ? "Approve" : action === "return" ? "Return" : "Reject"}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
          <div className="inline">
            {selected.can_submit && (
              <button type="button" className="tone-submit" onClick={() => void act("/submit", { version: selected.version })}>
                Submit for approval
              </button>
            )}
            {selected.can_resubmit && selected.review && (
              <button type="button" className="tone-submit" onClick={() => void act("/resubmit", { version: selected.version, review_version: selected.review!.version })}>
                Resubmit
              </button>
            )}
            {selected.can_issue && (
              <button type="button" className="tone-approve" onClick={() => void act("/issue", { version: selected.version })}>
                Issue order
              </button>
            )}
            {selected.can_cancel && (
              <button type="button" className="tone-withdraw" onClick={() => void act("/cancel", { reason, version: selected.version })}>
                Cancel order
              </button>
            )}
            {selected.can_close && (
              <button
                type="button"
                className="tone-approve"
                onClick={() => {
                  if (!reason.trim()) {
                    onError("Type the reason, then close the order.");
                    return;
                  }
                  void act("/close", { reason, version: selected.version });
                }}
              >
                Close order
              </button>
            )}
          </div>
          {(selected.can_cancel || selected.can_close || selected.review) && (
            <input aria-label="Order reason" placeholder="Reason, required to cancel, close, return, or reject" value={reason} onChange={(e) => setReason(e.target.value)} />
          )}
          {selected.can_acknowledge && (
            <form
              className="option-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void act("/acknowledge", { note, version: selected.version });
              }}
            >
              <h3>Supplier acknowledgement</h3>
              <label>
                Note
                <input aria-label="Acknowledgement note" value={note} onChange={(e) => setNote(e.target.value)} required />
              </label>
              <button type="submit" className="tone-note">Record acknowledgement</button>
            </form>
          )}
          {selected.can_amend && (
            <form
              className="option-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void act("/amendments", {
                  number: amendNumber,
                  promised_date: selected.promised_date,
                  delivery_location: selected.delivery_location,
                  terms: selected.terms,
                  reason,
                  lines: selected.lines
                    .filter((line) => amendQty[line.award_id])
                    .map((line) => ({ award_id: line.award_id, quantity: amendQty[line.award_id] })),
                });
              }}
            >
              <h3 className="section-mark"><Scale size={18} strokeWidth={2.4} /> Amendment</h3>
              <p>The issued revision stays on record. This amendment must be approved and issued before it replaces the commitment.</p>
              <label>
                Amendment number
                <input aria-label="Amendment number" value={amendNumber} onChange={(e) => setAmendNumber(e.target.value)} required />
              </label>
              {selected.lines.map((line) => (
                <label key={line.award_id}>
                  {line.item_code} issued {line.quantity} {line.unit}
                  <input
                    aria-label={`Amend quantity ${line.item_code}`}
                    value={amendQty[line.award_id] || ""}
                    onChange={(e) => setAmendQty((current) => ({ ...current, [line.award_id]: e.target.value }))}
                  />
                </label>
              ))}
              <label>
                Amendment reason
                <input aria-label="Amendment reason" value={reason} onChange={(e) => setReason(e.target.value)} required />
              </label>
              <button type="submit" className="tone-return">Save amendment</button>
            </form>
          )}
        </article>
      )}
    </section>
  );
}

const RECEIPT_FLOW = [
  { name: "Posted", hint: "Quantity recorded", icon: Truck, tone: "stage-commercial" },
  { name: "Partially Received", hint: "Some arrived", icon: Package, tone: "stage-awaiting" },
  { name: "Received", hint: "Full quantity", icon: ClipboardCheck, tone: "stage-technical" },
  { name: "Closed", hint: "Delivery finished", icon: BadgeCheck, tone: "stage-awarded" },
] as const;

type ReceiptSource = {
  purchase_order_id: number;
  number: string;
  status: string;
  vendor: string;
  discipline: string;
  lines: { purchase_order_line_id: number; item_code: string; ordered: string; remaining: string; unit: string }[];
};

type ReceiptRow = {
  id: number;
  number: string;
  status: string;
  purchase_order_number: string;
  order_status: string;
  vendor: string;
  discipline: string;
  receipt_date: string;
  delivery_note: string;
  warehouse: string;
  cancellation_reason: string;
  version: number;
  lines: { id: number; item_code: string; quantity: string; unit: string }[];
  order_steps: { name: string; status: string }[];
  can_cancel: boolean;
  hint: string;
};

function Receipts({
  pid,
  context,
  status,
  onStatus,
  onError,
}: {
  pid: number;
  context: Context;
  status: string;
  onStatus: (value: string) => void;
  onError: (text: string) => void;
}) {
  const [rows, setRows] = useState<ReceiptRow[]>([]);
  const [selected, setSelected] = useState<ReceiptRow | null>(null);
  const [sources, setSources] = useState<ReceiptSource[]>([]);
  const [sourcesReady, setSourcesReady] = useState(false);
  const [orderId, setOrderId] = useState("");
  const [number, setNumber] = useState("");
  const [receiptDate, setReceiptDate] = useState("");
  const [deliveryNote, setDeliveryNote] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [quantities, setQuantities] = useState<Record<number, string>>({});
  const [reason, setReason] = useState("");
  const source = sources.find((row) => String(row.purchase_order_id) === orderId);
  async function reload(id?: number) {
    const list = await api<ReceiptRow[]>(`/projects/${pid}/procurement/receipts${status ? `?status=${encodeURIComponent(status)}` : ""}`);
    setRows(list);
    if (id) setSelected(await api<ReceiptRow>(`/projects/${pid}/procurement/receipts/${id}`));
  }
  useEffect(() => {
    void reload().catch((err) => onError((err as Error).message));
    setSourcesReady(false);
    void api<ReceiptSource[]>(`/projects/${pid}/procurement/receipt-sources`)
      .then((next) => {
        setSources(next);
        setSourcesReady(true);
      })
      .catch(() => {
        setSources([]);
        setSourcesReady(true);
      });
  }, [pid, status]);
  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      const row = await api<ReceiptRow>(`/projects/${pid}/procurement/receipts`, "POST", {
        number,
        purchase_order_id: Number(orderId),
        receipt_date: receiptDate,
        delivery_note: deliveryNote,
        warehouse_id: warehouseId ? Number(warehouseId) : null,
        lines: (source?.lines || [])
          .filter((line) => quantities[line.purchase_order_line_id])
          .map((line) => ({ purchase_order_line_id: line.purchase_order_line_id, quantity: quantities[line.purchase_order_line_id] })),
      });
      setNumber("");
      setQuantities({});
      onError("");
      await reload(row.id);
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <h3 className="section-mark">
        <Truck size={18} strokeWidth={2.4} /> Goods receipts
      </h3>
      <ol className="review-chain">
        {RECEIPT_FLOW.map((step) => {
          const Icon = step.icon;
          return (
            <li key={step.name} className={`review-step ${step.tone}`}>
              <Icon size={16} strokeWidth={2.4} />
              <strong>{step.name}</strong>
              <em>{step.hint}</em>
            </li>
          );
        })}
      </ol>
      <p className="note-card note-alert">
        Stores records what arrived against an issued or acknowledged order. A partial delivery marks the order Partially Received. The full quantity marks it Received. Close the order when delivery is finished. Accept the receipt on Stock before the quantity can be issued. Open Invoices to record the supplier bill. Matching and payment stay closed.
      </p>
      <label>
        Status
        <select aria-label="Receipt status" value={status} onChange={(e) => onStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["Posted", "Cancelled"].map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
      </label>
      <div className="inline">
        {rows.map((row) => (
          <button key={row.id} type="button" onClick={() => void reload(row.id)}>
            {row.number} <Pill value={row.status} />
          </button>
        ))}
      </div>
      {context.access.receipt_edit && (
        <form className="option-grid" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark"><Truck size={18} strokeWidth={2.4} /> New goods receipt</h3>
          <label>
            Receipt number
            <input aria-label="Receipt number" value={number} onChange={(e) => setNumber(e.target.value)} required />
          </label>
          <label>
            Purchase order
            <select aria-label="Receipt purchase order" value={orderId} onChange={(e) => setOrderId(e.target.value)} required>
              <option value="">Select order</option>
              {sources.map((row) => (
                <option key={row.purchase_order_id} value={row.purchase_order_id}>
                  {row.number} · {row.vendor} · {row.status}
                </option>
              ))}
            </select>
          </label>
          <label>
            Receipt date
            <input aria-label="Receipt date" type="date" value={receiptDate} onChange={(e) => setReceiptDate(e.target.value)} required />
          </label>
          <label>
            Delivery note
            <input aria-label="Delivery note" value={deliveryNote} onChange={(e) => setDeliveryNote(e.target.value)} />
          </label>
          <label>
            Warehouse
            <select aria-label="Receipt warehouse" value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
              <option value="">No warehouse</option>
              {context.warehouses.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.code} · {row.name}
                </option>
              ))}
            </select>
          </label>
          {sourcesReady && sources.length === 0 && (
            <p className="note-card note-alert">No issued order is waiting for a delivery. Issue a purchase order first.</p>
          )}
          {source?.lines.map((line) => (
            <label key={line.purchase_order_line_id}>
              {line.item_code} still to receive {line.remaining} of {line.ordered} {line.unit}
              <input
                aria-label={`Receipt quantity ${line.item_code}`}
                value={quantities[line.purchase_order_line_id] || ""}
                onChange={(e) => setQuantities((current) => ({ ...current, [line.purchase_order_line_id]: e.target.value }))}
              />
            </label>
          ))}
          <button type="submit" className="tone-submit">Post receipt</button>
        </form>
      )}
      {selected && (
        <article className="comment-card">
          <div className="title-row">
            <h3>{selected.number}</h3>
            <Pill value={selected.status} />
          </div>
          <p>
            Purchase order {selected.purchase_order_number} <Pill value={selected.order_status} /> · {selected.vendor} · {selected.discipline}
          </p>
          <p>
            Received {selected.receipt_date}
            {selected.delivery_note ? ` · note ${selected.delivery_note}` : ""}
            {selected.warehouse ? ` · warehouse ${selected.warehouse}` : ""}
          </p>
          <p className="note-card note-alert">{selected.hint}</p>
          <ol className="review-chain">
            {selected.order_steps.map((step) => {
              const Icon = PO_FLOW.find((item) => item.name === step.name)?.icon;
              return (
                <li key={step.name} className={`review-step ${step.status}`}>
                  {Icon ? <Icon size={16} strokeWidth={2.4} /> : null}
                  <strong>{step.name}</strong>
                  <em>{rfqStepLabel(step.status)}</em>
                </li>
              );
            })}
          </ol>
          <ul>
            {selected.lines.map((line) => (
              <li key={line.id}>
                {line.item_code} {line.quantity} {line.unit}
              </li>
            ))}
          </ul>
          {selected.cancellation_reason ? <p>Cancelled: {selected.cancellation_reason}</p> : null}
          {selected.can_cancel && (
            <form
              className="option-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void api<ReceiptRow>(`/projects/${pid}/procurement/receipts/${selected.id}/cancel`, "POST", {
                  reason,
                  version: selected.version,
                })
                  .then((row) => {
                    setReason("");
                    onError("");
                    return reload(row.id);
                  })
                  .catch((err) => onError((err as Error).message));
              }}
            >
              <label>
                Cancellation reason
                <input aria-label="Receipt cancellation reason" value={reason} onChange={(e) => setReason(e.target.value)} required />
              </label>
              <button type="submit" className="tone-withdraw">Cancel receipt</button>
            </form>
          )}
        </article>
      )}
    </section>
  );
}

const STOCK_FLOW = [
  { name: "Accept", hint: "Into warehouse", icon: Warehouse, tone: "stage-awarded" },
  { name: "Reserve", hint: "Hold available", icon: Lock, tone: "stage-awaiting" },
  { name: "Issue", hint: "To a recipient", icon: Send, tone: "stage-commercial" },
  { name: "Return", hint: "Back to stock", icon: ArrowLeftRight, tone: "stage-technical" },
] as const;

type StockBalance = {
  warehouse_id: number;
  warehouse: string;
  item_id: number;
  item_code: string;
  unit: string;
  on_hand: string;
  reserved: string;
  available: string;
  issued: string;
  returned: string;
};

type AcceptSource = {
  goods_receipt_id: number;
  number: string;
  lines: { goods_receipt_line_id: number; item_code: string; remaining: string; unit: string }[];
};

type IssueSource = {
  issue_id: number;
  number: string;
  warehouse: string;
  recipient: string;
  lines: { source_line_id: number; item_code: string; remaining: string; unit: string }[];
};

type StockPosting = {
  id: number;
  number: string;
  kind: string;
  status: string;
  warehouse_id: number;
  warehouse: string;
  package_id: number | null;
  package_code: string;
  reason: string;
  recipient: string;
  goods_receipt_number: string;
  source_number: string;
  cancellation_reason: string;
  version: number;
  lines: { id: number; item_id: number; item_code: string; quantity: string; unit: string; remaining: string | null }[];
  can_cancel: boolean;
};

type OpenPackage = { id: number; code: string; status: string };

function Stock({ pid, context, onError }: { pid: number; context: Context; onError: (text: string) => void }) {
  const [balances, setBalances] = useState<StockBalance[]>([]);
  const [postings, setPostings] = useState<StockPosting[]>([]);
  const [acceptSources, setAcceptSources] = useState<AcceptSource[]>([]);
  const [issueSources, setIssueSources] = useState<IssueSource[]>([]);
  const [ready, setReady] = useState(false);
  const [action, setAction] = useState("Accept");
  const [number, setNumber] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [receiptId, setReceiptId] = useState("");
  const [issueId, setIssueId] = useState("");
  const [itemId, setItemId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState("");
  const [recipient, setRecipient] = useState("");
  const [returnQty, setReturnQty] = useState<Record<number, string>>({});
  const [acceptQty, setAcceptQty] = useState<Record<number, string>>({});
  const [packages, setPackages] = useState<OpenPackage[]>([]);
  const [packageId, setPackageId] = useState("");
  const [reservationId, setReservationId] = useState("");
  const receipt = acceptSources.find((row) => String(row.goods_receipt_id) === receiptId);
  const issue = issueSources.find((row) => String(row.issue_id) === issueId);
  const warehouseItems = balances.filter((row) => String(row.warehouse_id) === warehouseId && Number(row.available) > 0);
  const reservations = postings.filter(
    (row) => row.kind === "Reservation" && row.status === "Posted" && String(row.warehouse_id) === warehouseId,
  );
  const reservation = reservations.find((row) => String(row.id) === reservationId);
  async function reload() {
    const [rows, moves, accepts, issues, open] = await Promise.all([
      api<StockBalance[]>(`/projects/${pid}/procurement/stock`),
      api<StockPosting[]>(`/projects/${pid}/procurement/stock/postings`),
      api<AcceptSource[]>(`/projects/${pid}/procurement/stock/accept-sources`),
      api<IssueSource[]>(`/projects/${pid}/procurement/stock/issue-sources`),
      api<OpenPackage[]>(`/projects/${pid}/construction/packages`).catch(() => [] as OpenPackage[]),
    ]);
    setBalances(rows);
    setPostings(moves);
    setAcceptSources(accepts);
    setIssueSources(issues);
    setPackages(open.filter((row) => !["Cancelled", "Handed Over"].includes(row.status)));
    setReady(true);
  }
  useEffect(() => {
    void reload().catch((err) => onError((err as Error).message));
  }, [pid]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      if (action === "Accept") {
        await api(`/projects/${pid}/procurement/stock/acceptances`, "POST", {
          number,
          warehouse_id: Number(warehouseId),
          goods_receipt_id: Number(receiptId),
          lines: (receipt?.lines || [])
            .filter((line) => acceptQty[line.goods_receipt_line_id])
            .map((line) => ({ goods_receipt_line_id: line.goods_receipt_line_id, quantity: acceptQty[line.goods_receipt_line_id] })),
        });
      } else if (action === "Reserve") {
        await api(`/projects/${pid}/procurement/stock/reservations`, "POST", {
          number,
          warehouse_id: Number(warehouseId),
          reason,
          package_id: packageId ? Number(packageId) : null,
          lines: [{ item_id: Number(itemId), quantity }],
        });
      } else if (action === "Issue") {
        await api(`/projects/${pid}/procurement/stock/issues`, "POST", {
          number,
          warehouse_id: Number(warehouseId),
          reason,
          recipient,
          reservation_id: reservationId ? Number(reservationId) : null,
          lines: [{ item_id: Number(itemId), quantity }],
        });
      } else {
        await api(`/projects/${pid}/procurement/stock/returns`, "POST", {
          number,
          issue_id: Number(issueId),
          reason,
          lines: (issue?.lines || [])
            .filter((line) => returnQty[line.source_line_id])
            .map((line) => ({ source_line_id: line.source_line_id, quantity: returnQty[line.source_line_id] })),
        });
      }
      setNumber("");
      setQuantity("");
      setReason("");
      setRecipient("");
      setPackageId("");
      setReservationId("");
      setAcceptQty({});
      setReturnQty({});
      onError("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <h3 className="section-mark">
        <Warehouse size={18} strokeWidth={2.4} /> Stock
      </h3>
      <ol className="review-chain">
        {STOCK_FLOW.map((step) => {
          const Icon = step.icon;
          return (
            <li key={step.name} className={`review-step ${step.tone}`}>
              <Icon size={16} strokeWidth={2.4} />
              <strong>{step.name}</strong>
              <em>{step.hint}</em>
            </li>
          );
        })}
      </ol>
      <p className="note-card note-alert">
        A goods receipt does not add stock. Accept it into a warehouse first. Reserve holds available quantity. Issue cannot exceed what is available. A return puts issued quantity back. Inspection, matching, and payment stay closed.
      </p>
      <table>
        <thead>
          <tr>
            <th>Warehouse</th>
            <th>Item</th>
            <th>On hand</th>
            <th>Reserved</th>
            <th>Available</th>
            <th>Issued</th>
            <th>Returned</th>
          </tr>
        </thead>
        <tbody>
          {balances.map((row) => (
            <tr key={`${row.warehouse_id}-${row.item_id}`}>
              <td>{row.warehouse}</td>
              <td>{row.item_code}</td>
              <td>{row.on_hand} {row.unit}</td>
              <td>{row.reserved}</td>
              <td>{row.available}</td>
              <td>{row.issued}</td>
              <td>{row.returned}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {ready && balances.length === 0 && <p className="muted">No stock is on hand yet.</p>}
      <div className="inline">
        {postings.map((row) => (
          <span key={row.id}>
            {row.number} <Pill value={row.kind} /> <Pill value={row.status} />
            {row.package_code ? ` · ${row.package_code}` : ""}
          </span>
        ))}
      </div>
      {context.access.stock_edit && (
        <form className="option-grid" onSubmit={(event) => void submit(event)}>
          <h3 className="section-mark"><Warehouse size={18} strokeWidth={2.4} /> Record movement</h3>
          <label>
            Action
            <select aria-label="Stock action" value={action} onChange={(e) => setAction(e.target.value)}>
              {STOCK_FLOW.map((step) => (
                <option key={step.name}>{step.name}</option>
              ))}
            </select>
          </label>
          <label>
            Number
            <input aria-label="Stock number" value={number} onChange={(e) => setNumber(e.target.value)} required />
          </label>
          {action !== "Return" && (
            <label>
              Warehouse
              <select aria-label="Stock warehouse" value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)} required>
                <option value="">Select warehouse</option>
                {context.warehouses.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.code} · {row.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {ready && context.warehouses.length === 0 && action !== "Return" && (
            <p className="note-card note-alert">Create a warehouse in Master data before accepting stock.</p>
          )}
          {action === "Accept" && (
            <>
              <label>
                Goods receipt
                <select aria-label="Stock receipt" value={receiptId} onChange={(e) => setReceiptId(e.target.value)} required>
                  <option value="">Select receipt</option>
                  {acceptSources.map((row) => (
                    <option key={row.goods_receipt_id} value={row.goods_receipt_id}>
                      {row.number}
                    </option>
                  ))}
                </select>
              </label>
              {ready && acceptSources.length === 0 && <p className="note-card note-alert">No posted receipt is waiting to be accepted.</p>}
              {receipt?.lines.map((line) => (
                <label key={line.goods_receipt_line_id}>
                  {line.item_code} still to accept {line.remaining} {line.unit}
                  <input
                    aria-label={`Accept quantity ${line.item_code}`}
                    value={acceptQty[line.goods_receipt_line_id] || ""}
                    onChange={(e) => setAcceptQty((current) => ({ ...current, [line.goods_receipt_line_id]: e.target.value }))}
                  />
                </label>
              ))}
            </>
          )}
          {(action === "Reserve" || action === "Issue") && (
            <>
              {action === "Reserve" && (
                <label>
                  Work package
                  <select aria-label="Reserve package" value={packageId} onChange={(e) => setPackageId(e.target.value)}>
                    <option value="">Project stock, no package</option>
                    {packages.map((row) => (
                      <option key={row.id} value={row.id}>
                        {row.code} · {row.status}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {action === "Issue" && (
                <label>
                  From reservation
                  <select
                    aria-label="Issue reservation"
                    value={reservationId}
                    onChange={(e) => {
                      setReservationId(e.target.value);
                      setItemId("");
                    }}
                  >
                    <option value="">Free stock, no reservation</option>
                    {reservations.map((row) => (
                      <option key={row.id} value={row.id}>
                        {row.number}
                        {row.package_code ? ` · ${row.package_code}` : ""}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label>
                Item
                <select aria-label="Stock item" value={itemId} onChange={(e) => setItemId(e.target.value)} required>
                  <option value="">Select item</option>
                  {reservation
                    ? reservation.lines
                      .filter((line) => Number(line.remaining) > 0)
                      .map((line) => (
                        <option key={line.id} value={line.item_id}>
                          {line.item_code} reserved {line.remaining} {line.unit}
                        </option>
                      ))
                    : warehouseItems.map((row) => (
                      <option key={row.item_id} value={row.item_id}>
                        {row.item_code} available {row.available} {row.unit}
                      </option>
                    ))}
                </select>
              </label>
              {action === "Reserve" && !packageId && (
                <p className="note-card">A reservation without a work package does not satisfy package material readiness.</p>
              )}
              <label>
                Quantity
                <input aria-label="Stock quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
              </label>
              {action === "Issue" && (
                <label>
                  Recipient
                  <input aria-label="Issue recipient" value={recipient} onChange={(e) => setRecipient(e.target.value)} required />
                </label>
              )}
              <label>
                Reason
                <input aria-label="Stock reason" value={reason} onChange={(e) => setReason(e.target.value)} required />
              </label>
            </>
          )}
          {action === "Return" && (
            <>
              <label>
                Issue
                <select aria-label="Return issue" value={issueId} onChange={(e) => setIssueId(e.target.value)} required>
                  <option value="">Select issue</option>
                  {issueSources.map((row) => (
                    <option key={row.issue_id} value={row.issue_id}>
                      {row.number} · {row.warehouse} · {row.recipient}
                    </option>
                  ))}
                </select>
              </label>
              {ready && issueSources.length === 0 && <p className="note-card note-alert">No issued quantity is waiting to be returned.</p>}
              {issue?.lines.map((line) => (
                <label key={line.source_line_id}>
                  {line.item_code} still out {line.remaining} {line.unit}
                  <input
                    aria-label={`Return quantity ${line.item_code}`}
                    value={returnQty[line.source_line_id] || ""}
                    onChange={(e) => setReturnQty((current) => ({ ...current, [line.source_line_id]: e.target.value }))}
                  />
                </label>
              ))}
              <label>
                Reason
                <input aria-label="Return reason" value={reason} onChange={(e) => setReason(e.target.value)} required />
              </label>
            </>
          )}
          <button type="submit" className="tone-submit">Post {action.toLowerCase()}</button>
        </form>
      )}
    </section>
  );
}

const INVOICE_FLOW = [
  { name: "Draft", hint: "Enter the bill", icon: Pencil, tone: "stage-draft" },
  { name: "Recorded", hint: "Evidence saved", icon: BadgeCheck, tone: "stage-awarded" },
] as const;

type InvoiceSource = {
  purchase_order_id: number;
  number: string;
  status: string;
  vendor: string;
  discipline: string;
  lines: {
    purchase_order_line_id: number;
    item_code: string;
    ordered: string;
    received: string;
    invoiced: string;
    remaining: string;
    unit: string;
    order_unit_price: string | null;
  }[];
};

type InvoiceRow = {
  id: number;
  number: string;
  status: string;
  purchase_order_id: number;
  purchase_order_number: string;
  order_status: string;
  vendor: string;
  vendor_reference: string;
  discipline: string;
  invoice_date: string;
  note: string;
  cancellation_reason: string;
  version: number;
  prices_visible: boolean;
  can_record: boolean;
  can_cancel: boolean;
  hint: string;
  steps: { name: string; status: string }[];
  lines: {
    id: number;
    purchase_order_line_id: number;
    item_code: string;
    quantity: string;
    ordered: string;
    received: string;
    invoiced: string;
    unit: string;
    order_unit_price: string | null;
    billed_unit_price: string | null;
    amount: string | null;
  }[];
};

function Invoices({
  pid,
  context,
  status,
  onStatus,
  onError,
}: {
  pid: number;
  context: Context;
  status: string;
  onStatus: (value: string) => void;
  onError: (text: string) => void;
}) {
  const [rows, setRows] = useState<InvoiceRow[]>([]);
  const [selected, setSelected] = useState<InvoiceRow | null>(null);
  const [sources, setSources] = useState<InvoiceSource[]>([]);
  const [sourcesReady, setSourcesReady] = useState(false);
  const [orderId, setOrderId] = useState("");
  const [number, setNumber] = useState("");
  const [vendorReference, setVendorReference] = useState("");
  const [invoiceDate, setInvoiceDate] = useState("");
  const [note, setNote] = useState("");
  const [quantities, setQuantities] = useState<Record<number, string>>({});
  const [prices, setPrices] = useState<Record<number, string>>({});
  const [reason, setReason] = useState("");
  const source = sources.find((row) => String(row.purchase_order_id) === orderId);
  async function reload(id?: number) {
    const list = await api<InvoiceRow[]>(`/projects/${pid}/procurement/invoices${status ? `?status=${encodeURIComponent(status)}` : ""}`);
    setRows(list);
    const next = await api<InvoiceSource[]>(`/projects/${pid}/procurement/invoice-sources`);
    setSources(next);
    setSourcesReady(true);
    if (id) setSelected(await api<InvoiceRow>(`/projects/${pid}/procurement/invoices/${id}`));
  }
  useEffect(() => {
    void reload().catch((err) => onError((err as Error).message));
  }, [pid, status]);
  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      const row = await api<InvoiceRow>(`/projects/${pid}/procurement/invoices`, "POST", {
        number,
        purchase_order_id: Number(orderId),
        vendor_reference: vendorReference,
        invoice_date: invoiceDate,
        note,
        lines: (source?.lines || [])
          .filter((line) => quantities[line.purchase_order_line_id])
          .map((line) => ({
            purchase_order_line_id: line.purchase_order_line_id,
            quantity: quantities[line.purchase_order_line_id],
            billed_unit_price: prices[line.purchase_order_line_id],
          })),
      });
      setNumber("");
      setVendorReference("");
      setNote("");
      setQuantities({});
      setPrices({});
      onError("");
      await reload(row.id);
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function command(path: string, body: object) {
    if (!selected) return;
    try {
      const row = await api<InvoiceRow>(`/projects/${pid}/procurement/invoices/${selected.id}/${path}`, "POST", body);
      setReason("");
      onError("");
      await reload(row.id);
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <h3 className="section-mark">
        <Receipt size={18} strokeWidth={2.4} /> Invoices
      </h3>
      <ol className="review-chain">
        {INVOICE_FLOW.map((step) => {
          const Icon = step.icon;
          return (
            <li key={step.name} className={`review-step ${step.tone}`}>
              <Icon size={16} strokeWidth={2.4} />
              <strong>{step.name}</strong>
              <em>{step.hint}</em>
            </li>
          );
        })}
      </ol>
      <p className="note-card note-alert">
        Record the supplier bill against an issued purchase order. Ordered, received, and billed quantities stay visible together. A different billed price is saved as entered. This screen does not match the bill and does not pay it.
      </p>
      <label>
        Status
        <select aria-label="Invoice status" value={status} onChange={(e) => onStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["Draft", "Recorded", "Cancelled"].map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
      </label>
      <div className="inline">
        {rows.map((row) => (
          <button key={row.id} type="button" onClick={() => void reload(row.id)}>
            {row.number} <Pill value={row.status} />
          </button>
        ))}
      </div>
      {context.access.invoice_edit && (
        <form className="option-grid" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark"><Receipt size={18} strokeWidth={2.4} /> New vendor invoice</h3>
          <label>
            Invoice number
            <input aria-label="Invoice number" value={number} onChange={(e) => setNumber(e.target.value)} required />
          </label>
          <label>
            Supplier invoice number
            <input aria-label="Supplier invoice number" value={vendorReference} onChange={(e) => setVendorReference(e.target.value)} required />
          </label>
          <label>
            Invoice date
            <input aria-label="Invoice date" type="date" value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)} required />
          </label>
          <label>
            Purchase order
            <select aria-label="Invoice purchase order" value={orderId} onChange={(e) => setOrderId(e.target.value)} required>
              <option value="">Select order</option>
              {sources.map((row) => (
                <option key={row.purchase_order_id} value={row.purchase_order_id}>
                  {row.number} · {row.vendor} · {row.status}
                </option>
              ))}
            </select>
          </label>
          <label>
            Note
            <input aria-label="Invoice note" value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          {sourcesReady && sources.length === 0 && (
            <p className="note-card note-alert">No issued order still has quantity to bill.</p>
          )}
          {source?.lines.map((line) => (
            <label key={line.purchase_order_line_id}>
              {line.item_code} ordered {line.ordered} {line.unit} · received {line.received} · billed {line.invoiced} · still to bill {line.remaining}
              {line.order_unit_price ? ` · order price ${line.order_unit_price}` : ""}
              <input
                aria-label={`Invoice quantity ${line.item_code}`}
                placeholder="Billed quantity"
                value={quantities[line.purchase_order_line_id] || ""}
                onChange={(e) => setQuantities((current) => ({ ...current, [line.purchase_order_line_id]: e.target.value }))}
              />
              <input
                aria-label={`Billed price ${line.item_code}`}
                placeholder="Billed unit price"
                value={prices[line.purchase_order_line_id] || ""}
                onChange={(e) => setPrices((current) => ({ ...current, [line.purchase_order_line_id]: e.target.value }))}
              />
            </label>
          ))}
          <button type="submit" className="tone-submit">Save draft</button>
        </form>
      )}
      {selected && (
        <article className="comment-card">
          <div className="title-row">
            <h3>{selected.number}</h3>
            <Pill value={selected.status} />
          </div>
          <p>
            Purchase order {selected.purchase_order_number} <Pill value={selected.order_status} /> · {selected.vendor} · supplier bill {selected.vendor_reference}
          </p>
          <p>
            Invoice date {selected.invoice_date}
            {selected.note ? ` · ${selected.note}` : ""}
          </p>
          <p className="note-card note-alert">{selected.hint}</p>
          <ol className="review-chain">
            {selected.steps.map((step) => {
              const Icon = INVOICE_FLOW.find((item) => item.name === step.name)?.icon;
              return (
                <li key={step.name} className={`review-step ${step.status}`}>
                  {Icon ? <Icon size={16} strokeWidth={2.4} /> : null}
                  <strong>{step.name}</strong>
                  <em>{rfqStepLabel(step.status)}</em>
                </li>
              );
            })}
          </ol>
          <ul>
            {selected.lines.map((line) => (
              <li key={line.id}>
                {line.item_code} billed {line.quantity} {line.unit}
                {line.billed_unit_price ? ` at ${line.billed_unit_price}` : ""}
                {line.amount ? ` · amount ${line.amount}` : ""}
                {` · ordered ${line.ordered} · received ${line.received}`}
                {line.order_unit_price ? ` · order price ${line.order_unit_price}` : ""}
              </li>
            ))}
          </ul>
          {selected.cancellation_reason ? <p>Cancelled: {selected.cancellation_reason}</p> : null}
          {selected.can_record && (
            <button type="button" className="tone-submit" onClick={() => void command("record", { version: selected.version })}>
              Record bill
            </button>
          )}
          {selected.can_cancel && (
            <form
              className="option-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void command("cancel", { reason, version: selected.version });
              }}
            >
              <label>
                Cancel reason
                <input aria-label="Invoice cancel reason" value={reason} onChange={(e) => setReason(e.target.value)} required />
              </label>
              <button type="submit" className="tone-reject">Cancel invoice</button>
            </form>
          )}
        </article>
      )}
    </section>
  );
}
