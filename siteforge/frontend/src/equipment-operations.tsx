import { useEffect, useState } from "react";
import { api } from "./api";

export type OperationTab = "Availability" | "Allocations" | "Usage" | "Custody";
type AssetOption = { id: number; asset_code: string; name: string; operational_condition?: string | null; status: string };
type ApiRows<T> = { items: T[]; basis?: string; limit?: number };
type Compliance = { compliance_eligible: boolean; reason?: string | null; holds?: Array<{ id: number; status: string; reason: string }>; evidence?: Array<{ id: number; kind: string; status: string; valid_through?: string | null }>; basis?: string };
type Custody = { id: number; action: string; quantity: number; custodian_user_id?: number; allocation_id?: number | null; location?: string; recorded_at?: string; parent_issue_id?: number | null };
type Usage = { id: number; allocation_id: number; starts_at: string; ends_at: string; operating_hours: number; idle_hours: number; breakdown_hours: number; maintenance_hours: number; meter_start?: number | null; meter_end?: number | null; fuel_liters?: number | null; evidence_ref?: string };
type Allocation = { id: number; resource_type: string; resource_ref: string; starts_at: string; ends_at: string; status: string; activity_id?: number };
type Result = { compliance?: Compliance; custody?: { items: Custody[]; available_quantity?: number; basis?: string }; usage?: ApiRows<Usage>; allocations?: ApiRows<Allocation> };
const surface: React.CSSProperties = { background: "#fff", border: "1px solid #dce4ed", borderRadius: 12, padding: 18 };
const th: React.CSSProperties = { textAlign: "left", padding: 8, borderBottom: "1px solid #dce4ed" };
const td: React.CSSProperties = { padding: 8, borderBottom: "1px solid #eef1f6" };
const str = (value: unknown): string => value === null || value === undefined || value === "" ? "—" : String(value);
function GridTable({ headers, rows }: { headers: string[]; rows: (string | number)[][] }) {
  return <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr>{headers.map(h => <th key={h} style={th}>{h}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} style={td}>{c}</td>)}</tr>)}</tbody></table>{rows.length === 0 && <p>No verified records returned for this selection.</p>}</div>;
}

/** Read-only operational evidence. No client-side availability certification or cost posting. */
export function EquipmentOperations({ project, tab, assets }: { project: number; tab: OperationTab; assets: AssetOption[] }) {
  const [assetId, setAssetId] = useState(0);
  const [scheduleId, setScheduleId] = useState("");
  const [result, setResult] = useState<Result>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => { setAssetId(0); setScheduleId(""); setResult({}); setError(""); }, [project]);
  const selected = assets.find(a => a.id === assetId);
  useEffect(() => {
    let alive = true;
    setResult({}); setError("");
    if (!project || (tab === "Allocations" ? !/^\d+$/.test(scheduleId) || Number(scheduleId) <= 0 : !assetId)) return;
    setBusy(true);
    const prefix = `/projects/${project}/planning`;
    const requests: Array<Promise<[keyof Result, unknown]>> = tab === "Allocations"
      ? [["allocations", api<ApiRows<Allocation>>(`${prefix}/allocations?schedule_id=${Number(scheduleId)}`)]].map(async ([key, p]): Promise<[keyof Result, unknown]> => [key as keyof Result, await p])
      : tab === "Availability"
        ? [["compliance", api<Compliance>(`${prefix}/equipment-assets/${assetId}/compliance-status`)]].map(async ([key, p]): Promise<[keyof Result, unknown]> => [key as keyof Result, await p])
        : tab === "Custody"
          ? [["custody", api<Result["custody"]>(`${prefix}/equipment-assets/${assetId}/custody`)]].map(async ([key, p]): Promise<[keyof Result, unknown]> => [key as keyof Result, await p])
          : [["usage", api<ApiRows<Usage>>(`${prefix}/equipment-assets/${assetId}/usage`)]].map(async ([key, p]): Promise<[keyof Result, unknown]> => [key as keyof Result, await p]);
    Promise.all(requests).then(pairs => { if (alive) setResult(Object.fromEntries(pairs) as Result); })
      .catch(e => { if (alive) setError(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (alive) setBusy(false); });
    return () => { alive = false; };
  }, [project, tab, assetId, scheduleId, reload]);
  const scopedAllocations = (result.allocations?.items || []).filter(a => a.resource_type === "Equipment");
  return <section style={surface}>
    <h3 style={{ marginTop: 0 }}>{tab}</h3>
    <p style={{ color: "#52657d" }}>Read-only authoritative operational records. Planning owns bookings; Equipment owns custody and usage. Values are not certified progress or Finance postings.</p>
    {tab === "Allocations" ? <label>Planning schedule ID <input type="number" min="1" step="1" value={scheduleId} onChange={e => setScheduleId(e.target.value)} placeholder="Enter existing schedule ID" /></label>
      : <label>Equipment <select value={assetId} onChange={e => setAssetId(Number(e.target.value))}><option value={0}>Select equipment</option>{assets.map(a => <option value={a.id} key={a.id}>{a.asset_code} — {a.name}</option>)}</select></label>}
    <button type="button" disabled={busy} style={{ marginLeft: 10 }} onClick={() => setReload(n => n + 1)}>Refresh</button>
    {busy && <p role="status">Loading operational records…</p>}
    {error && <p role="alert" style={{ color: "#b42318" }}>{error}</p>}
    {tab === "Availability" && selected && result.compliance && <>
      <p><strong>Operating condition:</strong> {str(selected.operational_condition)}. <strong>Register status:</strong> {selected.status}.</p>
      <p><strong>Compliance evidence:</strong> {result.compliance.compliance_eligible ? "Eligible by internal compliance rules" : "Blocked or not cleared"}{result.compliance.reason ? ` — ${result.compliance.reason}` : ""}</p>
      <p><strong>Active safety holds:</strong> {(result.compliance.holds || []).filter(h => h.status !== "Released").length}</p>
      <p style={{ color: "#52657d" }}>This does not certify availability: bookings, maintenance, operator eligibility, and real-time holds require a server-side combined availability decision.</p>
    </>}
    {tab === "Allocations" && result.allocations && <>
      <p>Showing Equipment reservations in Planning schedule #{scheduleId}. Booking statuses come from Planning; overlap and operational eligibility must be enforced by the backend.</p>
      <GridTable headers={["Allocation", "Equipment ref", "Activity", "Start", "End", "Status"]} rows={scopedAllocations.map(a => [a.id, a.resource_ref, str(a.activity_id), a.starts_at, a.ends_at, a.status])} />
    </>}
    {tab === "Custody" && result.custody && <>
      <p><strong>Custody quantity available:</strong> {str(result.custody.available_quantity)}. This is not Stores stock.</p>
      <GridTable headers={["Event", "Action", "Quantity", "Custodian", "Allocation", "Location", "Recorded"]} rows={(result.custody.items || []).map(c => [c.id, c.action, c.quantity, str(c.custodian_user_id), str(c.allocation_id), str(c.location), str(c.recorded_at)])} />
    </>}
    {tab === "Usage" && result.usage && <>
      <p>Showing a maximum of {result.usage.limit ?? 200} usage records. Usage evidence is not accepted construction progress.</p>
      <GridTable headers={["Record", "Allocation", "Start", "End", "Operating h", "Idle h", "Breakdown h", "Maintenance h", "Meter end", "Fuel L"]} rows={(result.usage.items || []).map(u => [u.id, u.allocation_id, u.starts_at, u.ends_at, u.operating_hours, u.idle_hours, u.breakdown_hours, u.maintenance_hours, str(u.meter_end), str(u.fuel_liters)])} />
    </>}
    {tab !== "Allocations" && !assetId && <p>Select an equipment asset to see its project-scoped records.</p>}
    {tab === "Allocations" && (!/^\d+$/.test(scheduleId) || Number(scheduleId) <= 0) && <p>Enter an existing Planning schedule ID to load reservations.</p>}
  </section>;
}
