import { useEffect, useState, type ChangeEvent } from "react";
import { api, downloadFile, postForm } from "./api";

type Evidence = {id:number;file_name:string;content_type:string;size:number;sha256:string};
const allowed = ["application/pdf", "image/jpeg", "image/png", "text/plain"];
/** Private evidence links: all reads/downloads use session-based, scope-checked APIs. */
export function StoresEvidence({basePath,canUpload=true}:{basePath:string;canUpload?:boolean}) {
  const [items,setItems]=useState<Evidence[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [updated,setUpdated]=useState(0);
  useEffect(()=>{let active=true;setItems([]);setError("");
    void api<Evidence[]>(`${basePath}/evidence`).then(rows=>{if(active)setItems(rows)}).catch(e=>{if(active)setError((e as Error).message)});
    return ()=>{active=false};
  },[basePath,updated]);
  async function upload(event:ChangeEvent<HTMLInputElement>) {
    const file=event.target.files?.[0]; event.target.value=""; if(!file || busy)return;
    if(!allowed.includes(file.type)){setError("Choose a PDF, PNG, JPEG or text document.");return;}
    setBusy(true);setError("");
    try {const payload=new FormData();payload.append("upload",file);
      await postForm(`${basePath}/evidence`,payload);setUpdated(n=>n+1);
    }catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  return <div style={{display:"grid",gap:8,marginTop:8}}>
    {error&&<p role="alert" className="error">{error}</p>}
    {items.map(f=><div key={f.id} style={{display:"flex",alignItems:"center",gap:8,flexWrap:"wrap"}}>
      <span>{f.file_name} ({Math.ceil(f.size/1024)} KB)</span>
      <button type="button" onClick={()=>void downloadFile(`${basePath}/evidence/${f.id}/download`,f.file_name).catch(e=>setError((e as Error).message))}>Download</button>
    </div>)}
    {!items.length&&<span className="muted">No evidence attached.</span>}
    {canUpload&&<label>Attach certificate, delivery challan or supporting evidence
      <input type="file" accept=".pdf,.png,.jpg,.jpeg,.txt" disabled={busy} onChange={e=>void upload(e)}/>
    </label>}
    <small className="muted">Private project/company-scoped documents. Upload limits are enforced by the server.</small>
  </div>;
}
