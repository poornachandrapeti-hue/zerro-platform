import { useEffect, useState } from "react";
import { api } from "../api";

type Project = { project_id: number; code: string; name: string };
type Schedule = { id: number; version: string; activity_count: number };
type Activity = { activity_code: string; activity_name: string; activity_type: string; planned_start: string | null; planned_finish: string | null; discipline_id: number | null };

/** Partner-only read path. Do not replace with the internal PlanningHome component. */
export function PartnerPlanning({ initialProjectId }: { initialProjectId: number | null }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [pid, setPid] = useState<number | null>(null);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [scheduleId, setScheduleId] = useState<number | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [commitment, setCommitment] = useState("Committed");
  const [note, setNote] = useState("");
  const [chosenActivity, setChosenActivity] = useState("");
  const [feedback, setFeedback] = useState("");
  const [commitments, setCommitments] = useState<{id:number;activity_code:string;commitment:string;status:string;review_note:string}[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api<{items: Project[]}>("/partner/projects").then((result) => {
      if (!active) return;
      setProjects(result.items);
      setPid((result.items.find(p => p.project_id === initialProjectId) || result.items[0])?.project_id ?? null);
    }).catch((err: Error) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [initialProjectId]);

  useEffect(() => {
    setSchedules([]); setScheduleId(null); setActivities([]); setError("");
    if (!pid) return;
    let active = true;
    setLoading(true);
    api<{schedules: Schedule[]}>(`/projects/${pid}/partner-planning/schedules`)
      .then(result => { if (active) { setSchedules(result.schedules); setScheduleId(result.schedules[0]?.id ?? null); } })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [pid]);

  useEffect(() => {
    setActivities([]);
    if (!pid || !scheduleId) return;
    let active = true;
    setLoading(true);
    api<{activities: Activity[]}>(`/projects/${pid}/partner-planning/schedules/${scheduleId}/activities`)
      .then(result => { if (active) { setActivities(result.activities); setChosenActivity(result.activities[0]?.activity_code ?? ""); setError(""); } })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [pid, scheduleId]);

  async function sendCommitment() {
    if (!pid || !scheduleId || !chosenActivity) return;
    const item = activities.find(a => a.activity_code === chosenActivity);
    if (!item) return;
    try {
      await api(`/projects/${pid}/partner-planning/schedules/${scheduleId}/activities/${encodeURIComponent(item.activity_code)}/commitments`, "POST", {commitment,note});
      setFeedback("Commitment submitted for internal review."); setNote("");
      const r = await api<{items: typeof commitments}>(`/projects/${pid}/partner-planning/commitments`); setCommitments(r.items);
    } catch(e) { setFeedback((e as Error).message); }
  }
  useEffect(() => {
    setCommitments([]); setChosenActivity("");
    if (!pid) return;
    let active=true;
    api<{items: typeof commitments}>(`/projects/${pid}/partner-planning/commitments`).then(r=>{if(active)setCommitments(r.items)}).catch(()=>{});
    return ()=>{active=false};
  },[pid]);

  return <section className="panel">
    <h2>Partner Planning</h2>
    <p className="muted">Published schedule activities assigned to your authorized company and disciplines. Internal forecasts, commercial values and other companies' work are not available here.</p>
    {projects.length > 1 && <label>Project <select value={pid ?? ""} onChange={e => setPid(Number(e.target.value))}>{projects.map(p => <option key={p.project_id} value={p.project_id}>{p.code} — {p.name}</option>)}</select></label>}
    {schedules.length > 0 && <label>Approved schedule <select value={scheduleId ?? ""} onChange={e => setScheduleId(Number(e.target.value))}>{schedules.map(s => <option key={s.id} value={s.id}>Revision {s.version} ({s.activity_count} assigned activities)</option>)}</select></label>}
    {error && <p role="alert" className="error">{error}</p>}
    {loading && <p className="muted">Loading authorized Planning records…</p>}
    {!loading && !error && !projects.length && <p className="muted">No projects assigned.</p>}
    {!loading && !error && pid && !schedules.length && <p className="muted">No published schedules are available to your company.</p>}
    {!loading && !error && scheduleId && !activities.length && <p className="muted">No activities in this published schedule are available to your role.</p>}
    {!!activities.length && <div style={{marginTop:16,display:"grid",gap:8}}>
      <h3>Submit activity commitment</h3>
      <label>Activity <select value={chosenActivity} onChange={e=>setChosenActivity(e.target.value)}>{activities.map(a=><option key={a.activity_code} value={a.activity_code}>{a.activity_code} — {a.activity_name}</option>)}</select></label>
      <label>Response <select value={commitment} onChange={e=>setCommitment(e.target.value)}><option value="Committed">Committed</option><option value="AtRisk">At risk</option><option value="Declined">Declined</option></select></label>
      <label>Reason / note <textarea value={note} onChange={e=>setNote(e.target.value)} maxLength={1000}/></label>
      <button disabled={!chosenActivity || (commitment!=="Committed" && !note.trim())} onClick={sendCommitment}>Submit for review</button>
      {feedback && <p role="status">{feedback}</p>}
      <h3>My company's submissions</h3>
      {commitments.map(c=><p key={c.id}>{c.activity_code} — {c.commitment} — {c.status}{c.review_note ? ` (${c.review_note})`:""}</p>)}
    </div>}
    {!!activities.length && <div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Code</th><th>Activity</th><th>Type</th><th>Planned start</th><th>Planned finish</th></tr></thead><tbody>{activities.map(a => <tr key={a.activity_code}><td>{a.activity_code}</td><td>{a.activity_name}</td><td>{a.activity_type}</td><td>{a.planned_start || "—"}</td><td>{a.planned_finish || "—"}</td></tr>)}</tbody></table></div>}
  </section>;
}
