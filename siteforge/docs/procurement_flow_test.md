# ZerroBuild — Procurement Flow Test (FLOW-01)

Project: **FLOW-01 · Flow Test Plant**
Purpose: walk one material requirement through every Procurement tab, from requirement to vendor invoice.

---

## 1. Who does what

| Person | Login | Role on FLOW-01 | Does in this test |
|---|---|---|---|
| Deepa Nair | deepa.site@yourcompany.com | Site Engineer | Raises requirements |
| Anita Desai | anita.head@yourcompany.com | Discipline Head | Approves requirement, requisition, quotation technical review, purchase order |
| Project Administrator | admin@yourcompany.com | Organization admin | Buyer and stores: requisition, RFQ, purchase order, receipt, stock, invoice |

- Use your existing passwords.
- Each browser tab keeps its own login. Keep Deepa, Anita and Admin open in three tabs.
- Nobody can approve their own submission. Admin cannot approve in place of Anita.
- Optional: assign sekhar the **Procurement Officer** role and Karan the **Stores Officer** role, and they can replace Admin.

## 2. Already set up (no action)

| Item | Value |
|---|---|
| Item | CBL-01 Cable 4C x 16 · Electrical · unit m |
| Vendors (approved) | FLOW-V1, 02 |
| Warehouse | WH-01 |
| Review routes | Requirement, requisition and purchase order → Anita Desai |

Where to approve: **Home → My approvals**, or open the record and use the review box.

---

## 3. Main flow

### Step 1 — Requirement
**Deepa** · Procurement → Requirements → New requirement

| Field | Value |
|---|---|
| Number | REQ-T01 |
| Company | Your Company |
| Discipline | Electrical |
| Requested by | Deepa Nair |
| Required at site | 2026-11-15 |
| Priority | High |
| Purpose | Cable for MCC panel feeders |
| Item / Quantity | CBL-01 / 100 m |

1. **Deepa:** Create requirement → Submit for review.
2. **Anita:** My approvals → REQ-T01 → Approve.

**Expected:** REQ-T01 is Approved.

### Step 2 — Approved Purchase Needs and requisition
**Admin** · Procurement → Approved Purchase Needs

**Expected:** REQ-T01 is listed with 100 remaining to buy.

Click **Check stock and raise requisition**, then fill the PR form:

| Field | Value |
|---|---|
| PR number | PR-T01 |
| Request date | today |
| Required delivery | 2026-11-10 |
| Justification | Uncovered quantity for REQ-T01 |

1. **Admin:** Create draft requisition.
2. **Admin:** Requisitions → PR-T01 → Submit for review.
3. **Anita:** My approvals → PR-T01 → Approve.

**Expected:** PR-T01 is Approved. Approved Purchase Needs shows 0 remaining for REQ-T01.

### Step 3 — Quotation (RFQ)
**Admin** · Procurement → Quotations → New RFQ

| Field | Value |
|---|---|
| RFQ number | RFQ-T01 |
| Approved requisition | PR-T01 |
| Quotation due date | 2026-10-20 |
| Delivery location | FLOW-01 site store |
| Technical requirements | IS 1554, 1.1 kV, armoured |
| Commercial requirements | 30 days credit |
| Vendors | FLOW-V1, 02 |
| Quantity | 100 |

1. **Admin:** Save draft RFQ → Issue RFQ.
2. **Admin:** Record quotation, once per vendor:

| Vendor | Reference | Quotation date | Validity | Currency | Unit price |
|---|---|---|---|---|---|
| FLOW-V1 | Q-FV1-001 | today | 2026-11-30 | INR | 450 |
| 02 | Q-02-001 | today | 2026-11-30 | INR | 420 |

3. **Admin:** Start technical review.
4. **Anita:** Procurement → Quotations → RFQ-T01 → **Compliant** on both quotations.
5. **Admin:** Commercial comparison — currency INR, rate date today, rate 1, note "Both compliant" → Save comparison.
6. **Admin:** Award — 100 to FLOW-V1, reason "Better delivery time" → Record award.

**Expected:** RFQ-T01 is Awarded. The lowest price is not selected automatically.

### Step 4 — Purchase order
**Admin** · Procurement → Purchase orders → New purchase order

| Field | Value |
|---|---|
| Order number | PO-T01 |
| Awarded vendor | RFQ-T01 · FLOW-V1 |
| Promised date | 2026-11-05 |
| Delivery location | FLOW-01 site store |
| Terms | 30 days credit |
| Quantity | 100 |

1. **Admin:** Save draft order → Submit for approval.
2. **Anita:** My approvals → PO-T01 → Approve.
3. **Admin:** Issue order → Record acknowledgement "Vendor confirmed by email".

**Expected:** PO-T01 is Acknowledged.

### Step 5 — Goods receipt
**Admin** · Procurement → Goods receipts → New goods receipt

| Receipt | Purchase order | Date | Delivery note | Warehouse | Quantity | Expected |
|---|---|---|---|---|---|---|
| GRN-T01 | PO-T01 | today | DN-5501 | WH-01 | 60 | PO Partially Received |
| GRN-T02 | PO-T01 | today | DN-5502 | WH-01 | 40 | PO Received |

### Step 6 — Stock
**Admin** · Procurement → Stock → Record movement

| Action | Number | Details | Expected |
|---|---|---|---|
| Accept | ACC-T01 | WH-01 · GRN-T01 · 60 | On hand +60 |
| Accept | ACC-T02 | WH-01 · GRN-T02 · 40 | On hand +40 |
| Reserve | RES-T01 | WH-01 · CBL-01 · 10 · "Hold for MCC-2" | Reserved 10 |
| Issue | ISS-T01 | WH-01 · CBL-01 · 20 · recipient Deepa Nair · "MCC-1 feeders" | On hand −20 |
| Return | RET-T01 | ISS-T01 · 5 · "Excess cut length" | On hand +5 |

**Expected:** for CBL-01 in WH-01, on hand rises by 85 and available by 75, added to any stock already there. A goods receipt alone does not add stock.

### Step 7 — Vendor invoice
**Admin** · Procurement → Invoices → New vendor invoice

| Field | Value |
|---|---|
| Invoice number | INV-T01 |
| Supplier invoice number | FV1/2026/118 |
| Invoice date | today |
| Purchase order | PO-T01 |
| Billed quantity / price | 100 / 450 |
| Note | Full supply |

1. **Admin:** Save draft → Record bill.

**Expected:** ordered 100, received 100 and billed 100 are shown together. Matching and payment are not open.

---

## 4. Extra test — stock is used before buying

1. **Deepa:** raise REQ-T02 — CBL-01, 120 m, purpose "Cable for DB-3", required 2026-11-25 → Submit for review.
2. **Anita:** Approve REQ-T02.
3. **Admin:** Approved Purchase Needs → REQ-T02 → Check stock and raise requisition.
   - **Expected:** free stock in WH-01 is shown (about 75 from Step 6).
4. **Admin:** Allocate free stock first.
   - **Expected:** remaining to buy drops to about 45.
5. **Admin:** create PR-T02.
   - **Expected:** the requisition is only for the remaining quantity, not 120.

## 5. Negative checks

| Check | How | Expected |
|---|---|---|
| Self-approval blocked | Anita creates and submits her own requirement | No Approve button for Anita on it |
| Return for correction | Anita types a reason and clicks Return on REQ-T02 | Deepa gets a task, corrects it, clicks Resubmit |
| Admin has no approval bypass | Admin opens a record waiting for Anita | No Approve button for Admin |

## 6. Result sheet

| # | Step | Pass / Fail | Notes |
|---|---|---|---|
| 1 | Requirement REQ-T01 approved | | |
| 2 | PR-T01 created from Purchase Needs and approved | | |
| 3 | RFQ-T01 issued, quoted, technically reviewed, awarded | | |
| 4 | PO-T01 approved, issued, acknowledged | | |
| 5 | GRN-T01 partial, GRN-T02 full | | |
| 6 | Stock accept, reserve, issue, return | | |
| 7 | INV-T01 recorded | | |
| 8 | REQ-T02 allocation and PR-T02 for remainder | | |
| 9 | Negative checks | | |

---

The "-T" numbers mark test records. They are real records on FLOW-01; cancel them afterwards if you do not want them in reports.
