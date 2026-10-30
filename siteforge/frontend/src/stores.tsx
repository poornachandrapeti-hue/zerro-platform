import { useEffect, useState, type FormEvent } from "react";
import { Warehouse, MapPinned, RefreshCw, ClipboardList, Truck, PackagePlus, ListChecks, PackageCheck, Undo2, ArrowLeftRight, CalendarClock, Gauge, LayoutDashboard, HardHat, Scale, type LucideIcon } from "lucide-react";
import { api } from "./api";
import { StoresEvidence } from "./storesEvidence";
import type { Session } from "./types";

type PreservationPlan = {id:number;receipt_lot_id:number;lot_code:string;warehouse_id:number;condition:string;status:string;next_due_date:string;expiry_date:string|null;version:number;instructions:string;frequency_days:number;responsible_user_id:number;last_checked_at:string|null;stock_readiness:string};
type PreservationCheck = {id:number;condition:string;findings:string;evidence:string;checked_by:number;checked_at:string};
type Wh = { id: number; code: string; name: string; location: string; officer: string; active: boolean };
type Loc = { id: number; warehouse_id: number; parent_id: number | null; code: string; name: string; location_type: string; restrictions: string; active: boolean; version: number };
type Receipt = { id: number; number: string; status: string; purchase_order_number: string; vendor: string; receipt_date: string; warehouse: string; lines: {quantity: string; accepted: string; unit: string; item_code: string}[] };
type Notice = {id:number;number:string;purchase_order_id:number;expected_date:string;delivery_note:string;status:string;lines:{purchase_order_line_id:number;quantity:string}[]};
type Intake = {id:number;number:string;intake_type:string;status:string;reason:string;lines:{item_id:number;quantity:string;unit:string}[]};
type IntakeOptions = {warehouses:{id:number;code:string;name:string}[];companies:{id:number;name:string}[];items:{id:number;code:string;description:string;base_unit:string;tracking_required:boolean}[]};
type IntakeEntry = {item_id:number;quantity:string;batch_or_heat:string};
type MaterialRequest = {id:number;request_key:string;requirement_line_id:number|null;item_id:number;quantity:string;unit:string;required_date:string;work_package_id:number|null;planning_wbs_id:number|null;status:string;version:number;created_by:number;review_reason:string;requester_company_id:number|null;origin:"Partner"|"Internal"};
type TransferMonitor = {as_of:string;counts:Record<string,number>;record_count:number;coverage:string;aging_basis:string;physical_stock_readiness:string;records:{id:number;reference:string;status:string;receipt_overdue_proxy:boolean;age_hours_since_request:number|null;discrepancy_status:string}[]};
type TransferRecord = {id:number;reference:string;source_warehouse_id:number;destination_warehouse_id:number;item_id:number;quantity:string;dispatched_quantity:string|null;received_quantity:string|null;damaged_quantity:string|null;purpose:string;status:string;version:number;discrepancy_note:string;discrepancy_status:string;discrepancy_resolution:string;inventory_posted:boolean};
type MaterialReturn = {id:number;handover_id:number;requested_quantity:string;received_quantity:string|null;condition:string;reason:string;status:string;version:number;receipt_evidence:string|null;qa_decision:string|null;qa_evidence:string|null;location_id:number|null;placement_evidence:string|null;stock_posted:boolean;stock_posting_id:number|null};
type MaterialHandover = {id:number;handover_reference:string;quantity:string;received_quantity:string|null;damaged_quantity:string|null;status:string;version:number;discrepancy_note:string;resolution_note:string};
type MaterialDemand = {request_id:number;item_id:number;unit:string;approved_demand:string;unallocated_demand:string;note:string};
type LotOption = {id:number;batch_number?:string|null;heat_number?:string|null;serial_number?:string|null;goods_receipt_line_id:number};
type AllocationOverview = {request_id:number;approved_quantity:string;allocated_quantity:string;active_reserved_quantity:string;consumed_by_issue:string;released_quantity:string;unallocated_quantity:string;reservations:{id:number;lot_id:number;allocated_quantity:string;remaining_quantity:string;status:string}[]};
type Phase5Overview = {as_of:string; counts:Record<string,number>;record_count:number;coverage:string;inventory_verified:boolean;records:{handover_id:number;handover_reference:string;work_package_id:number|null;material_request_id:number;handover_status:string;dispatched_quantity:string;return_status:string|null;return_stock_posting_id:number|null;acknowledgment_overdue:boolean;dispatched_at:string|null}[]};
type MaterialBalanceRow = {handover_id:number;work_package_id:number|null;item_id:number;unit:string;issued_quantity:string;ledger_posted_return_quantity:string;ledger_outstanding_quantity:string;pending_custody_return_quantity:string;verified_consumed_quantity:string;verified_installed_quantity:string;pending_qa_consumed_quantity:string;pending_qa_installed_quantity:string;rejected_evidence_quantity:string;unallocated_outstanding_quantity:string;physical_inventory_verified:boolean;coverage:string};
type MaterialBalanceResponse = {records:MaterialBalanceRow[];coverage:string;inventory_verified:boolean;as_of:string};
type MaterialUsage = {id:number;handover_id:number;work_package_id:number;item_id:number;unit:string;quantity:string;usage_type:"Consumed"|"Installed";evidence_key:string;evidence:string;status:string;submitted_by:number;version:number;verification_note:string};
type Source = { purchase_order_id: number; number: string; vendor: string; lines: {purchase_order_line_id: number; item_code: string; remaining: string; unit: string}[] };
function slug(value:string){return value.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'')}
function Pill({value}:{value:string}){return <span className={`state-pill state-${slug(value)}`}>{value}</span>}
export function StoresHome({session, initialProjectId}: {session: Session; initialProjectId?: number | null}) {
  const [pid, setPid] = useState<number>(initialProjectId || session.memberships.find(m=>m.project_id)?.project_id || 0);
  const [warehouses, setWarehouses] = useState<Wh[]>([]);
  const [locations, setLocations] = useState<Loc[]>([]);
  const [warehouseId, setWarehouseId] = useState(0);
  const [code, setCode] = useState(""); const [name, setName] = useState("");
  const [parentId, setParentId] = useState(0); const [kind, setKind] = useState("Bin");
  const [error, setError] = useState(""); const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [poId, setPoId] = useState(0);
  const [receiptNo, setReceiptNo] = useState("");
  const [deliveryNote, setDeliveryNote] = useState("");
  const [receiptDate, setReceiptDate] = useState(new Date().toISOString().slice(0,10));
  const [quantities, setQuantities] = useState<Record<number,string>>({});
  const [tab, setTab] = useState<"warehouses"|"receipts"|"notices"|"intakes"|"requests"|"handovers"|"returns"|"operations"|"usage"|"balances"|"transfers"|"preservation"|"phase7">("warehouses");
  const [notices,setNotices] = useState<Notice[]>([]);
  const [intakes,setIntakes] = useState<Intake[]>([]);
  const [evidenceSelection,setEvidenceSelection]=useState<{kind:"notice"|"intake"|"receipt";id:number}|null>(null);
  const [noticeNo,setNoticeNo] = useState("");
  const [expectedDate,setExpectedDate] = useState(new Date().toISOString().slice(0,10));
  const [noticePo,setNoticePo] = useState(0);
  const [noticeQuantities,setNoticeQuantities] = useState<Record<number,string>>({});
  const [noticeDelivery,setNoticeDelivery] = useState("");
  const [materialRequests,setMaterialRequests] = useState<MaterialRequest[]>([]);
  const [materialDemand,setMaterialDemand] = useState<MaterialDemand[]>([]);
  const [operations,setOperations]=useState<Phase5Overview|null>(null);
  const [materialBalance,setMaterialBalance]=useState<MaterialBalanceResponse|null>(null);
  const [balanceWorkPackage,setBalanceWorkPackage]=useState('');
  const [balanceLoading,setBalanceLoading]=useState(false);
  const [balanceError,setBalanceError]=useState('');
  const [usageRecords,setUsageRecords]=useState<MaterialUsage[]>([]);
  const [qaUsageRecords,setQaUsageRecords]=useState<MaterialUsage[]>([]);
  const [usageHandover,setUsageHandover]=useState('');
  const [usageWorkPackage,setUsageWorkPackage]=useState('');
  const [usageKind,setUsageKind]=useState<'Consumed'|'Installed'>('Consumed');
  const [usageQuantity,setUsageQuantity]=useState('');
  const [usageKey,setUsageKey]=useState('');
  const [usageEvidence,setUsageEvidence]=useState('');
  const [usageReviewNotes,setUsageReviewNotes]=useState<Record<number,string>>({});
  const [usageLoadError,setUsageLoadError]=useState('');
  const [handovers,setHandovers]=useState<MaterialHandover[]>([]);
  const [returns,setReturns]=useState<MaterialReturn[]>([]);
  const [phase7Monitor,setPhase7Monitor]=useState<{as_of:string;coverage:string;counts:Record<string,number|null>;preservation:{id:number;status:string;owner_id:number;next_due_date:string}[];cycle_counts:{id:number;reference:string;status:string}[];adjustments:{id:number;reference:string;status:string}[];scrap_cases:{id:number;reference:string;status:string}[];limitations:string[]}|null>(null);
  const [phase7Error,setPhase7Error]=useState("");
  const [phase7Loading,setPhase7Loading]=useState(false);
  async function loadPhase7Monitor(){
    if(!pid)return;
    setPhase7Loading(true);setPhase7Error("");setPhase7Monitor(null);
    try { setPhase7Monitor(await api(`/projects/${pid}/stores/phase7/operations-monitor`)); }
    catch(e){setPhase7Error(e instanceof Error?e.message:String(e));}
    finally{setPhase7Loading(false);}
  }
  const [preservationPlans,setPreservationPlans]=useState<PreservationPlan[]>([]);
  const [preservationLoading,setPreservationLoading]=useState(false);
  const [preservationError,setPreservationError]=useState('');
  const [preservationLot,setPreservationLot]=useState('');
  const [preservationInstructions,setPreservationInstructions]=useState('');
  const [preservationFrequency,setPreservationFrequency]=useState(30);
  const [preservationDue,setPreservationDue]=useState('');
  const [preservationOwner,setPreservationOwner]=useState('');
  const [preservationNotes,setPreservationNotes]=useState<Record<number,string>>({});
  const [preservationEvidence,setPreservationEvidence]=useState<Record<number,string>>({});
  const [preservationCondition,setPreservationCondition]=useState<Record<number,string>>({});
  const [preservationHistory,setPreservationHistory]=useState<Record<number,PreservationCheck[]>>({});
  const [transfers,setTransfers]=useState<TransferRecord[]>([]);
  const [transferMonitor,setTransferMonitor]=useState<TransferMonitor|null>(null);
  const [transferMonitorError,setTransferMonitorError]=useState('');
  const [transferReference,setTransferReference]=useState('');
  const [transferSource,setTransferSource]=useState(0);
  const [transferDestination,setTransferDestination]=useState(0);
  const [transferItem,setTransferItem]=useState(0);
  const [transferQuantity,setTransferQuantity]=useState('');
  const [transferPurpose,setTransferPurpose]=useState('');
  const [transferNotes,setTransferNotes]=useState<Record<number,string>>({});
  const [transferReceived,setTransferReceived]=useState<Record<number,string>>({});
  const [transferDamaged,setTransferDamaged]=useState<Record<number,string>>({});
  const [transferPostingChecks,setTransferPostingChecks]=useState<Record<number,{blockers:string[];eligible_for_posting:boolean}>>({});

  const [returnLocation,setReturnLocation]=useState<Record<number,string>>({});
  const [returnPostingReference,setReturnPostingReference]=useState<Record<number,string>>({});
  const [returnExceptions,setReturnExceptions]=useState<{counts:Record<string,number>;total_records:number;physical_stock_readiness:string;coverage:string}|null>(null);
  const [returnWorkload,setReturnWorkload]=useState<{active_tasks:number;overdue_tasks:number;blocked_tasks:number;unassigned_exceptions:number;by_owner_id:Record<string,number>;coverage:string}|null>(null);
  const [returnReconciliation,setReturnReconciliation]=useState<{return_id:number;reconciliation_state:string}[]>([]);
  const [returnEvidence,setReturnEvidence]=useState<Record<number,string>>({});
  const [returnQuantities,setReturnQuantities]=useState<Record<number,string>>({});
  const [resolutionNotes,setResolutionNotes]=useState<Record<number,string>>({});
  const [lots,setLots] = useState<LotOption[]>([]);
  const [selectedAllocRequest,setSelectedAllocRequest] = useState<number|null>(null);
  const [allocationOverview,setAllocationOverview] = useState<AllocationOverview|null>(null);
  const [allocationLot,setAllocationLot] = useState(0);
  const [allocationQuantity,setAllocationQuantity] = useState("");
  const [allocationKey,setAllocationKey] = useState("");
  const [requestQueueOnly,setRequestQueueOnly] = useState(false);
  const [requestKey,setRequestKey] = useState("");
  const [requestRequirementLine,setRequestRequirementLine] = useState("");
  const [requestItem,setRequestItem] = useState(0);
  const [requestQty,setRequestQty] = useState("");
  const [requestDate,setRequestDate] = useState(new Date().toISOString().slice(0,10));
  const [requestWbs,setRequestWbs] = useState("");
  const [requestWorkPackage,setRequestWorkPackage] = useState("");
  const [requestReason,setRequestReason] = useState("");
  const [requestReviewReasons,setRequestReviewReasons] = useState<Record<number,string>>({});
  const [intakeOptions,setIntakeOptions] = useState<IntakeOptions>({warehouses:[],companies:[],items:[]});
  const [intakeNumber,setIntakeNumber] = useState("");
  const [intakeType,setIntakeType] = useState("Free Issue");
  const [intakeWarehouse,setIntakeWarehouse] = useState(0);
  const [intakeOwner,setIntakeOwner] = useState(0);
  const [intakeSource,setIntakeSource] = useState(0);
  const [intakeReason,setIntakeReason] = useState("");
  const [intakeLines,setIntakeLines] = useState<IntakeEntry[]>([{item_id:0,quantity:"",batch_or_heat:""}]);
  async function loadPreservation(){
    if(!pid)return;
    setPreservationLoading(true);setPreservationError('');
    try{const result=await api<{items:PreservationPlan[]}>(`/projects/${pid}/stores/preservation/plans`);setPreservationPlans(result.items);}
    catch(e){setPreservationError((e as Error).message);}finally{setPreservationLoading(false);}
  }
  async function createPreservation(e:FormEvent){
    e.preventDefault();setPreservationError('');
    try{await api(`/projects/${pid}/stores/preservation/plans`,'POST',{
      receipt_lot_id:Number(preservationLot),instructions:preservationInstructions,
      frequency_days:preservationFrequency,next_due_date:preservationDue,responsible_user_id:Number(preservationOwner)});
      setPreservationLot('');setPreservationInstructions('');await loadPreservation();}
    catch(e){setPreservationError((e as Error).message);}
  }
  async function inspectPreservation(plan:PreservationPlan){
    setPreservationError('');
    try{await api(`/projects/${pid}/stores/preservation/plans/${plan.id}/checks`,'POST',{
      version:plan.version, request_key:`pres-${plan.id}-${Date.now()}`,
      condition:preservationCondition[plan.id]||'Good',findings:preservationNotes[plan.id]||'',
      evidence:preservationEvidence[plan.id]||''});await loadPreservation();}
    catch(e){setPreservationError((e as Error).message);}
  }
  async function loadPreservationHistory(plan:PreservationPlan){
    try{const r=await api<{items:PreservationCheck[]}>(`/projects/${pid}/stores/preservation/plans/${plan.id}/checks`);
      setPreservationHistory(old=>({...old,[plan.id]:r.items}));}
    catch(e){setPreservationError((e as Error).message);}
  }
  async function loadTransfers(){
    if(!pid)return;
    try {const result=await api<{records:TransferRecord[]}>(`/projects/${pid}/stores/material-transfers`);setTransfers(result.records);}
    catch(e){setError((e as Error).message);}
  }
  async function loadTransferMonitor(){
    if(!pid)return;
    setTransferMonitor(null);setTransferMonitorError('');
    try {const result=await api<TransferMonitor>(`/projects/${pid}/stores/material-transfers/monitor`);setTransferMonitor(result);}
    catch(e){setTransferMonitorError((e as Error).message);}
  }
  async function checkTransferPosting(id:number){
    if(!pid)return;
    try {
      const result=await api<{blockers:string[];eligible_for_posting:boolean}>(`/projects/${pid}/stores/material-transfers/${id}/posting-readiness`);
      setTransferPostingChecks(v=>({...v,[id]:result}));
    } catch(e){setMessage(String(e));}
  }

  async function submitTransfer(e:FormEvent){
    e.preventDefault();setBusy(true);setError('');
    try{await api(`/projects/${pid}/stores/material-transfers`,'POST',{
      reference:transferReference,source_warehouse_id:transferSource,destination_warehouse_id:transferDestination,
      item_id:transferItem,quantity:transferQuantity,purpose:transferPurpose});
      setTransferReference('');setTransferQuantity('');setTransferPurpose('');setMessage('Transfer custody request created. No stock was moved.');await loadTransfers();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function advanceTransfer(row:TransferRecord,action:'decision'|'dispatch'|'receive'|'resolve-discrepancy',approval?:boolean,decision?:string){
    setBusy(true);setError('');
    const evidence=(transferNotes[row.id]||'').trim();
    if(evidence.length<3){setError('Enter at least 3 characters of evidence.');setBusy(false);return;}
    let body:Record<string,unknown>={version:row.version,evidence};
    if(action==='decision')body={...body,approve:approval};
    if(action==='dispatch')body={...body,quantity:row.quantity};
    if(action==='receive')body={...body,received_quantity:transferReceived[row.id]??row.dispatched_quantity,damaged_quantity:transferDamaged[row.id]??'0',discrepancy_note:evidence};
    if(action==='resolve-discrepancy')body={...body,action:decision};
    try{await api(`/projects/${pid}/stores/material-transfers/${row.id}/${action}`,'POST',body);
      setMessage(`Transfer ${row.reference}: ${action} recorded. Stock balances remain unverified.`);await loadTransfers();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function loadUsages(){
    if(!pid)return;
    const filter=usageWorkPackage.trim()?`?work_package_id=${encodeURIComponent(usageWorkPackage.trim())}`:'';
    const [mine,queue]=await Promise.allSettled([
      api<{records:MaterialUsage[]}>(`/projects/${pid}/stores/phase5/material-usages${filter}`),
      api<{records:MaterialUsage[]}>(`/projects/${pid}/stores/phase5/material-usages/qa-queue`)
    ]);
    setUsageRecords(mine.status==='fulfilled'?mine.value.records:[]);
    const qa=queue.status==='fulfilled'?queue.value.records:[];
    setQaUsageRecords(usageWorkPackage.trim()?qa.filter(r=>String(r.work_package_id)===usageWorkPackage.trim()):qa);
    setUsageLoadError(mine.status==='rejected'&&queue.status==='rejected'?'Usage evidence unavailable or access denied for this project.':'');
  }
  async function submitMaterialUsage(e:FormEvent){
    e.preventDefault();if(busy)return;
    const handover_id=Number(usageHandover), quantity=Number(usageQuantity);
    if(!Number.isInteger(handover_id)||handover_id<=0||!Number.isFinite(quantity)||quantity<=0||!usageKey.trim()||usageEvidence.trim().length<5){setError('Enter a valid handover, positive quantity, evidence key and evidence (5+ characters).');return;}
    setBusy(true);setError('');setMessage('');
    try{
      await api(`/projects/${pid}/stores/phase5/material-usages`,'POST',{handover_id,usage_type:usageKind,quantity:usageQuantity,evidence_key:usageKey.trim(),evidence:usageEvidence.trim()});
      setMessage('Construction material usage submitted for independent QA review. No inventory or progress posted.');setUsageEvidence('');setUsageKey('');setUsageQuantity('');await loadUsages();
    }catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  async function reviewMaterialUsage(row:MaterialUsage,decision:'Verified'|'Rejected'){
    const note=(usageReviewNotes[row.id]||'').trim();if(note.length<5){setError('QA verification note must contain at least 5 characters.');return;}
    setBusy(true);setError('');setMessage('');
    try{await api(`/projects/${pid}/stores/phase5/material-usages/${row.id}/verify`,'POST',{version:row.version,decision,note});setMessage(`Usage #${row.id}: ${decision}. No inventory posting performed.`);await loadUsages()}
    catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  async function loadReturns(){
    if(!pid)return;
    try{
      const [data, reconciliation, places, monitoring, workload]=await Promise.all([
        api<{records:MaterialReturn[]}>(`/projects/${pid}/stores/material-returns`),
        api<{records:{return_id:number;reconciliation_state:string}[]}>(`/projects/${pid}/stores/material-returns/reconciliation`).catch(()=>({records:[]})),
        api<Loc[]>(`/projects/${pid}/stores/locations`).catch(()=>[] as Loc[]),
        api<{counts:Record<string,number>;total_records:number;physical_stock_readiness:string;coverage:string}>(`/projects/${pid}/stores/material-returns/exception-monitor`).catch(()=>null),
        api<{active_tasks:number;overdue_tasks:number;blocked_tasks:number;unassigned_exceptions:number;by_owner_id:Record<string,number>;coverage:string}>(`/projects/${pid}/stores/material-returns/exception-workload`).catch(()=>null)
      ]);
      setReturns(data.records);setReturnReconciliation(reconciliation.records);setLocations(places);setReturnExceptions(monitoring);setReturnWorkload(workload);
    }catch(e){setError((e as Error).message);setReturns([]);setReturnExceptions(null);setReturnWorkload(null)}
  }
  async function processReturn(row:MaterialReturn,action:'receive'|'qa-disposition',decision?:'Accepted'|'Rejected'|'Quarantined'){
    const evidence=(returnEvidence[row.id]||'').trim();if(evidence.length<3){setError('Receipt/QA evidence must contain at least 3 characters.');return;}
    const received=returnQuantities[row.id]||row.requested_quantity;
    if(action==='receive'&&(!Number.isFinite(Number(received))||Number(received)<=0||Number(received)>Number(row.requested_quantity))){setError('Verified receipt quantity must be positive and cannot exceed the requested quantity.');return;}
    setBusy(true);setError('');setMessage('');
    try{await api(`/projects/${pid}/stores/material-returns/${row.id}/${action}`,'POST',action==='receive'?{version:row.version,received_quantity:received,evidence}:{version:row.version,decision,evidence});setMessage(`Return ${row.id} ${action==='receive'?'received':'QA reviewed'}. This does not post inventory.`);setReturnEvidence(v=>({...v,[row.id]:''}));await loadReturns()}catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  async function placeReturn(row:MaterialReturn){
    const locationId=Number(returnLocation[row.id]);const evidence=(returnEvidence[row.id]||'').trim();
    if(!Number.isInteger(locationId)||locationId<=0||evidence.length<3){setError('Select a bin and enter placement evidence (3+ characters).');return;}
    setBusy(true);setError('');setMessage('');
    try{await api(`/projects/${pid}/stores/material-returns/${row.id}/placement`,'POST',{version:row.version,location_id:locationId,evidence});setMessage(`Return #${row.id} custody location recorded; no stock posted.`);await loadReturns()}catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  async function postReturn(row:MaterialReturn){
    const posting_number=(returnPostingReference[row.id]||'').trim();const evidence=(returnEvidence[row.id]||'').trim();
    if(!posting_number||evidence.length<3){setError('Posting reference and evidence are required.');return;}
    setBusy(true);setError('');setMessage('');
    try{await api(`/projects/${pid}/stores/material-returns/${row.id}/post-stock`,'POST',{version:row.version,posting_number,evidence});setMessage(`Return #${row.id} stock posting recorded.`);await loadReturns()}catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  async function loadMaterialBalance(){
    if(!pid)return;
    const wp=balanceWorkPackage.trim();
    if(wp && (!Number.isSafeInteger(Number(wp)) || Number(wp)<=0)) {setBalanceError('Work-package ID must be a positive integer.');setMaterialBalance(null);return;}
    setBalanceLoading(true);setBalanceError('');setMaterialBalance(null);
    try{
      const url=`/projects/${pid}/stores/phase5/work-package-material-balance${wp?`?work_package_id=${encodeURIComponent(wp)}`:''}`;
      const result=await api<MaterialBalanceResponse>(url);
      setMaterialBalance(result);
    }catch(e){setBalanceError((e as Error).message);setMaterialBalance(null)}
    finally{setBalanceLoading(false)}
  }
  async function loadOperations(){
    if(!pid)return;
    try {const result=await api<Phase5Overview>(`/projects/${pid}/stores/phase5/operations-overview`);setOperations(result)}
    catch(e){setOperations(null);setError((e as Error).message)}
  }
  async function loadHandovers(){
    try{const response=await api<{records:MaterialHandover[]}>(`/projects/${pid}/stores/material-handovers`);setHandovers(response.records)}catch(e){setHandovers([]);setError((e as Error).message)}
  }
  async function reviewHandover(row:MaterialHandover,decision:'Resolved'|'Escalated'){
    const evidence=(resolutionNotes[row.id]||'').trim();if(evidence.length<3){setError('Review evidence must contain at least 3 characters.');return;}
    setBusy(true);setError('');try{await api(`/projects/${pid}/stores/material-handovers/${row.id}/resolve`,'POST',{version:row.version,decision,evidence});setMessage(`Handover ${row.handover_reference}: ${decision}. No stock adjustment was posted.`);await loadHandovers()}catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  async function loadMaterialRequests() {
    if (!pid) return;
    try {
      const [requests, demand] = await Promise.all([
        api<MaterialRequest[]>(`/projects/${pid}/stores/material-requests`),
        api<MaterialDemand[]>(`/projects/${pid}/stores/material-requests/shortfalls`)
      ]);
      setMaterialRequests(requests); setMaterialDemand(demand);
    } catch(e) {setError((e as Error).message);}
  }
  async function createMaterialRequest(e: FormEvent) {
    e.preventDefault(); if(busy || !canRequestCreate) return;
    if(!requestWbs.trim() && !requestWorkPackage.trim()) {setError("Choose a WBS or work-package reference.");return;}
    const wbs=requestWbs.trim()?Number(requestWbs):null, wp=requestWorkPackage.trim()?Number(requestWorkPackage):null;
    if((wbs!==null && (!Number.isInteger(wbs)||wbs<=0))||(wp!==null&&(!Number.isInteger(wp)||wp<=0))){setError("WBS and work-package IDs must be positive integers.");return;}
    setBusy(true);setError("");setMessage("");
    try {
      await api(`/projects/${pid}/stores/material-requests`,"POST",{request_key:requestKey.trim(),requirement_line_id:Number(requestRequirementLine),item_id:requestItem,quantity:requestQty,required_date:requestDate,planning_wbs_id:wbs,work_package_id:wp,reason:requestReason});
      setRequestKey("");setRequestQty("");setRequestReason("");setMessage("Material request created as Draft. No stock was reserved.");
      await loadMaterialRequests();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function changeMaterialRequest(row: MaterialRequest, decision:"Submit"|"Approved"|"Rejected") {
    setBusy(true);setError("");setMessage("");
    try {
      if(decision==="Submit") await api(`/projects/${pid}/stores/material-requests/${row.id}/submit`,"POST",{});
      else {
        const reason=(requestReviewReasons[row.id]||"").trim();
        if(reason.length<3) throw new Error("Review reason must contain at least 3 characters.");
        await api(`/projects/${pid}/stores/material-requests/${row.id}/review`,"POST",{version:row.version,decision,reason});
      }
      setMessage(`Material request ${row.request_key}: ${decision}. No stock was posted.`);
      await loadMaterialRequests();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function inspectAllocations(requestId:number) {
    setSelectedAllocRequest(requestId); setAllocationOverview(null); setError("");
    try {
      const [overview,lotResponse] = await Promise.all([
        api<AllocationOverview>(`/projects/${pid}/stores/material-requests/${requestId}/allocations`),
        api<{records:LotOption[]}>(`/projects/${pid}/stores/receipt-lots`)
      ]);
      setAllocationOverview(overview); setLots(lotResponse.records); setAllocationLot(0);
    } catch(e) {setError((e as Error).message);}
  }
  async function allocateSelectedLot(e:FormEvent) {
    e.preventDefault(); if(!selectedAllocRequest||busy||!canRequestAllocate)return;
    setBusy(true);setError("");setMessage("");
    try {
      await api(`/projects/${pid}/stores/material-requests/${selectedAllocRequest}/allocate-lot`,"POST",{
        lot_id:allocationLot,quantity:allocationQuantity,allocation_key:allocationKey.trim()
      });
      setMessage("Allocation recorded against approved demand. No physical material issue occurred.");
      setAllocationQuantity("");setAllocationKey("");
      await Promise.all([inspectAllocations(selectedAllocRequest),loadMaterialRequests()]);
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function loadIntakeOptions() {
    if (!pid || !canReceive) return;
    try {setIntakeOptions(await api<IntakeOptions>(`/projects/${pid}/stores/exceptional-intake-options`));}
    catch(e){setError((e as Error).message);}
  }
  async function createIntake(e: FormEvent) {
    e.preventDefault(); if (!canReceive || busy) return;
    if (!intakeWarehouse || !intakeOwner || !intakeSource || intakeLines.some(l=>!l.item_id || !(Number(l.quantity)>0))) {
      setError("Choose warehouse, owner, source and valid material quantities."); return;
    }
    setBusy(true);setError("");setMessage("");
    try {
      await api(`/projects/${pid}/stores/exceptional-intakes`,"POST",{
        number:intakeNumber.trim(),intake_type:intakeType,warehouse_id:intakeWarehouse,
        owner_company_id:intakeOwner,source_company_id:intakeSource,reason:intakeReason,
        lines:intakeLines.map(l=>({...l,unit:intakeOptions.items.find(i=>i.id===l.item_id)?.base_unit||""}))
      });
      setIntakeNumber("");setIntakeReason("");setIntakeLines([{item_id:0,quantity:"",batch_or_heat:""}]);
      setMessage("Intake submitted for independent review. No stock movement has been posted.");
      await loadIntake();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  const [reviewNotes,setReviewNotes] = useState<Record<number,string>>({});
  async function reviewIntake(intake: Intake, decision: "Approve" | "Reject") {
    if (busy || intake.status !== "Pending Review") return;
    const note = (reviewNotes[intake.id] || "").trim();
    if (note.length < 5) {setError("A review note of at least 5 characters is required.");return;}
    setBusy(true);setError("");setMessage("");
    try {
      await api(`/projects/${pid}/stores/exceptional-intakes/${intake.id}/review`, "POST", {decision,note});
      setMessage(`Intake ${intake.number} ${decision === "Approve" ? "approved for processing" : "rejected"}. No inventory movement was posted.`);
      await loadIntake();
    } catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function loadIntake() {
    if (!pid) return;
    try {
      const [ns,ins] = await Promise.all([
        api<Notice[]>(`/projects/${pid}/stores/delivery-notices`),
        api<Intake[]>(`/projects/${pid}/stores/exceptional-intakes`)
      ]);
      setNotices(ns);setIntakes(ins);
    } catch(e) {setError((e as Error).message);}
  }
  async function createNotice(e: FormEvent) {
    e.preventDefault();if(!noticePo)return;
    const selected = sources.find(x=>x.purchase_order_id===noticePo);
    const lines=(selected?.lines||[]).filter(x=>Number(noticeQuantities[x.purchase_order_line_id]||0)>0)
      .map(x=>({purchase_order_line_id:x.purchase_order_line_id,quantity:noticeQuantities[x.purchase_order_line_id]}));
    if (!lines.length){setError("Enter at least one notice quantity.");return;}
    setBusy(true);setError("");setMessage("");
    try {
      await api(`/projects/${pid}/stores/delivery-notices`,"POST",{
        number:noticeNo,purchase_order_id:noticePo,expected_date:expectedDate,
        delivery_note:noticeDelivery,lines
      });
      setNoticeNo("");setNoticeQuantities({});setNoticeDelivery("");
      setMessage("Delivery notice submitted. This is not a posted goods receipt.");
      await loadIntake();
    } catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  const hasPerm = (permission: string) =>
    session.user.organization_admin ||
    session.memberships.some((m) => m.project_id === pid && m.permissions?.includes(permission));
  const canEdit = hasPerm("procurement.master.edit");
  const canStock = hasPerm("procurement.stock.edit");
  const canReceive = hasPerm("procurement.receipt.edit");
  const canRequestCreate = hasPerm("stores.requests.create");
  const canRequestReview = hasPerm("stores.requests.review");
  const canRequestAllocate = hasPerm("stores.requests.allocate");
  // Legacy alias: transfer / stock-post actions still use procurement.stock.edit on the API.
  const canRequest = canStock;
  async function loadReceipts() {
    if (!pid) return;
    try {
      setError("");
      const [items, eligible] = await Promise.all([
        api<Receipt[]>(`/projects/${pid}/stores/receipts`),
        api<Source[]>(`/projects/${pid}/stores/receipt-sources`)
      ]);
      setReceipts(items); setSources(eligible);
      setPoId(old => eligible.some(x=>x.purchase_order_id===old) ? old : eligible[0]?.purchase_order_id || 0);
    } catch (e) {setError((e as Error).message);}
  }
  async function postReceipt(e: FormEvent) {
    e.preventDefault(); if (!canReceive || !poId) return;
    const src = sources.find(x=>x.purchase_order_id===poId);
    const lines = (src?.lines || []).filter(x=>Number(quantities[x.purchase_order_line_id] || 0)>0)
      .map(x=>({purchase_order_line_id:x.purchase_order_line_id,quantity:quantities[x.purchase_order_line_id]}));
    if (!lines.length) {setError("Enter at least one positive receipt quantity.");return;}
    if (src?.lines.some(x=>Number(quantities[x.purchase_order_line_id]||0)>Number(x.remaining))) {
      setError("A receipt quantity exceeds its remaining PO quantity.");return;
    }
    setBusy(true);setError("");setMessage("");
    try {
      await api(`/projects/${pid}/stores/receipts`,"POST",{
        number:receiptNo, purchase_order_id:poId, receipt_date:receiptDate,
        delivery_note:deliveryNote, warehouse_id:warehouseId || null, lines
      });
      setReceiptNo("");setDeliveryNote("");setQuantities({});
      setMessage("Goods receipt posted. Material awaits separate stock/quality acceptance.");
      await loadReceipts();
    } catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  async function reload() {
    if (!pid) return;
    try {
      setError("");
      const [w, l] = await Promise.all([api<Wh[]>(`/projects/${pid}/stores/warehouses`), api<Loc[]>(`/projects/${pid}/stores/locations`)]);
      setWarehouses(w); setLocations(l);
      setWarehouseId(old => w.some(x=>x.id===old) ? old : w[0]?.id || 0);
    } catch (e) { setError((e as Error).message); }
  }
  useEffect(() => { void reload(); void loadReceipts(); void loadIntake(); void loadMaterialRequests(); }, [pid]);
  async function create(e: FormEvent) {
    e.preventDefault(); if (!warehouseId || !canEdit) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await api(`/projects/${pid}/stores/locations`, "POST", {warehouse_id: warehouseId, parent_id: parentId || null, code, name, location_type: kind, restrictions: "", active: true});
      setCode(""); setName(""); setParentId(0); setMessage("Storage location created."); await reload();
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }
  const tabs: {key: typeof tab; label: string; icon: LucideIcon; tone: string; open: () => void}[] = [
    {key:"warehouses", label:"Warehouses & Locations", icon:Warehouse, tone:"tone-swh", open:()=>setTab("warehouses")},
    {key:"receipts", label:"Goods Receipts", icon:ClipboardList, tone:"tone-sgrn", open:()=>{setTab("receipts");void loadReceipts();}},
    {key:"notices", label:"Delivery Notices", icon:Truck, tone:"tone-sasn", open:()=>{setTab("notices");void loadIntake();}},
    {key:"intakes", label:"Exceptional Intakes", icon:PackagePlus, tone:"tone-sintake", open:()=>{setTab("intakes");void loadIntake();void loadIntakeOptions();}},
    {key:"requests", label:"Material Requests", icon:ListChecks, tone:"tone-sreq", open:()=>{setTab("requests");void loadMaterialRequests();void loadIntakeOptions();}},
    {key:"handovers", label:"Material Handovers", icon:PackageCheck, tone:"tone-shand", open:()=>{setTab("handovers");void loadHandovers();}},
    {key:"returns", label:"Material Returns & QA", icon:Undo2, tone:"tone-sret", open:()=>{setTab("returns");void loadReturns();}},
    {key:"transfers", label:"Material Transfers", icon:ArrowLeftRight, tone:"tone-sxfer", open:()=>{setTab("transfers");void loadTransfers();void loadTransferMonitor();void loadIntakeOptions();}},
    {key:"preservation", label:"Preservation & Expiry", icon:CalendarClock, tone:"tone-spres", open:()=>{setTab("preservation");void loadPreservation();}},
    {key:"phase7", label:"Phase 7 Operations", icon:Gauge, tone:"tone-sops7", open:()=>{setTab("phase7");void loadPhase7Monitor();}},
    {key:"operations", label:"Phase 5 Overview", icon:LayoutDashboard, tone:"tone-sops5", open:()=>{setTab("operations");void loadOperations();}},
    {key:"usage", label:"Construction Material Usage", icon:HardHat, tone:"tone-suse", open:()=>{setTab("usage");void loadUsages();}},
    {key:"balances", label:"Work-Package Material Balance", icon:Scale, tone:"tone-sbal", open:()=>{setTab("balances");void loadMaterialBalance();}},
  ];
  return <section className="panel">
    <div className="panel-heading">
      <div><h2>Store &amp; Inventory</h2>
        <p className="muted">Warehouses and PO goods receipts · Shared source records, no duplicate stock ledger.</p></div>
      <div><button type="button" onClick={()=>void reload()}><RefreshCw size={15}/> Refresh</button></div>
    </div>
    {error && <p role="alert" className="error">{error}</p>}{message && <p role="status" className="note-card note-good">{message}</p>}
    <div className="proc-nav">{tabs.map(t=>{const Icon=t.icon;return <button key={t.key} type="button" className={`proc-tab ${t.tone}${tab===t.key?" is-on":""}`} aria-pressed={tab===t.key} onClick={t.open}><Icon size={14} strokeWidth={2.4}/><span>{t.label}</span></button>})}</div>
    {tab === "phase7" && <section>
      <h3 className="section-mark"><Gauge size={18} strokeWidth={2.4}/> Phase 7 — preservation, counts, adjustments & scrap</h3>
      <p className="muted">Read-only operational workload. Physical stock readiness is unverified; count variances and write-offs are not authorized.</p>
      <button type="button" disabled={phase7Loading} onClick={()=>void loadPhase7Monitor()}>Refresh workload</button>
      {phase7Error && <p role="alert" className="error">{phase7Error}</p>}
      {phase7Loading && <p>Loading project workload…</p>}
      {phase7Monitor && <>
        <p>Snapshot: {phase7Monitor.as_of} · {phase7Monitor.coverage}</p>
        <ul className="fact-row">
          {Object.entries(phase7Monitor.counts).map(([name,value])=><li className="fact" key={name}><strong>{name.replaceAll("_"," ")}</strong><em>{value===null?"Unknown":value}</em></li>)}
        </ul>
        <h4>Preservation due / holds</h4><ul>{phase7Monitor.preservation.filter(x=>x.status!=="Scheduled").slice(0,30).map(x=><li key={x.id}>Plan #{x.id}: {x.status}, owner #{x.owner_id}, due {x.next_due_date}</li>)}</ul>
        <h4>Cycle counts</h4><ul>{phase7Monitor.cycle_counts.slice(0,30).map(x=><li key={x.id}>{x.reference}: {x.status}</li>)}</ul>
        <h4>Adjustment requests</h4><ul>{phase7Monitor.adjustments.slice(0,30).map(x=><li key={x.id}>{x.reference}: {x.status}</li>)}</ul>
        <h4>Scrap cases</h4><ul>{phase7Monitor.scrap_cases.slice(0,30).map(x=><li key={x.id}>{x.reference}: {x.status}</li>)}</ul>
        <h4>Coverage limitations</h4><ul>{phase7Monitor.limitations.map((x,i)=><li key={i}>{x}</li>)}</ul>
      </>}
    </section>}
    {tab === "preservation" && <section>
      <h3 className="section-mark"><CalendarClock size={18} strokeWidth={2.4}/> Material preservation & expiry</h3>
      <p className="muted">Inspection evidence and due/overdue holds only. Stock availability remains unverified.</p>
      <button type="button" onClick={()=>void loadPreservation()} disabled={preservationLoading}>Refresh plans</button>
      {preservationError && <p role="alert" className="error">{preservationError}</p>}
      {canReceive && <form onSubmit={createPreservation} className="contact-form st-divider">
        <label>Receipt lot ID <input aria-label="Receipt lot ID" required type="number" min="1" value={preservationLot} onChange={e=>setPreservationLot(e.target.value)}/></label>
        <label>Responsible user ID <input aria-label="Responsible user ID" required type="number" min="1" value={preservationOwner} onChange={e=>setPreservationOwner(e.target.value)}/></label>
        <label>Frequency (days) <input type="number" min="1" max="3650" value={preservationFrequency} onChange={e=>setPreservationFrequency(Number(e.target.value))}/></label>
        <label>Next inspection <input required type="date" value={preservationDue} onChange={e=>setPreservationDue(e.target.value)}/></label>
        <label className="wide">Instructions <textarea required minLength={3} value={preservationInstructions} onChange={e=>setPreservationInstructions(e.target.value)}/></label>
        <button type="submit" className="primary">Create plan</button>
      </form>}
      <div className="hr-table-wrap"><table><thead><tr><th>Lot</th><th>Status</th><th>Expiry</th><th>Next inspection</th><th>Condition</th><th>Inspection</th></tr></thead><tbody>
      {preservationPlans.map(plan=><tr key={plan.id}><td>{plan.lot_code} (#{plan.receipt_lot_id})</td><td><Pill value={plan.status}/></td><td>{plan.expiry_date||'—'}</td><td>{plan.next_due_date}</td><td>{plan.condition}</td><td>
        {canReceive && <div className="st-stack">
          <select aria-label={`Condition for ${plan.lot_code}`} value={preservationCondition[plan.id]||'Good'} onChange={e=>setPreservationCondition(v=>({...v,[plan.id]:e.target.value}))}><option>Good</option><option>Attention</option><option>Quarantined</option></select>
          <input aria-label="Inspection findings" placeholder="Inspection findings" value={preservationNotes[plan.id]||''} onChange={e=>setPreservationNotes(v=>({...v,[plan.id]:e.target.value}))}/>
          <input aria-label="Inspection evidence" placeholder="Evidence reference" value={preservationEvidence[plan.id]||''} onChange={e=>setPreservationEvidence(v=>({...v,[plan.id]:e.target.value}))}/>
          <button type="button" className="tone-submit" disabled={(preservationNotes[plan.id]||'').trim().length<3||(preservationEvidence[plan.id]||'').trim().length<3} onClick={()=>void inspectPreservation(plan)}>Record inspection</button>
        </div>}
        <button type="button" onClick={()=>void loadPreservationHistory(plan)}>View history</button>
        {preservationHistory[plan.id] && <ul>{preservationHistory[plan.id].map(check=><li key={check.id}>{check.checked_at}: {check.condition} — {check.findings}</li>)}</ul>}
      </td></tr>)}</tbody></table></div>
      {!preservationPlans.length && <p className="muted">No preservation plans found. Lots without plans are not verified as preservation-cleared.</p>}
      <p className="note-card">Expired lots and recorded preservation holds are checked in GRN-lot reservation and issue paths. Transfer-derived material and legacy writers require separate coverage review.</p>
    </section>}
    {tab === "transfers" && <div>
      <h3 className="section-mark"><ArrowLeftRight size={18} strokeWidth={2.4}/> Phase 6 — Warehouse material transfers</h3>
      <p className="muted">Custody only: approval, dispatch, receipt and discrepancies. This screen does not move inventory or prove stock availability.</p>
      <form onSubmit={submitTransfer} className="contact-form">
        <input required aria-label="Transfer reference" placeholder="Transfer reference" maxLength={120} value={transferReference} onChange={e=>setTransferReference(e.target.value)}/>
        <select required aria-label="Source warehouse" value={transferSource} onChange={e=>setTransferSource(Number(e.target.value))}><option value={0}>Source warehouse</option>{warehouses.filter(w=>w.active).map(w=><option key={w.id} value={w.id}>{w.code} — {w.name}</option>)}</select>
        <select required aria-label="Destination warehouse" value={transferDestination} onChange={e=>setTransferDestination(Number(e.target.value))}><option value={0}>Destination warehouse</option>{warehouses.filter(w=>w.active).map(w=><option key={w.id} value={w.id}>{w.code} — {w.name}</option>)}</select>
        <select required aria-label="Transfer material" value={transferItem} onChange={e=>setTransferItem(Number(e.target.value))}><option value={0}>Material item</option>{intakeOptions.items.map(i=><option key={i.id} value={i.id}>{i.code} — {i.description}</option>)}</select>
        <input required aria-label="Transfer quantity" type="number" min="0.001" step="0.001" placeholder="Quantity" value={transferQuantity} onChange={e=>setTransferQuantity(e.target.value)}/>
        <input required aria-label="Transfer purpose" minLength={3} placeholder="Purpose" value={transferPurpose} onChange={e=>setTransferPurpose(e.target.value)}/>
        <button type="submit" className="primary" disabled={busy||!canRequest||!transferSource||!transferDestination||transferSource===transferDestination||!transferItem}>Submit request</button>
      </form>
      <button type="button" onClick={()=>void loadTransfers()}>Refresh transfers</button>
      <section aria-label="Transfer custody monitor" className="note-card">
        <h4>Transfer custody monitoring</h4>
        <button type="button" onClick={()=>void loadTransferMonitor()}>Refresh transfer monitor</button>
        {transferMonitorError&&<p role="alert" className="error">{transferMonitorError}</p>}
        {transferMonitor&&<><p><strong>In transit:</strong> {transferMonitor.counts.in_transit||0} · <strong>Overdue (request-age proxy):</strong> {transferMonitor.counts.overdue_in_transit||0} · <strong>Open/escalated discrepancies:</strong> {transferMonitor.counts.open_discrepancy||0} · <strong>Pending custody confirmation:</strong> {transferMonitor.counts.pending_custody_confirmation||0}</p>
          <small>Latest {transferMonitor.record_count} source-project transfers only. Aging uses request creation, not dispatch time. Stock readiness: {transferMonitor.physical_stock_readiness}. As of {transferMonitor.as_of}.</small>
          <ul>{transferMonitor.records.filter(r=>r.receipt_overdue_proxy).slice(0,10).map(r=><li key={r.id}>{r.reference}: in transit for approximately {r.age_hours_since_request} hours since request</li>)}</ul>
        </>}
      </section>
      <div className="hr-table-wrap"><table><thead><tr><th>Reference</th><th>Warehouses</th><th>Item / Qty</th><th>Custody state</th><th>Discrepancy</th><th>Action evidence</th></tr></thead><tbody>
      {transfers.map(r=><tr key={r.id}><td><strong>{r.reference}</strong><p>#{r.id}</p></td><td>{r.source_warehouse_id} → {r.destination_warehouse_id}</td><td>{r.item_id} / {r.quantity}</td><td><Pill value={r.status}/><p>{r.received_quantity!=null?`Received: ${r.received_quantity}`:''}</p></td><td>{r.discrepancy_status}<p>{r.discrepancy_note||''}</p><small>{r.discrepancy_resolution||''}</small></td><td>
        <textarea aria-label={`Transfer ${r.reference} evidence`} placeholder="Required action evidence / discrepancy explanation" value={transferNotes[r.id]||''} onChange={e=>setTransferNotes(v=>({...v,[r.id]:e.target.value}))}/>
        <button type="button" onClick={()=>void checkTransferPosting(r.id)}>Check posting readiness</button>
        {transferPostingChecks[r.id]&&<div role="status" className="note-card note-alert"><strong>Posting blocked — custody is not stock.</strong><ul>{transferPostingChecks[r.id].blockers.map((reason,index)=><li key={index}>{reason}</li>)}</ul></div>}
        {r.status==='Pending Approval'&&<><button type="button" className="tone-approve" disabled={busy||!canRequest} onClick={()=>void advanceTransfer(r,'decision',true)}>Approve</button><button type="button" className="tone-reject" disabled={busy||!canRequest} onClick={()=>void advanceTransfer(r,'decision',false)}>Reject</button></>}
        {r.status==='Approved'&&<button type="button" className="tone-submit" disabled={busy||!canRequest} onClick={()=>void advanceTransfer(r,'dispatch')}>Record dispatch</button>}
        {r.status==='In Transit'&&<><input aria-label={`Transfer ${r.reference} received quantity`} type="number" min="0" max={r.dispatched_quantity||r.quantity} step="0.001" placeholder="Received quantity" value={transferReceived[r.id]??r.dispatched_quantity??''} onChange={e=>setTransferReceived(v=>({...v,[r.id]:e.target.value}))}/><input aria-label={`Transfer ${r.reference} damaged quantity`} type="number" min="0" step="0.001" placeholder="Damaged quantity" value={transferDamaged[r.id]??'0'} onChange={e=>setTransferDamaged(v=>({...v,[r.id]:e.target.value}))}/><button type="button" className="tone-approve" disabled={busy||!canRequest} onClick={()=>void advanceTransfer(r,'receive')}>Confirm receipt</button></>}
        {r.status==='Discrepancy'&&r.discrepancy_status==='Open'&&<><button type="button" className="tone-approve" disabled={busy||!canRequest} onClick={()=>void advanceTransfer(r,'resolve-discrepancy',undefined,'Resolved')}>Resolve</button><button type="button" className="tone-return" disabled={busy||!canRequest} onClick={()=>void advanceTransfer(r,'resolve-discrepancy',undefined,'Escalated')}>Escalate</button></>}
      </td></tr>)}
      </tbody></table></div>{!transfers.length&&<p className="muted">No transfer custody records found.</p>}
    </div>}
    {tab === "balances" && <div>
      <h3 className="section-mark"><Scale size={18} strokeWidth={2.4}/> Work-package material balance</h3>
      <p className="muted">Read-only, exact issue-linked records. Issued quantities are not automatically consumed or installed. Pending returns do not reduce ledger outstanding, and evidence does not modify stock or progress.</p>
      <div className="contact-form">
        <label>Work-package ID <input type="number" min="1" placeholder="All visible work packages" value={balanceWorkPackage} onChange={e=>setBalanceWorkPackage(e.target.value)} /></label>
        <button type="button" disabled={balanceLoading} onClick={()=>void loadMaterialBalance()}>{balanceLoading?'Loading…':'Refresh material balance'}</button>
      </div>
      {balanceError&&<p role="alert" className="error">Material balance unavailable: {balanceError}. No estimated quantities are displayed.</p>}
      {materialBalance&&<>
        <p className="note-card note-alert"><strong>Inventory verified: No.</strong> {materialBalance.coverage} · As of {new Date(materialBalance.as_of).toLocaleString()}</p>
        <div className="hr-table-wrap"><table><thead><tr><th>Handover</th><th>Work package</th><th>Item / Unit</th><th>Issued</th><th>Posted returns</th><th>Outstanding</th><th>Return custody pending</th><th>QA pending usage</th><th>Verified consumed</th><th>Verified installed</th><th>Unallocated outstanding</th></tr></thead><tbody>
          {materialBalance.records.map(row=><tr key={row.handover_id}><td>#{row.handover_id}</td><td>{row.work_package_id??'—'}</td><td>#{row.item_id} / {row.unit}</td><td>{row.issued_quantity}</td><td>{row.ledger_posted_return_quantity}</td><td>{row.ledger_outstanding_quantity}</td><td>{row.pending_custody_return_quantity}</td><td>{row.pending_qa_consumed_quantity} consumed / {row.pending_qa_installed_quantity} installed</td><td>{row.verified_consumed_quantity}</td><td>{row.verified_installed_quantity}</td><td>{row.unallocated_outstanding_quantity}</td></tr>)}
        </tbody></table></div>
        {!materialBalance.records.length&&<p className="muted">No linked material issues are visible for this project and work-package filter.</p>}
        <small>Balances are scoped to your authorized material requests. Unmapped legacy movements and unverified physical stock are excluded.</small>
      </>}
    </div>}
    {tab === "usage" && <div>
      <h3 className="section-mark"><HardHat size={18} strokeWidth={2.4}/> Construction material usage and independent QA verification</h3>
      <p className="muted">Evidence only: issued, returned, consumed, installed and QA-verified are distinct states. No stock, billing or progress is posted by this screen.</p>
      <form onSubmit={submitMaterialUsage} className="contact-form">
        <label>Handover ID <input type="number" min="1" required value={usageHandover} onChange={e=>setUsageHandover(e.target.value)}/></label>
        <label>Usage type <select value={usageKind} onChange={e=>setUsageKind(e.target.value as 'Consumed'|'Installed')}><option value="Consumed">Consumed</option><option value="Installed">Installed</option></select></label>
        <label>Quantity <input type="number" min="0.001" step="0.001" required value={usageQuantity} onChange={e=>setUsageQuantity(e.target.value)}/></label>
        <label>Evidence key <input required maxLength={120} value={usageKey} onChange={e=>setUsageKey(e.target.value)}/></label>
        <label className="wide">Supporting evidence <textarea required minLength={5} maxLength={4000} value={usageEvidence} onChange={e=>setUsageEvidence(e.target.value)}/></label>
        <button type="submit" className="primary" disabled={busy}>Submit for QA</button>
      </form>
      <div className="contact-form st-divider">
        <label>Work-package filter <input type="number" min="1" placeholder="All work packages" value={usageWorkPackage} onChange={e=>setUsageWorkPackage(e.target.value)}/></label>
        <button type="button" onClick={()=>void loadUsages()}>Refresh usage / QA queue</button>
      </div>
      {usageLoadError&&<p role="alert" className="error">Usage list unavailable: {usageLoadError}</p>}
      <div className="hr-table-wrap"><table><thead><tr><th>Evidence</th><th>Handover</th><th>Work package</th><th>Material</th><th>Type / Qty</th><th>Status</th><th>QA review</th></tr></thead><tbody>
        {usageRecords.concat(qaUsageRecords.filter(row=>!usageRecords.some(other=>other.id===row.id))).map(row=><tr key={row.id}><td><strong>#{row.id} · {row.evidence_key}</strong><p>{row.evidence}</p></td><td>#{row.handover_id}</td><td>#{row.work_package_id}</td><td>#{row.item_id}</td><td>{row.usage_type} · {row.quantity} {row.unit}</td><td><Pill value={row.status}/>{row.verification_note&&<p>{row.verification_note}</p>}</td><td>{row.status==='Pending QA'?<><textarea aria-label={`QA note for material usage ${row.id}`} placeholder="Independent QA decision evidence" value={usageReviewNotes[row.id]||''} onChange={e=>setUsageReviewNotes(v=>({...v,[row.id]:e.target.value}))}/><button type="button" className="tone-approve" disabled={busy} onClick={()=>void reviewMaterialUsage(row,'Verified')}>Verify</button><button type="button" className="tone-reject" disabled={busy} onClick={()=>void reviewMaterialUsage(row,'Rejected')}>Reject</button></>:'Reviewed'}</td></tr>)}
      </tbody></table></div>
      {!usageRecords.length&&!qaUsageRecords.length&&!usageLoadError&&<p className="muted">No material-specific usage records visible for this project/filter.</p>}
      <small>Record visibility and action authority are enforced by the backend. This list is limited to 300 records.</small>
    </div>}
    {tab === "operations" && <div>
      <h3 className="section-mark"><LayoutDashboard size={18} strokeWidth={2.4}/> Phase 5 — Material custody and return overview</h3>
      <p className="muted">Read-only handover, discrepancy, return and QA stages. Stock availability and installation are not verified here.</p>
      <button type="button" onClick={()=>void loadOperations()}>Refresh overview</button>
      {operations ? <>
        <p>{operations.coverage} · Updated {new Date(operations.as_of).toLocaleString()}</p>
        <p className="note-card note-alert">Physical inventory verified: <strong>No</strong></p>
        <ul className="fact-row">{Object.entries(operations.counts).map(([key,value])=><li key={key} className="fact"><strong>{key.replaceAll('_',' ')}</strong><em>{value}</em></li>)}</ul>
        <div className="hr-table-wrap"><table><thead><tr><th>Handover</th><th>Work package</th><th>Material request</th><th>Dispatched</th><th>Handover status</th><th>Acknowledgment age</th><th>Return status</th><th>Return posting</th></tr></thead><tbody>
          {operations.records.map(row=><tr key={row.handover_id}><td><strong>{row.handover_reference}</strong></td><td>{row.work_package_id??'—'}</td><td>#{row.material_request_id}</td><td>{row.dispatched_quantity}</td><td><Pill value={row.handover_status}/></td><td>{row.acknowledgment_overdue?<Pill value="Overdue"/>:row.dispatched_at?"Within threshold / completed":"Unknown"}</td><td>{row.return_status?<Pill value={row.return_status}/>:'—'}</td><td>{row.return_stock_posting_id?`#${row.return_stock_posting_id}`:'Not posted'}</td></tr>)}
        </tbody></table></div>
      </> : <p className="muted">Overview unavailable — no values shown.</p>}
    </div>}
    {tab === "handovers" && <div>
      <h3 className="section-mark"><PackageCheck size={18} strokeWidth={2.4}/> Material handovers and discrepancy review</h3><p className="muted">Independent Stores review records the decision and evidence. A resolution is not a stock adjustment, replacement issue or evidence of installed progress.</p>
      <button type="button" onClick={()=>void loadHandovers()}>Refresh handovers</button>
      <div className="hr-table-wrap"><table><thead><tr><th>Reference</th><th>Dispatched</th><th>Received</th><th>Damaged</th><th>Status</th><th>Discrepancy</th><th>Independent Stores review</th></tr></thead><tbody>
       {handovers.map(row=><tr key={row.id}><td><strong>{row.handover_reference}</strong></td><td>{row.quantity}</td><td>{row.received_quantity??'—'}</td><td>{row.damaged_quantity??'—'}</td><td><Pill value={row.status}/></td><td>{row.discrepancy_note||'—'}{row.resolution_note&&<p>Review: {row.resolution_note}</p>}</td><td>{row.status==='Discrepancy'&&canEdit?<><textarea aria-label={`Resolution evidence ${row.handover_reference}`} maxLength={4000} placeholder="Verified resolution evidence" value={resolutionNotes[row.id]||''} onChange={e=>setResolutionNotes(v=>({...v,[row.id]:e.target.value}))}/><button type="button" className="tone-approve" disabled={busy} onClick={()=>void reviewHandover(row,'Resolved')}>Mark resolved</button><button type="button" className="tone-return" disabled={busy} onClick={()=>void reviewHandover(row,'Escalated')}>Escalate</button></>:'—'}</td></tr>)}
      </tbody></table></div>{handovers.length===0&&<p className="muted">No material handovers recorded.</p>}
    </div>}
    {tab === "returns" && <div>
      <h3 className="section-mark"><Undo2 size={18} strokeWidth={2.4}/> Material returns — Stores custody, QA and reconciliation</h3><p className="muted">Return bin assignment records custody only. Posting is disabled by default and requires controlled database cutover. No quarantine release is automatic.</p>
      {returnExceptions ? <div className="note-card">
        <strong>Return exception monitor — {returnExceptions.total_records} recent returns</strong>
        <p>Physical stock readiness: {returnExceptions.physical_stock_readiness}. {returnExceptions.coverage}</p>
        <ul className="fact-row">{Object.entries(returnExceptions.counts).map(([key,count])=><li key={key} className="fact"><strong>{key.replaceAll('_',' ')}</strong><em>{count}</em></li>)}</ul>
      </div> : <p className="muted">Return exception monitor unavailable — no verified summary.</p>}
      {returnWorkload ? <div className="note-card">
        <strong>Return exception task workload</strong>
        <p>Open assigned tasks: {returnWorkload.active_tasks} · Overdue: {returnWorkload.overdue_tasks} · Blocked: {returnWorkload.blocked_tasks} · Unassigned: {returnWorkload.unassigned_exceptions}</p>
        <div className="fin-actions">{Object.entries(returnWorkload.by_owner_id).map(([owner,count])=><span key={owner}>Owner #{owner}: {count}</span>)}</div>
        <small>{returnWorkload.coverage} Stock readiness remains unverified.</small>
      </div> : <p className="muted">Return task workload unavailable — no verified task metrics.</p>}
      <button type="button" onClick={()=>void loadReturns()}>Refresh returns</button>
      <div className="hr-table-wrap"><table><thead><tr><th>Return</th><th>Handover ID</th><th>Requested</th><th>Received</th><th>Condition</th><th>Status</th><th>Evidence / decision</th><th>Bin / posting reconciliation</th></tr></thead><tbody>
      {returns.map(row=><tr key={row.id}><td><strong>#{row.id}</strong><p>{row.reason}</p></td><td>{row.handover_id}</td><td>{row.requested_quantity}</td><td>{row.received_quantity??'—'}</td><td>{row.condition}</td><td><Pill value={row.status}/></td><td>
      {row.receipt_evidence&&<p>Stores: {row.receipt_evidence}</p>}{row.qa_decision&&<p>QA: {row.qa_decision} — {row.qa_evidence}</p>}
      {(row.status==='Submitted'||row.status==='Awaiting QA')&&<div className="st-stack">
       {row.status==='Submitted'&&<label>Quantity physically received <input aria-label={`Return ${row.id} received quantity`} type="number" min="0.001" step="0.001" max={row.requested_quantity} value={returnQuantities[row.id]??row.requested_quantity} onChange={e=>setReturnQuantities(v=>({...v,[row.id]:e.target.value}))}/></label>}
       <textarea aria-label={`Return ${row.id} evidence`} placeholder="Required verification evidence" maxLength={4000} value={returnEvidence[row.id]||''} onChange={e=>setReturnEvidence(v=>({...v,[row.id]:e.target.value}))}/>
       {row.status==='Submitted'?<button type="button" className="tone-submit" disabled={busy||!canEdit} onClick={()=>void processReturn(row,'receive')}>Confirm Stores receipt</button>:<div className="fin-actions"><button type="button" className="tone-approve" disabled={busy} onClick={()=>void processReturn(row,'qa-disposition','Accepted')}>QA Accept</button><button type="button" className="tone-return" disabled={busy} onClick={()=>void processReturn(row,'qa-disposition','Quarantined')}>Quarantine</button><button type="button" className="tone-reject" disabled={busy} onClick={()=>void processReturn(row,'qa-disposition','Rejected')}>Reject</button></div>}
      </div>}</td><td>
       <p>{returnReconciliation.find(x=>x.return_id===row.id)?.reconciliation_state||'Not verified'}</p>
       {row.location_id&&<p>Bin #{row.location_id} · {row.placement_evidence||'—'}</p>}
       {row.stock_posted&&<p>Ledger posting #{row.stock_posting_id}</p>}
       {row.status==='QA Accepted'&&!row.stock_posted&&canRequest&&<div className="st-stack">
         {!row.location_id&&<><select aria-label={`Return ${row.id} storage bin`} value={returnLocation[row.id]||''} onChange={e=>setReturnLocation(v=>({...v,[row.id]:e.target.value}))}>
           <option value=''>Select active storage bin</option>{locations.filter(l=>l.active&&l.location_type==='Bin').map(l=><option key={l.id} value={l.id}>{l.code} (warehouse #{l.warehouse_id})</option>)}
         </select><textarea aria-label={`Return ${row.id} placement evidence`} placeholder='Placement evidence' value={returnEvidence[row.id]||''} onChange={e=>setReturnEvidence(v=>({...v,[row.id]:e.target.value}))}/><button disabled={busy} type='button' className="tone-submit" onClick={()=>void placeReturn(row)}>Record bin custody</button></>}
         {!!row.location_id&&<><input aria-label={`Return ${row.id} posting reference`} placeholder='Unique posting reference' maxLength={80} value={returnPostingReference[row.id]||''} onChange={e=>setReturnPostingReference(v=>({...v,[row.id]:e.target.value}))}/><textarea aria-label={`Return ${row.id} posting evidence`} placeholder='Posting evidence' value={returnEvidence[row.id]||''} onChange={e=>setReturnEvidence(v=>({...v,[row.id]:e.target.value}))}/><button disabled={busy} type='button' className="tone-submit" onClick={()=>void postReturn(row)}>Post return (feature-gated)</button></>}
       </div>}
      </td></tr>)}
      </tbody></table></div>{returns.length===0&&<p className="muted">No returns recorded for this project.</p>}
    </div>}
    {tab === "warehouses" && <>
    <div className="contact-form">
      <label>Project <select value={pid} onChange={e=>setPid(Number(e.target.value))}>{Array.from(new Set(session.memberships.map(m=>m.project_id).filter((id): id is number => typeof id === "number"))).map(id=><option key={id} value={id}>{id}</option>)}</select></label>
      <label>Warehouse <select value={warehouseId} onChange={e=>{setWarehouseId(Number(e.target.value));setParentId(0);}}>{warehouses.map(w=><option key={w.id} value={w.id}>{w.code} — {w.name}</option>)}</select></label>
    </div>
    <div><h3 className="section-mark"><MapPinned size={18} strokeWidth={2.4}/> Warehouse locations</h3>
      <div className="hr-table-wrap"><table><thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Parent</th><th>Status</th></tr></thead>
      <tbody>{locations.filter(x=>x.warehouse_id===warehouseId).map(x=><tr key={x.id}><td><strong>{x.code}</strong></td><td>{x.name}</td><td>{x.location_type}</td><td>{locations.find(p=>p.id===x.parent_id)?.code || "—"}</td><td><Pill value={x.active?"Active":"Inactive"}/></td></tr>)}</tbody></table></div>
      {!locations.some(x=>x.warehouse_id===warehouseId)&&<p className="muted">No storage locations yet.</p>}
    </div>
    {canEdit && !!warehouseId && <form onSubmit={create} className="contact-form st-divider">
      <label>Code <input required maxLength={80} value={code} onChange={e=>setCode(e.target.value)}/></label>
      <label>Name <input required maxLength={200} value={name} onChange={e=>setName(e.target.value)}/></label>
      <label>Type <select value={kind} onChange={e=>setKind(e.target.value)}><option>Zone</option><option>Rack</option><option>Bin</option></select></label>
      <label>Parent <select value={parentId} onChange={e=>setParentId(Number(e.target.value))}><option value={0}>No parent</option>{locations.filter(x=>x.warehouse_id===warehouseId&&x.active).map(x=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select></label>
      <button disabled={busy} type="submit" className="primary">{busy?"Saving...":"Create location"}</button>
    </form>}
    </>}
    {tab === "notices" && <div>
      <div><h3 className="section-mark"><Truck size={18} strokeWidth={2.4}/> Advance shipping notices</h3>
        <p className="muted">Supplier-provided delivery forecasts. Notices do not post a goods receipt, reserve stock or release materials.</p>
        <div className="hr-table-wrap"><table><thead><tr><th>ASN</th><th>PO ID</th><th>ETA</th><th>Delivery note</th><th>Status</th></tr></thead>
          <tbody>{notices.map(n=><tr key={n.id}><td><strong>{n.number}</strong></td><td>{n.purchase_order_id}</td><td>{n.expected_date}</td><td>{n.delivery_note}</td><td><Pill value={n.status}/></td><td><button type="button" onClick={()=>setEvidenceSelection({kind:"notice",id:n.id})}>Evidence</button></td></tr>)}</tbody>
        </table></div>{!notices.length && <p className="muted">No advance shipping notices recorded.</p>}
      </div>
      {canReceive && <form className="st-divider" onSubmit={createNotice}>
        <h3 className="section-mark"><Truck size={18} strokeWidth={2.4}/> Record supplier delivery notice</h3>
        <div className="contact-form">
          <label>ASN number <input required maxLength={80} value={noticeNo} onChange={e=>setNoticeNo(e.target.value)}/></label>
          <label>Expected date <input required type="date" value={expectedDate} onChange={e=>setExpectedDate(e.target.value)}/></label>
          <label>Purchase order <select required value={noticePo} onChange={e=>{setNoticePo(Number(e.target.value));setNoticeQuantities({});}}>
            <option value={0}>Select PO</option>{sources.map(x=><option key={x.purchase_order_id} value={x.purchase_order_id}>{x.number} — {x.vendor}</option>)}
          </select></label>
          <label>Delivery note <input maxLength={160} value={noticeDelivery} onChange={e=>setNoticeDelivery(e.target.value)}/></label>
        </div>
        <div className="hr-table-wrap"><table><thead><tr><th>Item</th><th>Ordered remaining</th><th>Unit</th><th>Forecast quantity</th></tr></thead>
          <tbody>{(sources.find(x=>x.purchase_order_id===noticePo)?.lines||[]).map(l=><tr key={l.purchase_order_line_id}><td>{l.item_code}</td><td>{l.remaining}</td><td>{l.unit}</td>
            <td><input type="number" min="0" step="0.001" value={noticeQuantities[l.purchase_order_line_id]||""}
              onChange={e=>setNoticeQuantities(p=>({...p,[l.purchase_order_line_id]:e.target.value}))}/></td></tr>)}</tbody></table></div>
        <button type="submit" className="primary" disabled={busy||!noticePo}>{busy?"Saving...":"Submit delivery notice"}</button>
      </form>}
    </div>}
    {tab === "intakes" && <div>
      <h3 className="section-mark"><PackagePlus size={18} strokeWidth={2.4}/> Free-issue / non-PO / opening stock intake queue</h3>
      <p className="muted">Exception requests require independent review. Even approved requests do not create stock until ledger posting and QA release are implemented.</p>
      <div className="hr-table-wrap"><table><thead><tr><th>Reference</th><th>Type</th><th>Reason</th><th>Status</th><th>Independent review</th></tr></thead>
      <tbody>{intakes.map(x=><tr key={x.id}><td><strong>{x.number}</strong></td><td>{x.intake_type}</td><td>{x.reason}</td><td><Pill value={x.status}/></td><td><button type="button" onClick={()=>setEvidenceSelection({kind:"intake",id:x.id})}>Evidence</button></td><td>{canEdit && x.status === "Pending Review" ? <div className="fin-actions">
        <input aria-label={`Review note ${x.number}`} placeholder="Review reason (5+ chars)" maxLength={2000} value={reviewNotes[x.id]||""} onChange={e=>setReviewNotes(old=>({...old,[x.id]:e.target.value}))}/>
        <button type="button" className="tone-approve" disabled={busy} onClick={()=>void reviewIntake(x,"Approve")}>Approve</button><button type="button" className="tone-reject" disabled={busy} onClick={()=>void reviewIntake(x,"Reject")}>Reject</button></div>:"—"}</td></tr>)}</tbody></table></div>
      {!intakes.length&&<p className="muted">No exceptional intake requests recorded.</p>}
      {canReceive && <form onSubmit={createIntake} className="st-divider">
        <h3 className="section-mark"><PackagePlus size={18} strokeWidth={2.4}/> Submit an exceptional intake request</h3>
        <p className="muted">Requests require independent approval; submitting or approving does not post stock.</p>
        <div className="contact-form">
          <label>Reference <input required maxLength={80} value={intakeNumber} onChange={e=>setIntakeNumber(e.target.value)}/></label>
          <label>Type <select value={intakeType} onChange={e=>setIntakeType(e.target.value)}><option>Free Issue</option><option>Non PO</option><option>Opening Stock</option></select></label>
          <label>Warehouse <select required value={intakeWarehouse} onChange={e=>setIntakeWarehouse(Number(e.target.value))}><option value={0}>Select warehouse</option>{intakeOptions.warehouses.map(w=><option key={w.id} value={w.id}>{w.code} — {w.name}</option>)}</select></label>
          <label>Material owner <select required value={intakeOwner} onChange={e=>setIntakeOwner(Number(e.target.value))}><option value={0}>Select owner</option>{intakeOptions.companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
          <label>Source company <select required value={intakeSource} onChange={e=>setIntakeSource(Number(e.target.value))}><option value={0}>Select source</option>{intakeOptions.companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
          <label className="wide">Justification <textarea required minLength={5} maxLength={2000} value={intakeReason} onChange={e=>setIntakeReason(e.target.value)}/></label>
        </div>
        <div className="hr-table-wrap"><table><thead><tr><th>Material</th><th>Quantity</th><th>Base unit</th><th>Batch / Heat</th><th></th></tr></thead><tbody>
          {intakeLines.map((l,index)=><tr key={index}><td><select required value={l.item_id} onChange={e=>setIntakeLines(rows=>rows.map((r,j)=>j===index?{...r,item_id:Number(e.target.value)}:r))}><option value={0}>Select material</option>{intakeOptions.items.map(i=><option key={i.id} value={i.id}>{i.code} — {i.description}</option>)}</select></td>
          <td><input type="number" min="0.001" step="any" required value={l.quantity} onChange={e=>setIntakeLines(rows=>rows.map((r,j)=>j===index?{...r,quantity:e.target.value}:r))}/></td>
          <td>{intakeOptions.items.find(i=>i.id===l.item_id)?.base_unit || "—"}</td>
          <td><input maxLength={120} value={l.batch_or_heat} onChange={e=>setIntakeLines(rows=>rows.map((r,j)=>j===index?{...r,batch_or_heat:e.target.value}:r))}/></td>
          <td><button type="button" disabled={intakeLines.length===1} onClick={()=>setIntakeLines(rows=>rows.filter((_,j)=>j!==index))}>Remove</button></td></tr>)}
        </tbody></table></div>
        <div className="fin-actions"><button type="button" onClick={()=>setIntakeLines(rows=>[...rows,{item_id:0,quantity:"",batch_or_heat:""}])}>Add material</button>
        <button type="submit" className="primary" disabled={busy||!intakeOptions.items.length}>{busy?"Submitting...":"Submit for review"}</button></div>
      </form>}
    </div>}
    {tab === "requests" && <div>
      <h3 className="section-mark"><ListChecks size={18} strokeWidth={2.4}/> Material Issue Requests — linked to approved Procurement Requirements</h3>
      <p className="muted">Choose an existing approved Procurement requirement line. This requests Stores stock release; it does not create another material demand. Requests require approved WBS/work-package references and independent review. Approved demand is not automatically reserved, issued, or counted as installed progress.</p>
      <div className="fin-actions">
        <button type="button" disabled={busy} onClick={()=>void loadMaterialRequests()}>Refresh requests</button>
        <label><input type="checkbox" checked={requestQueueOnly} onChange={e=>setRequestQueueOnly(e.target.checked)}/> Pending approval only</label>
      </div>
      <p className="note-card">Partner requests enter this same internal review queue. Approvals revalidate the source requirement and released contractor work package; no stock posts here.</p>
      <div className="hr-table-wrap"><table><thead><tr><th>Request</th><th>Origin / company</th><th>Requirement line</th><th>Material</th><th>Quantity</th><th>Required</th><th>Work scope</th><th>Status</th><th>Action</th></tr></thead><tbody>
        {materialRequests.filter(r=>!requestQueueOnly||r.status==="Pending Approval").map(r=><tr key={r.id}><td><strong>{r.request_key}</strong></td><td>{r.requester_company_id?`Partner · company ${r.requester_company_id}`:"Internal"}</td><td>{r.requirement_line_id||"Legacy — link required"}</td><td>{intakeOptions.items.find(i=>i.id===r.item_id)?.code||r.item_id}</td><td>{r.quantity} {r.unit}</td><td>{r.required_date}</td><td>{r.work_package_id?`Work package ${r.work_package_id}`:`WBS ${r.planning_wbs_id}`}</td><td><Pill value={r.status}/></td><td>
          {r.status==="Draft"&&<button type="button" className="tone-submit" disabled={busy||!canRequestCreate} onClick={()=>void changeMaterialRequest(r,"Submit")}>Submit</button>}
          {r.status==="Approved"&&<button type="button" className="tone-note" disabled={busy} onClick={()=>void inspectAllocations(r.id)}>View / allocate</button>}
          {r.status==="Pending Approval"&&canRequestReview&&<div className="fin-actions"><input aria-label={`Review reason for ${r.request_key}`} placeholder="Review reason" minLength={3} value={requestReviewReasons[r.id]||""} onChange={e=>setRequestReviewReasons(v=>({...v,[r.id]:e.target.value}))}/><button type="button" className="tone-approve" disabled={busy} onClick={()=>void changeMaterialRequest(r,"Approved")}>Approve</button><button type="button" className="tone-reject" disabled={busy} onClick={()=>void changeMaterialRequest(r,"Rejected")}>Reject</button></div>}
        </td></tr>)}
      </tbody></table>{!materialRequests.length&&<p className="muted">No material requests yet.</p>}</div>
      {selectedAllocRequest!==null&&<div className="note-card">
        <h4>Request #{selectedAllocRequest} — lot allocations</h4>
        <button type="button" onClick={()=>{setSelectedAllocRequest(null);setAllocationOverview(null)}}>Close</button>
        {allocationOverview&&<><p>Approved: {allocationOverview.approved_quantity} · Reserved: {allocationOverview.active_reserved_quantity} · Issued: {allocationOverview.consumed_by_issue} · Released: {allocationOverview.released_quantity} · Unallocated: {allocationOverview.unallocated_quantity}. Issue does not mean installation.</p>
        <div className="hr-table-wrap"><table><thead><tr><th>Lot</th><th>Reserved</th><th>Remaining</th><th>Status</th></tr></thead><tbody>
          {allocationOverview.reservations.map(r=><tr key={r.id}><td>{r.lot_id}</td><td>{r.allocated_quantity}</td><td>{r.remaining_quantity}</td><td><Pill value={r.status}/></td></tr>)}
        </tbody></table></div></>}
        {canRequestAllocate&&<form onSubmit={allocateSelectedLot} className="contact-form st-divider">
          <label>Receipt lot <select required value={allocationLot} onChange={e=>setAllocationLot(Number(e.target.value))}><option value={0}>Select a registered lot</option>{lots.map(l=><option key={l.id} value={l.id}>Lot #{l.id} · batch {l.batch_number||"—"} · heat {l.heat_number||"—"}</option>)}</select></label>
          <label>Reserve quantity <input required type="number" min="0.001" step="0.001" value={allocationQuantity} onChange={e=>setAllocationQuantity(e.target.value)}/></label>
          <label>Unique allocation key <input required maxLength={120} value={allocationKey} onChange={e=>setAllocationKey(e.target.value)}/></label>
          <button type="submit" className="primary" disabled={busy||!allocationLot||!allocationQuantity||!allocationKey.trim()}>Allocate eligible stock</button>
        </form>}
        <p className="muted">Backend QA, ownership, expiry and feature gates determine eligibility. A visible lot is not necessarily available.</p>
      </div>}
      <h3 className="section-mark st-divider"><ListChecks size={18} strokeWidth={2.4}/> Approved demand awaiting allocation</h3>
      <p className="muted">This is unallocated demand, not a verified warehouse stock shortage.</p>
      <div className="hr-table-wrap"><table><thead><tr><th>Request ID</th><th>Material</th><th>Approved demand</th><th>Unallocated</th></tr></thead><tbody>{materialDemand.map(d=><tr key={d.request_id}><td>{d.request_id}</td><td>{d.item_id}</td><td>{d.approved_demand} {d.unit}</td><td>{d.unallocated_demand} {d.unit}</td></tr>)}</tbody></table></div>
      {canRequestCreate&&<form onSubmit={createMaterialRequest} className="st-divider"><h3 className="section-mark"><ListChecks size={18} strokeWidth={2.4}/> New material issue request (from approved requirement)</h3>
        <div className="contact-form">
          <label>Request reference <input required maxLength={120} value={requestKey} onChange={e=>setRequestKey(e.target.value)}/></label>
          <label>Approved Procurement requirement line ID <input type="number" min="1" required value={requestRequirementLine} onChange={e=>setRequestRequirementLine(e.target.value)}/></label>
          <label>Material <select required value={requestItem} onChange={e=>setRequestItem(Number(e.target.value))}><option value={0}>Choose item</option>{intakeOptions.items.map(i=><option key={i.id} value={i.id}>{i.code} — {i.description}</option>)}</select></label>
          <label>Quantity <input type="number" required min="0.001" step="any" value={requestQty} onChange={e=>setRequestQty(e.target.value)}/></label>
          <label>Required date <input type="date" required value={requestDate} onChange={e=>setRequestDate(e.target.value)}/></label>
          <label>Planning WBS ID <input type="number" min="1" value={requestWbs} onChange={e=>setRequestWbs(e.target.value)}/></label>
          <label>Work package ID <input type="number" min="1" value={requestWorkPackage} onChange={e=>setRequestWorkPackage(e.target.value)}/></label>
          <label className="wide">Justification <textarea maxLength={2000} value={requestReason} onChange={e=>setRequestReason(e.target.value)}/></label>
        </div>
        <button type="submit" className="primary" disabled={busy||!requestRequirementLine||!requestItem||!requestKey.trim()||!requestQty}>{busy?"Saving...":"Create draft request"}</button>
      </form>}
    </div>}
    {evidenceSelection && <div className="note-card">
      <h4>Document evidence</h4><button type="button" onClick={()=>setEvidenceSelection(null)}>Close</button>
      <StoresEvidence basePath={`/projects/${pid}/stores/${evidenceSelection.kind}/${evidenceSelection.id}`} canUpload={canReceive}/>
    </div>}
    {tab === "receipts" && <div>
      <div><h3 className="section-mark"><ClipboardList size={18} strokeWidth={2.4}/> Goods receipts</h3>
        <p className="muted">Linked to the existing Procurement PO and receipt records. Posting a receipt does not release stock.</p>
        <div className="hr-table-wrap"><table><thead><tr><th>GRN</th><th>PO</th><th>Vendor</th><th>Date</th><th>Warehouse</th><th>Status</th><th>Evidence</th></tr></thead>
        <tbody>{receipts.map(r=><tr key={r.id}><td><strong>{r.number}</strong></td><td>{r.purchase_order_number}</td><td>{r.vendor}</td><td>{r.receipt_date}</td><td>{r.warehouse||"—"}</td><td><Pill value={r.status}/></td><td><button type="button" onClick={()=>setEvidenceSelection({kind:"receipt",id:r.id})}>Evidence</button></td></tr>)}</tbody></table></div>
        {!receipts.length && <p className="muted">No goods receipts recorded.</p>}
      </div>
      {canReceive && <form className="st-divider" onSubmit={postReceipt}>
        <h3 className="section-mark"><ClipboardList size={18} strokeWidth={2.4}/> Create PO-linked goods receipt</h3>
        <div className="contact-form">
          <label>Receipt number <input required maxLength={80} value={receiptNo} onChange={e=>setReceiptNo(e.target.value)}/></label>
          <label>Receipt date <input required type="date" value={receiptDate} onChange={e=>setReceiptDate(e.target.value)}/></label>
          <label>Purchase order <select required value={poId} onChange={e=>{setPoId(Number(e.target.value));setQuantities({});}}>
            <option value={0}>Select PO</option>{sources.map(x=><option key={x.purchase_order_id} value={x.purchase_order_id}>{x.number} — {x.vendor}</option>)}
          </select></label>
          <label>Warehouse <select value={warehouseId} onChange={e=>setWarehouseId(Number(e.target.value))}><option value={0}>Unassigned</option>{warehouses.filter(x=>x.active).map(w=><option key={w.id} value={w.id}>{w.code} — {w.name}</option>)}</select></label>
          <label>Delivery note <input value={deliveryNote} onChange={e=>setDeliveryNote(e.target.value)}/></label>
        </div>
        <div className="hr-table-wrap"><table><thead><tr><th>Item</th><th>Remaining</th><th>Unit</th><th>Receipt quantity</th></tr></thead><tbody>
          {(sources.find(x=>x.purchase_order_id===poId)?.lines||[]).map(line=><tr key={line.purchase_order_line_id}><td>{line.item_code}</td><td>{line.remaining}</td><td>{line.unit}</td><td><input type="number" min="0" max={line.remaining} step="0.001" value={quantities[line.purchase_order_line_id]||""} onChange={e=>setQuantities(prev=>({...prev,[line.purchase_order_line_id]:e.target.value}))}/></td></tr>)}
        </tbody></table></div>
        <button type="submit" className="primary" disabled={busy||!poId}>{busy?"Posting...":"Post receipt"}</button>
      </form>}
      <p className="note-card">PO-linked GRNs post through the existing Procurement receipt service. Free-issue/non-PO intake requests and ASN notices are tracked separately and cannot create accepted stock. QA release and unified ledger posting remain pending.</p>
    </div>}
  </section>;
}
