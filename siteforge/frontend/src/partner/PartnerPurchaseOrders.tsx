import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";

type PartnerProject = { project_id: number; code: string; name: string };
type Order = {
  id: number;
  reference: string;
  status: string;
  currency: string;
  version: number;
  promised_date: string | null;
};
type Acknowledgment = { id: number; state: string; submitted_version: number; note: string; review_note: string | null };

const STATUS_TONE: Record<string, string> = {
  Issued: "blue",
  Acknowledged: "teal",
  "Partially Received": "amber",
  Received: "green",
  Closed: "grey",
  Superseded: "grey",
  Cancelled: "red",
  Rejected: "red",
};

export function PartnerPurchaseOrders({ initialProjectId }: { initialProjectId: number | null }) {
  const [projects, setProjects] = useState<PartnerProject[]>([]);
  const [pid, setPid] = useState<number | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);

  useEffect(() => {
    api<{ items: PartnerProject[] }>("/partner/projects")
      .then((body) => {
        setProjects(body.items);
        const wanted = body.items.find((p) => p.project_id === initialProjectId) || body.items[0];
        setPid(wanted ? wanted.project_id : null);
      })
      .catch((err) => setError((err as Error).message));
  }, [initialProjectId]);

  useEffect(() => {
    setOrders([]);
    setOpenId(null);
    if (!pid) return;
    setLoading(true);
    api<{ items: Order[] }>(`/partner/projects/${pid}/transactions?kind=purchase_orders&limit=100`)
      .then((body) => {
        setOrders(body.items);
        setError("");
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [pid]);

  return (
    <section className="panel">
      <h2>Purchase orders</h2>
      <p className="muted">
        Orders issued to your company on this project. Acknowledging an order sends it to the buyer for review; the
        order itself does not change until the buyer accepts.
      </p>
      {projects.length > 1 ? (
        <label>
          Project{" "}
          <select value={pid ?? ""} onChange={(e) => setPid(Number(e.target.value))}>
            {projects.map((p) => (
              <option key={p.project_id} value={p.project_id}>
                {p.code} — {p.name}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {error ? (
        <div role="alert" className="error">
          {error}
        </div>
      ) : null}
      {!error && !projects.length ? <p className="muted">Your company is not on any active project yet.</p> : null}
      {loading ? <p className="muted">Loading purchase orders…</p> : null}
      {pid && !loading && !error && !orders.length ? (
        <p className="muted">No purchase orders have been issued to your company on this project.</p>
      ) : null}
      {orders.length ? (
        <div className="mp-table-wrap">
          <table className="mp-table">
            <thead>
              <tr>
                <th>PO number</th>
                <th>Status</th>
                <th>Currency</th>
                <th>Promised date</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <OrderRow
                  key={order.id}
                  pid={pid!}
                  order={order}
                  open={openId === order.id}
                  onToggle={() => setOpenId(openId === order.id ? null : order.id)}
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function OrderRow({
  pid,
  order,
  open,
  onToggle,
}: {
  pid: number;
  order: Order;
  open: boolean;
  onToggle: () => void;
}) {
  const [history, setHistory] = useState<Acknowledgment[] | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!open) return;
    api<{ items: Acknowledgment[] }>(`/partner/projects/${pid}/purchase-orders/${order.id}/acknowledgments`)
      .then((body) => setHistory(body.items))
      .catch((err) => setError((err as Error).message));
  }, [open, pid, order.id, tick]);

  const alreadySent = history?.some((row) => row.submitted_version === order.version);
  const canAcknowledge = order.status === "Issued" && history !== null && !alreadySent;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const result = await api<{ message: string }>(
        `/partner/projects/${pid}/purchase-orders/${order.id}/acknowledgments`,
        "POST",
        { note, po_version: order.version },
      );
      setNote("");
      setNotice(result.message);
      setTick((t) => t + 1);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <tr>
        <td>
          <strong>{order.reference}</strong>
        </td>
        <td>
          <span className={`ed-pill ed-${STATUS_TONE[order.status] || "grey"}`}>{order.status}</span>
        </td>
        <td>{order.currency || "—"}</td>
        <td>{order.promised_date ? new Date(order.promised_date).toLocaleDateString() : "—"}</td>
        <td>
          <button type="button" onClick={onToggle}>
            {open ? "Hide" : order.status === "Issued" ? "Acknowledge" : "Details"}
          </button>
        </td>
      </tr>
      {open ? (
        <tr>
          <td colSpan={5}>
            {error ? (
              <div role="alert" className="error">
                {error}
              </div>
            ) : null}
            {notice ? <p className="muted">{notice}</p> : null}
            {history === null && !error ? <p className="muted">Loading acknowledgments…</p> : null}
            {history?.length ? (
              <ul>
                {history.map((row) => (
                  <li key={row.id}>
                    Version {row.submitted_version} · <strong>{row.state}</strong> · {row.note}
                    {row.review_note ? ` · Buyer: ${row.review_note}` : ""}
                  </li>
                ))}
              </ul>
            ) : history ? (
              <p className="muted">No acknowledgment sent yet.</p>
            ) : null}
            {alreadySent ? <p className="muted">An acknowledgment for this order version is already with the buyer.</p> : null}
            {order.status !== "Issued" ? <p className="muted">Only issued orders can be acknowledged.</p> : null}
            {canAcknowledge ? (
              <form className="inline" onSubmit={(e) => void submit(e)}>
                <input
                  required
                  maxLength={2000}
                  placeholder="Acknowledgment note, e.g. accepted, delivery as promised"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
                <button className="primary" disabled={!note.trim()}>
                  Send acknowledgment
                </button>
              </form>
            ) : null}
          </td>
        </tr>
      ) : null}
    </>
  );
}
