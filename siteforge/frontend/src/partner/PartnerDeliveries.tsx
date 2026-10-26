import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { StoresEvidence } from "../storesEvidence";

type Project = { project_id: number; name: string; code: string };
type PurchaseOrder = { purchase_order_id: number; number: string; lines: { purchase_order_line_id: number; quantity: string }[] };
type Notice = { id: number; number: string; purchase_order_id: number; expected_date: string; delivery_note: string; status: string; lines: {purchase_order_line_id:number; quantity:string}[] };

export function PartnerDeliveries({initialProjectId}: {initialProjectId: number | null}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [pid, setPid] = useState<number | null>(null);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [selectedNotice,setSelectedNotice]=useState<number|null>(null);
  const [po, setPo] = useState(0);
  const [number, setNumber] = useState("");
  const [expected, setExpected] = useState(new Date().toISOString().slice(0,10));
  const [delivery, setDelivery] = useState("");
  const [quantities, setQuantities] = useState<Record<number,string>>({});
  const [error, setError] = useState(""); const [message,setMessage] = useState(""); const [busy,setBusy] = useState(false);
  useEffect(() => { void api<{items:Project[]}>("/partner/projects").then(data => {
    setProjects(data.items);
    const desired = data.items.find(x=>x.project_id===initialProjectId) || data.items[0];
    setPid(desired?.project_id ?? null);
  }).catch(e=>setError((e as Error).message)); }, [initialProjectId]);
  async function load(project: number) {
    setError("");
    try {
      const [source, existing] = await Promise.all([
        api<PurchaseOrder[]>(`/partner/projects/${project}/stores/notice-sources`),
        api<Notice[]>(`/partner/projects/${project}/stores/delivery-notices`)
      ]);
      setOrders(source); setNotices(existing); setPo(old => source.some(s=>s.purchase_order_id===old)?old:(source[0]?.purchase_order_id ?? 0));
    } catch(e) { setError((e as Error).message); setOrders([]);setNotices([]); }
  }
  useEffect(()=>{setOrders([]);setNotices([]);setPo(0);setQuantities({});if(pid)void load(pid);},[pid]);
  async function submit(event:FormEvent) {
    event.preventDefault(); if(!pid || !po || busy)return;
    const source=orders.find(x=>x.purchase_order_id===po);
    const lines=(source?.lines||[]).filter(x=>Number(quantities[x.purchase_order_line_id]||0)>0).map(x=>({purchase_order_line_id:x.purchase_order_line_id,quantity:quantities[x.purchase_order_line_id]}));
    if(!lines.length){setError("Enter at least one positive quantity.");return;}
    if(source?.lines.some(x=>Number(quantities[x.purchase_order_line_id]||0)>Number(x.quantity))){setError("Notice quantity cannot exceed the original PO quantity.");return;}
    setBusy(true);setError("");setMessage("");
    try {
      await api(`/partner/projects/${pid}/stores/delivery-notices`,"POST",{number,purchase_order_id:po,expected_date:expected,delivery_note:delivery,lines});
      setNumber("");setDelivery("");setQuantities({});setMessage("Delivery notice submitted to Stores. This does not post a GRN or stock.");
      await load(pid);
    } catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  return <section className="panel"><h2>My delivery notices</h2>
    <p className="muted">Notify ZerroBuild Stores about an expected shipment against a purchase order issued to your company. A notice is not a goods receipt or material acceptance.</p>
    {projects.length>1&&<label>Project <select value={pid??""} onChange={e=>setPid(Number(e.target.value))}>{projects.map(x=><option key={x.project_id} value={x.project_id}>{x.code} — {x.name}</option>)}</select></label>}
    {error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status">{message}</p>}
    {!projects.length&&<p className="muted">No authorized partner projects available.</p>}
    <div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>ASN</th><th>Purchase order</th><th>Expected</th><th>Delivery note</th><th>Status</th><th>Documents</th></tr></thead><tbody>
      {notices.map(n=><tr key={n.id}><td>{n.number}</td><td>{orders.find(o=>o.purchase_order_id===n.purchase_order_id)?.number || n.purchase_order_id}</td><td>{n.expected_date}</td><td>{n.delivery_note||"—"}</td><td>{n.status}</td><td><button type="button" onClick={()=>setSelectedNotice(n.id)}>Evidence</button></td></tr>)}
    </tbody></table></div>{pid&&selectedNotice&&<div className="panel" style={{marginTop:12}}><h3>ASN evidence</h3><button type="button" onClick={()=>setSelectedNotice(null)}>Close</button><StoresEvidence basePath={`/partner/projects/${pid}/stores/delivery-notices/${selectedNotice}`}/></div>}{pid&&!notices.length&&<p className="muted">No delivery notices yet.</p>}
    {pid&&<form onSubmit={submit} style={{marginTop:24,display:"grid",gap:12,maxWidth:850}}>
      <h3>Submit advance shipping notice</h3>
      <label>ASN reference <input required maxLength={80} value={number} onChange={e=>setNumber(e.target.value)}/></label>
      <label>Expected arrival <input type="date" required value={expected} onChange={e=>setExpected(e.target.value)}/></label>
      <label>Purchase order <select required value={po} onChange={e=>{setPo(Number(e.target.value));setQuantities({});}}><option value={0}>Select issued PO</option>{orders.map(o=><option key={o.purchase_order_id} value={o.purchase_order_id}>{o.number}</option>)}</select></label>
      <label>Delivery note / challan reference <input maxLength={160} value={delivery} onChange={e=>setDelivery(e.target.value)}/></label>
      <div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>PO line</th><th>Ordered qty</th><th>Expected shipment qty</th></tr></thead><tbody>{(orders.find(o=>o.purchase_order_id===po)?.lines||[]).map((l,i)=><tr key={l.purchase_order_line_id}><td>Line {i+1}</td><td>{l.quantity}</td><td><input type="number" min="0" max={l.quantity} step="0.001" value={quantities[l.purchase_order_line_id]||""} onChange={e=>setQuantities(q=>({...q,[l.purchase_order_line_id]:e.target.value}))}/></td></tr>)}</tbody></table></div>
      <button className="btn" type="submit" disabled={!po||busy}>{busy?"Submitting...":"Submit ASN"}</button>
      {!orders.length&&<p className="muted">No eligible purchase orders issued to your company.</p>}
    </form>}
  </section>;
}
