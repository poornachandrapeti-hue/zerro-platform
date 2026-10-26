import { FormEvent, useEffect, useState } from "react";
import { api } from "./api";
import type { Discipline } from "./types";

type Member = { user_id: number; name: string; active?: boolean };
type ProjectRow = { id: number; code: string; name: string };
type SavedPolicy = {
    id: number;
    discipline_id: number | null;
    policy_version: number;
    stages: {
        name: string;
        rule?: string;
        quorum_count?: number;
        reviewers: { id: number; name: string; approval_limit?: number | null }[];
    }[];
};
type LevelReviewer = { user_id: number; approval_limit: string };
type Level = { name: string; rule: "all" | "quorum"; quorum_count: number; reviewers: LevelReviewer[] };

const RECORD_TYPES: [string, string][] = [
    ["project.activation", "Project activation"],
    ["procurement.requirement", "Procurement – Material requirement"],
    ["procurement.requisition", "Procurement – Purchase requisition"],
    ["procurement.purchase_order", "Procurement – Purchase order"],
    ["construction.release", "Construction – Work release"],
    ["construction.progress", "Construction – Daily progress"],
    ["construction.handover", "Construction – Handover"],
    ["quality.inspection", "Quality – Inspection offer"],
    ["quality.document", "Quality – Plan / ITP"],
    ["quality.template", "Quality – Discipline template"],
    ["quality.material", "Quality – Material inspection"],
    ["quality.construction", "Quality – Construction inspection"],
    ["quality.ncr", "Quality – NCR"],
    ["quality.ncr.close", "Quality – NCR closure"],
    ["quality.concession", "Quality – Concession"],
    ["quality.hold", "Quality – Hold release"],
    ["quality.qualification", "Quality – Qualification"],
    ["quality.calibration", "Quality – Calibration"],
    ["quality.dossier", "Quality – Dossier"],
    ["quality.punch.close", "Quality – Punch closure"],
    ["hse.document", "HSE – Document"],
    ["hse.assessment", "HSE – Risk assessment"],
    ["hse.permit", "HSE – Permit"],
    ["hse.incident", "HSE – Incident closure"],
    ["hse.hold", "HSE – Safety hold release"],
    ["hr.deployment", "HR – Deployment"],
    ["hr.request", "HR / Manpower – Workforce demand"],
    ["hr.attendance", "HR – Attendance"],
    ["hr.correction", "HR – Attendance correction"],
    ["hr.leave", "HR – Leave"],
    ["hr.overtime", "HR – Overtime"],
    ["hr.offboarding", "HR – Demobilization"],
];
const LIMIT_TYPES = new Set(["procurement.requisition", "procurement.purchase_order"]);
const emptyLevel = (n: number): Level => ({
    name: `Level ${n}`,
    rule: "all",
    quorum_count: 1,
    reviewers: [{ user_id: 0, approval_limit: "" }],
});

export type RouteShape = {
    discipline_id: number | null;
    stages: { reviewers: { id: number; approval_limit?: number | null }[] }[];
};
export type ApprovalTarget = { projectId: number; recordType: string; disciplineId: number | null };

export const OPEN_APPROVAL_LEVELS = "open-approval-levels";

// `capacity` is how many reviewers the module's own editor can set on each stage.
export function routeLocked(rows: RouteShape[] | undefined, disciplineId: number | null, capacity: number[] = [1]) {
    const row = (rows || []).find((item) => (item.discipline_id ?? null) === disciplineId);
    if (!row) return false;
    return (
        row.stages.length > capacity.length ||
        row.stages.some(
            (stage, i) =>
                stage.reviewers.length > capacity[i] || stage.reviewers.some((r) => r.approval_limit != null),
        )
    );
}

export function useSavedRoutes(pid: number, recordType: string, enabled: boolean) {
    const [rows, setRows] = useState<RouteShape[]>([]);
    useEffect(() => {
        if (!enabled || !pid) return;
        api<RouteShape[]>(`/projects/${pid}/approval-policies?record_type=${recordType}`)
            .then(setRows)
            .catch(() => setRows([]));
    }, [pid, recordType, enabled]);
    return rows;
}

export function RouteLockNotice({ target }: { target: ApprovalTarget }) {
    return (
        <p className="muted" role="note">
            This route has more than one level, more than one reviewer, or an approval limit. Saving here would replace it
            with a single reviewer, so it is managed on Approval levels.{" "}
            <button
                type="button"
                onClick={() => window.dispatchEvent(new CustomEvent<ApprovalTarget>(OPEN_APPROVAL_LEVELS, { detail: target }))}
            >
                Open Approval levels
            </button>
        </p>
    );
}

export function ApprovalLevelsPage({ disciplines, initial }: { disciplines: Discipline[]; initial?: ApprovalTarget | null }) {
    const [projects, setProjects] = useState<ProjectRow[]>([]);
    const [pid, setPid] = useState(0);
    const [recordType, setRecordType] = useState(
        initial && RECORD_TYPES.some(([value]) => value === initial.recordType) ? initial.recordType : RECORD_TYPES[0][0],
    );
    const [discipline, setDiscipline] = useState(initial?.disciplineId || 0);
    const [members, setMembers] = useState<Member[]>([]);
    const [saved, setSaved] = useState<SavedPolicy[]>([]);
    const [levels, setLevels] = useState<Level[]>([emptyLevel(1)]);
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [tick, setTick] = useState(0);

    useEffect(() => {
        api<{ items: ProjectRow[] }>("/projects?offset=0&limit=100")
            .then((r) => {
                setProjects(r.items);
                const wanted = r.items.find((p) => p.id === initial?.projectId);
                if (wanted || r.items[0]) setPid((wanted || r.items[0]).id);
            })
            .catch((e) => setError((e as Error).message));
    }, []);

    useEffect(() => {
        if (!pid) return;
        api<Member[]>(`/projects/${pid}/memberships`)
            .then((rows) => {
                const seen = new Set<number>();
                setMembers(rows.filter((m) => m.active !== false && !seen.has(m.user_id) && seen.add(m.user_id)));
            })
            .catch((e) => setError((e as Error).message));
    }, [pid]);

    useEffect(() => {
        if (!pid) return;
        api<SavedPolicy[]>(`/projects/${pid}/approval-policies?record_type=${recordType}`)
            .then((rows) => {
                setSaved(rows);
                const current = rows.find((row) => (row.discipline_id || 0) === discipline);
                setLevels(
                    current
                        ? current.stages.map((stage) => ({
                            name: stage.name,
                            rule: stage.rule === "quorum" ? "quorum" : "all",
                            quorum_count: stage.quorum_count || 1,
                            reviewers: stage.reviewers.map((r) => ({
                                user_id: r.id,
                                approval_limit: r.approval_limit == null ? "" : String(r.approval_limit),
                            })),
                        }))
                        : [emptyLevel(1)],
                );
            })
            .catch((e) => setError((e as Error).message));
    }, [pid, recordType, discipline, tick]);

    function change(index: number, patch: Partial<Level>) {
        setLevels((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
    }
    function changeReviewer(index: number, rIndex: number, patch: Partial<LevelReviewer>) {
        change(index, {
            reviewers: levels[index].reviewers.map((r, i) => (i === rIndex ? { ...r, ...patch } : r)),
        });
    }

    async function save(e: FormEvent) {
        e.preventDefault();
        setError("");
        setNotice("");
        try {
            await api(`/projects/${pid}/approval-policies`, "POST", {
                record_type: recordType,
                company_id: null,
                discipline_id: discipline || null,
                allow_self_approval: false,
                stages: levels.map((level) => {
                    const reviewers = level.reviewers.filter((r) => r.user_id > 0);
                    return {
                        name: level.name.trim() || "Level",
                        rule: level.rule,
                        quorum_count: level.rule === "quorum" ? level.quorum_count : reviewers.length,
                        reviewer_ids: [],
                        reviewers: reviewers.map((r) => ({
                            user_id: r.user_id,
                            approval_limit:
                                LIMIT_TYPES.has(recordType) && r.approval_limit !== "" ? Number(r.approval_limit) : null,
                        })),
                        purpose: "",
                    };
                }),
            });
            setNotice("Approval levels saved. New submissions use this route. Reviews already in progress keep their old route.");
            setTick((t) => t + 1);
        } catch (err) {
            setError((err as Error).message);
        }
    }

    return (
        <section className="panel">
            <h2>Approval levels</h2>
            <p className="muted">
                Levels run in order: level 2 opens only after level 1 is complete. "All" needs every reviewer on the level;
                "Quorum" needs the number you set. Nobody approves their own submission. An organization administrator can
                approve any level, and that approval completes the level. Drawing routes stay on the Engineering screen.
            </p>
            <div className="inline">
                <label>
                    Project{" "}
                    <select value={pid} onChange={(e) => setPid(Number(e.target.value))}>
                        {projects.map((p) => (
                            <option key={p.id} value={p.id}>
                                {p.code} — {p.name}
                            </option>
                        ))}
                    </select>
                </label>
                <label>
                    Record{" "}
                    <select value={recordType} onChange={(e) => setRecordType(e.target.value)}>
                        {RECORD_TYPES.map(([value, label]) => (
                            <option key={value} value={value}>
                                {label}
                            </option>
                        ))}
                    </select>
                </label>
                <label>
                    Discipline{" "}
                    <select value={discipline} onChange={(e) => setDiscipline(Number(e.target.value))}>
                        <option value={0}>All disciplines</option>
                        {disciplines.map((d) => (
                            <option key={d.id} value={d.id}>
                                {d.name}
                            </option>
                        ))}
                    </select>
                </label>
            </div>
            <p className="muted">
                Saved:{" "}
                {saved.length
                    ? saved
                        .map(
                            (row) =>
                                `${disciplines.find((d) => d.id === row.discipline_id)?.name || "All disciplines"} (v${row.policy_version}): ${row.stages.length} level(s)`,
                        )
                        .join("; ")
                    : "Not set"}
            </p>
            <form onSubmit={save}>
                {levels.map((level, index) => (
                    <fieldset key={index} className="panel">
                        <legend>Level {index + 1}</legend>
                        <div className="inline">
                            <label>
                                Name <input value={level.name} onChange={(e) => change(index, { name: e.target.value })} />
                            </label>
                            <label>
                                Rule{" "}
                                <select
                                    value={level.rule}
                                    onChange={(e) => change(index, { rule: e.target.value === "quorum" ? "quorum" : "all" })}
                                >
                                    <option value="all">All must approve</option>
                                    <option value="quorum">Quorum</option>
                                </select>
                            </label>
                            {level.rule === "quorum" ? (
                                <label>
                                    Approvals needed{" "}
                                    <input
                                        type="number"
                                        min={1}
                                        max={level.reviewers.length}
                                        value={level.quorum_count}
                                        onChange={(e) => change(index, { quorum_count: Number(e.target.value) })}
                                    />
                                </label>
                            ) : null}
                            {levels.length > 1 ? (
                                <button type="button" onClick={() => setLevels((rows) => rows.filter((_, i) => i !== index))}>
                                    Remove level
                                </button>
                            ) : null}
                        </div>
                        {level.reviewers.map((reviewer, rIndex) => (
                            <div className="inline" key={rIndex}>
                                <select
                                    value={reviewer.user_id}
                                    onChange={(e) => changeReviewer(index, rIndex, { user_id: Number(e.target.value) })}
                                >
                                    <option value={0}>Choose reviewer</option>
                                    {members.map((m) => (
                                        <option key={m.user_id} value={m.user_id}>
                                            {m.name}
                                        </option>
                                    ))}
                                </select>
                                {LIMIT_TYPES.has(recordType) ? (
                                    <input
                                        type="number"
                                        min={0}
                                        placeholder="Approval limit (blank = no limit)"
                                        value={reviewer.approval_limit}
                                        onChange={(e) => changeReviewer(index, rIndex, { approval_limit: e.target.value })}
                                    />
                                ) : null}
                                {level.reviewers.length > 1 ? (
                                    <button
                                        type="button"
                                        onClick={() => change(index, { reviewers: level.reviewers.filter((_, i) => i !== rIndex) })}
                                    >
                                        Remove
                                    </button>
                                ) : null}
                            </div>
                        ))}
                        <button
                            type="button"
                            onClick={() => change(index, { reviewers: [...level.reviewers, { user_id: 0, approval_limit: "" }] })}
                        >
                            Add reviewer
                        </button>
                    </fieldset>
                ))}
                <div className="inline">
                    <button type="button" onClick={() => setLevels((rows) => [...rows, emptyLevel(rows.length + 1)])}>
                        Add level
                    </button>
                    <button className="primary" disabled={!pid}>
                        Save approval levels
                    </button>
                </div>
            </form>
            {error ? (
                <div role="alert" className="error">
                    {error}
                </div>
            ) : null}
            {notice ? <p className="muted">{notice}</p> : null}
        </section>
    );
}