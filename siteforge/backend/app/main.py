from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from .config import settings
from .db import engine
from .domains.identity_projects.router import router
from .domains.identity_projects.phase2 import router as phase2_router
from .domains.coordination.router import router as coordination_router
from .domains.engineering_documents.router import router as engineering_router
from .domains.engineering_documents.takeoff_router import router as takeoff_router
from .domains.supply_chain.router import router as procurement_router
from .domains.construction.router import router as construction_router
from .domains.hse.router import router as hse_router
from .domains.quality.router import router as quality_router
from .domains.workforce.router import router as workforce_router
from .domains.manpower.router import router as manpower_router
from .domains.partner_portal.router import router as partner_router
from .domains.partner_portal.transactions import router as partner_transactions_router

from .domains.partner_portal.acknowledgments import router as partner_acknowledgments_router

app = FastAPI(title="ZerroBuild", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Tab-Id"],
)


@app.exception_handler(IntegrityError)
async def duplicate_error(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"detail": "Duplicate value or invalid record reference"},
    )


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "version": "0.2.0"}


app.include_router(router)
app.include_router(phase2_router)
app.include_router(coordination_router)
app.include_router(engineering_router)
app.include_router(takeoff_router)
app.include_router(procurement_router)
app.include_router(construction_router)
app.include_router(quality_router)
app.include_router(hse_router)
app.include_router(workforce_router)
app.include_router(manpower_router)
app.include_router(partner_router)
app.include_router(partner_transactions_router)

app.include_router(partner_acknowledgments_router)

from .vision_progress import router as vision_progress_router
app.include_router(vision_progress_router)

from .domains.planning_reporting.router import router as planning_baseline_router
app.include_router(planning_baseline_router)

from .domains.planning_reporting.workspace_router import router as planning_workspace_router
app.include_router(planning_workspace_router)
from .domains.planning_reporting.actuals_router import router as planning_actuals_router
app.include_router(planning_actuals_router)
from .domains.planning_reporting.curves_router import router as planning_curves_router
app.include_router(planning_curves_router)

from .domains.planning_reporting.lookahead_router import router as planning_lookahead_router
app.include_router(planning_lookahead_router)
from .domains.planning_reporting.resources_router import router as planning_resources_router
app.include_router(planning_resources_router)
from .domains.planning_reporting.availability_router import router as planning_availability_router
app.include_router(planning_availability_router)

from .domains.planning_reporting.alerts_router import router as planning_alerts_router
app.include_router(planning_alerts_router)

from .domains.planning_reporting.reports_router import router as planning_reports_router
app.include_router(planning_reports_router)
from .domains.planning_reporting.excel_import_router import router as planning_excel_import_router
app.include_router(planning_excel_import_router)

from .domains.planning_reporting.bulk_import_router import router as planning_bulk_import_router
app.include_router(planning_bulk_import_router)

from .domains.planning_reporting.milestone_evidence_router import router as planning_milestone_evidence_router
app.include_router(planning_milestone_evidence_router)

# Phase 13 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â non-persistent, authenticated planning forecast previews.
from .domains.planning_reporting.forecast_router import router as planning_forecast_router
app.include_router(planning_forecast_router)

from .domains.planning_reporting.allocations_router import router as planning_allocations_router
app.include_router(planning_allocations_router)
from .domains.planning_reporting.hr_allocations_router import router as planning_hr_allocations_router
app.include_router(planning_hr_allocations_router)

from .domains.planning_reporting.equipment_router import router as planning_equipment_router
app.include_router(planning_equipment_router)
# Equipment E7B2 authority verification
from .domains.planning_reporting.equipment_e7_authority_api import router as equipment_authority_router
app.include_router(equipment_authority_router)
from .domains.planning_reporting.equipment_e7_handoff_api import router as equipment_handoff_router
app.include_router(equipment_handoff_router)

# Phase 29: isolated company-scoped Planning partner API
from .domains.planning_reporting.partner_router import router as partner_planning_router
app.include_router(partner_planning_router)

from .domains.progress_monitoring.router import router as progress_monitoring_router
app.include_router(progress_monitoring_router)
from .domains.progress_monitoring.stage_router import router as progress_stage_schemes_router
app.include_router(progress_stage_schemes_router)
from .domains.progress_monitoring.source_evidence import router as progress_source_evidence_router
app.include_router(progress_source_evidence_router)
from .domains.progress_monitoring.p2c_source_readback import router as progress_p2c_source_router
app.include_router(progress_p2c_source_router)
from .domains.progress_monitoring.p2c2_link_router import router as progress_evidence_link_router
app.include_router(progress_evidence_link_router)
from .domains.progress_monitoring.p3c1d_verification_router import router as progress_quantity_verification_router
app.include_router(progress_quantity_verification_router)
from .domains.progress_monitoring.milestone_router import router as progress_milestone_preview_router
app.include_router(progress_milestone_preview_router)

from .domains.progress_monitoring.reports_router import router as progress_reports_router
app.include_router(progress_reports_router)

# Phase 6: historical verified captures and permission-scoped alert indicators.
from .domains.progress_monitoring.history_router import router as progress_history_router
app.include_router(progress_history_router)

from .domains.progress_monitoring.milestone_policy_router import router as progress_milestone_policy_router
app.include_router(progress_milestone_policy_router)

# Phase 31.1 financial cost and budget controls
from .domains.commercial_financials.router import router as financials_router
app.include_router(financials_router)

from .domains.contracts.router import router as contracts_router, partner as partner_contracts_router
app.include_router(contracts_router)
app.include_router(partner_contracts_router)

# Stores & Inventory ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Phase 1 warehouse/location master
from .domains.stores_inventory.router import router as stores_router
app.include_router(stores_router)

from .domains.stores_inventory.lot_reconciliation import router as stores_lot_reconciliation_router
app.include_router(stores_lot_reconciliation_router)

from .domains.stores_inventory.posting_lots import router as stores_posting_lots_router
app.include_router(stores_posting_lots_router)

from .domains.stores_inventory.lot_balance_review import router as stores_lot_balance_review_router
app.include_router(stores_lot_balance_review_router)

# Stores Phase 3: QA decision attribution to receipt lots (read/write evidence, no stock release).
from .domains.stores_inventory.lot_qa_attribution import router as stores_lot_qa_attribution_router
app.include_router(stores_lot_qa_attribution_router)

from .domains.stores_inventory.lot_outbound_exposure import router as stores_lot_outbound_exposure_router
app.include_router(stores_lot_outbound_exposure_router)

from .domains.stores_inventory.qa_issued_impact import router as stores_qa_issued_impact_router
app.include_router(stores_qa_issued_impact_router)

from .domains.stores_inventory.outbound_lot_allocations import router as stores_outbound_lot_allocations_router
app.include_router(stores_outbound_lot_allocations_router)

from .domains.stores_inventory.lot_movement_review import router as stores_lot_movement_review_router
app.include_router(stores_lot_movement_review_router)

from .domains.stores_inventory.lot_coverage_audit import router as stores_lot_coverage_audit_router
app.include_router(stores_lot_coverage_audit_router)

# Phase 3: strict warehouse/item lot reconciliation; read-only, no stock release.
from .domains.stores_inventory.lot_balance_gate import router as stores_lot_ledger_gate_router
app.include_router(stores_lot_ledger_gate_router)

# Stores Phase 4: request lifecycle (no physical inventory posting).
from .domains.stores_inventory.material_requests import router as stores_material_requests_router
app.include_router(stores_material_requests_router)

# Phase 4: contractor-scoped request submissions; review remains internal.
from .domains.partner_portal.material_issue_requests import router as partner_stores_issue_router
app.include_router(partner_stores_issue_router)

from .domains.stores_inventory.material_handovers import router as stores_material_handovers_router
app.include_router(stores_material_handovers_router)
from .domains.stores_inventory.material_returns import router as stores_material_returns_router
app.include_router(stores_material_returns_router)
from .domains.stores_inventory.return_work_package_trace import router as stores_return_construction_trace_router
app.include_router(stores_return_construction_trace_router)
from .domains.stores_inventory.phase5_operations import router as stores_phase5_operations_router
app.include_router(stores_phase5_operations_router)

# Stores Phase 5 CP14: source-linked approved Construction progress evidence (read-only).
from .domains.stores_inventory.construction_consumption_evidence import router as stores_construction_consumption_evidence_router
app.include_router(stores_construction_consumption_evidence_router)

from .domains.stores_inventory.construction_material_usage import router as stores_construction_material_usage_router
app.include_router(stores_construction_material_usage_router)

# Phase 5 CP17: read-only work-package material balance (not inventory valuation).
from .domains.stores_inventory.phase5_material_balance import router as stores_phase5_material_balance_router
app.include_router(stores_phase5_material_balance_router)
from .domains.stores_inventory.transfers import router as stores_phase6_transfers_router
app.include_router(stores_phase6_transfers_router)
from .domains.stores_inventory.transfer_posting_readiness import router as stores_phase6_transfer_posting_readiness_router
app.include_router(stores_phase6_transfer_posting_readiness_router)
from .domains.stores_inventory.transfer_qa_reconciliation import router as stores_phase6_transfer_qa_router
app.include_router(stores_phase6_transfer_qa_router)
from .domains.stores_inventory.transfer_monitor import router as stores_phase6_transfer_monitor_router
app.include_router(stores_phase6_transfer_monitor_router)

from .domains.stores_inventory.vendor_returns import router as stores_vendor_returns_router
app.include_router(stores_vendor_returns_router)

from .domains.stores_inventory.transfer_lot_eligibility import router as stores_phase6_transfer_eligibility_router
app.include_router(stores_phase6_transfer_eligibility_router)

# Phase 6 mixed GRN / transfer-derived provenance read model; never enables issuing.
from .domains.stores_inventory.mixed_lot_allocation import router as stores_mixed_lot_provenance_router
app.include_router(stores_mixed_lot_provenance_router)

# Phase 6 transfer-derived lot allocation preview (read-only, fail-closed).
from .domains.stores_inventory.transfer_allocation_preview import router as stores_transfer_allocation_preview_router
app.include_router(stores_transfer_allocation_preview_router)

from .domains.stores_inventory.transfer_reservation_activation import router as stores_transfer_reservation_activation_router
app.include_router(stores_transfer_reservation_activation_router)

from .domains.stores_inventory.transfer_reservation_release import router as stores_transfer_reservation_release_router
app.include_router(stores_transfer_reservation_release_router)

from .domains.stores_inventory.transfer_lot_issue import router as stores_transfer_lot_issue_router
app.include_router(stores_transfer_lot_issue_router)

from .domains.stores_inventory.preservation import router as stores_phase7_preservation_router
app.include_router(stores_phase7_preservation_router)

from .domains.stores_inventory.cycle_counts import router as stores_phase7_cycle_counts_router
app.include_router(stores_phase7_cycle_counts_router)

from .domains.stores_inventory.stock_adjustments import router as stores_phase7_adjustment_router
app.include_router(stores_phase7_adjustment_router)

from .domains.stores_inventory.scrap_disposal import router as stores_phase7_scrap_router
app.include_router(stores_phase7_scrap_router)

from .domains.stores_inventory.phase7_monitor import router as stores_phase7_monitor_router
app.include_router(stores_phase7_monitor_router)

# Phase 8: read-only Contracts free-issue linkage gaps; no stock/financial writes.
from .domains.stores_inventory.phase8_contract_readiness import router as stores_phase8_contract_readiness_router
app.include_router(stores_phase8_contract_readiness_router)
from .domains.stores_inventory.phase8_planning_readiness import router as stores_phase8_planning_readiness_router
app.include_router(stores_phase8_planning_readiness_router)

from .domains.stores_inventory.phase8_progress_evidence import router as stores_phase8_progress_evidence_router
app.include_router(stores_phase8_progress_evidence_router)

from .domains.stores_inventory.phase8_financial_reconciliation import router as stores_phase8_finance_router
app.include_router(stores_phase8_finance_router)

# Phase 8 checkpoint 6: reference-only audit (no stock or finance writes)
from .domains.stores_inventory.phase8_cross_module_audit import router as stores_phase8_cross_module_audit_router
app.include_router(stores_phase8_cross_module_audit_router)

# Finance-owned inventory costing policy (no ledger mutation).
from .domains.commercial_financials.inventory_costing_policy import router as inventory_costing_policy_router
app.include_router(inventory_costing_policy_router)

from .domains.commercial_financials.landed_cost_authority import router as landed_cost_authority_router
app.include_router(landed_cost_authority_router)

from .domains.commercial_financials.receipt_invoice_authority import router as receipt_invoice_authority_router
app.include_router(receipt_invoice_authority_router)

from .domains.commercial_financials.receipt_cost_authority import router as receipt_cost_authority_router
app.include_router(receipt_cost_authority_router)

# Read-only, authenticated Finance view of posted issue-to-receipt cost lineage.
from .domains.commercial_financials.movement_receipt_api import router as movement_receipt_api_router
app.include_router(movement_receipt_api_router)

from .domains.commercial_financials.movement_journal_proposals import router as movement_journal_proposals_router
app.include_router(movement_journal_proposals_router)
from .domains.commercial_financials.phase9_command_center_feed import router as phase9_finance_feed_router
app.include_router(phase9_finance_feed_router)
