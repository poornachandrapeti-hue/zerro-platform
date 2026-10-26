import type { LucideIcon } from "lucide-react";
import { ArrowDown, ArrowLeft, ArrowRight, Award, BarChart3, FileCog, HardHat, PenTool, Star, TowerControl } from "lucide-react";

export type LifeModule = {
  id: string;
  title: string;
  detail: string;
  icon: LucideIcon;
  built: boolean;
  permissions: string[];
  adminOnly?: boolean;
  fullScope?: boolean;
  destination: string;
};

type Chip = { id: string; label: string; tone: "sky" | "mint" | "sand" | "peach" };
type Stage = {
  number: string;
  title: string;
  text: string;
  icon: LucideIcon;
  chips: Chip[];
  wide?: string;
};

const STAGES: Stage[] = [
  {
    number: "01",
    title: "SET UP & PLAN",
    text: "Lay the foundations for a successful project.",
    icon: FileCog,
    chips: [
      { id: "project", label: "Project Details", tone: "sky" },
      { id: "contracts", label: "Contracts", tone: "mint" },
      { id: "planning", label: "Planning", tone: "sand" },
    ],
  },
  {
    number: "02",
    title: "ENGINEER & CONTROL",
    text: "Turn designs into an executable plan with controlled information.",
    icon: PenTool,
    chips: [
      { id: "engineering", label: "Engineering & Drawing Management", tone: "sky" },
      { id: "documents", label: "Document Control & Correspondence", tone: "peach" },
    ],
  },
  {
    number: "03",
    title: "SOURCE & DELIVER",
    text: "Get the right materials and equipment to the right place at the right time.",
    icon: TowerControl,
    chips: [
      { id: "requests", label: "Requirements & Requests", tone: "sky" },
      { id: "procurement", label: "Procurement", tone: "peach" },
      { id: "stores", label: "Stores & Inventory", tone: "mint" },
      { id: "logistics", label: "Site Logistics", tone: "sky" },
    ],
  },
  {
    number: "06",
    title: "CERTIFY & HAND OVER",
    text: "Complete the project and deliver lasting value.",
    icon: Award,
    chips: [
      { id: "financials", label: "Financials", tone: "sky" },
      { id: "commissioning", label: "Commissioning, Completion & Handover", tone: "peach" },
    ],
  },
  {
    number: "05",
    title: "VERIFY & MEASURE",
    text: "Track performance, assure quality and demonstrate progress.",
    icon: BarChart3,
    chips: [
      { id: "quality", label: "Quality / QAQC", tone: "peach" },
      { id: "progress", label: "Progress & Reporting", tone: "mint" },
    ],
  },
  {
    number: "04",
    title: "PREPARE & EXECUTE",
    text: "Mobilise people, equipment and processes to build safely and deliver on plan.",
    icon: HardHat,
    chips: [
      { id: "hr", label: "HR", tone: "sky" },
      { id: "manpower", label: "Manpower", tone: "peach" },
      { id: "equipment", label: "Equipment & Tools", tone: "mint" },
      { id: "safety", label: "Safety / HSE", tone: "sky" },
    ],
    wide: "construction",
  },
];

const SUPPORT: { id: string; label: string; tone: string }[] = [
  { id: "administration", label: "Administration & Shared Services", tone: "support-blue" },
  { id: "risks", label: "Project Risks & Issues", tone: "support-orange" },
  { id: "change", label: "Change Management", tone: "support-green" },
  { id: "meetings", label: "Meetings & Actions", tone: "support-blue" },
];

export function Lifecycle({
  modules,
  shown,
  denied,
  favorite,
  onOpen,
  onFavorite,
}: {
  modules: Record<string, LifeModule>;
  shown: Set<string>;
  denied: Set<string>;
  favorite: (id: string) => boolean;
  onOpen: (item: LifeModule) => void;
  onFavorite: (id: string) => void;
}) {
  const top = STAGES.slice(0, 3);
  const bottom = STAGES.slice(3);
  return (
    <div className="life-sheet">
      <div className="life-flow">
        {top.map((stage, index) => (
          <StageCard
            key={stage.number}
            stage={stage}
            modules={modules}
            shown={shown}
            denied={denied}
            favorite={favorite}
            onOpen={onOpen}
            onFavorite={onFavorite}
            arrow={index < top.length - 1 ? "forward" : undefined}
          />
        ))}
        {bottom.map((stage, index) => (
          <StageCard
            key={stage.number}
            stage={stage}
            modules={modules}
            shown={shown}
            denied={denied}
            favorite={favorite}
            onOpen={onOpen}
            onFavorite={onFavorite}
            arrow={index < bottom.length - 1 ? "back" : undefined}
          />
        ))}
      </div>
      <section className="life-support">
        <div>
          <h2>CONTINUOUS PROJECT SUPPORT</h2>
          <p>Enabling collaboration, governance and continuous improvement across the entire lifecycle.</p>
        </div>
        <div className="life-support-row">
          {SUPPORT.filter((row) => shown.has(row.id)).map((row) => {
            const item = modules[row.id];
            if (!item) return null;
            const blocked = denied.has(row.id);
            return (
              <button
                key={row.id}
                type="button"
                className={`life-support-chip ${row.tone}${blocked ? " is-denied" : ""}`}
                disabled={blocked}
                title={blocked ? "No access for this role" : item.detail}
                onClick={() => onOpen(item)}
              >
                <span>
                  <item.icon size={22} strokeWidth={2.4} />
                </span>
                {row.label}
              </button>
            );
          })}
        </div>
      </section>
      <p className="life-note">Lifecycle grouping: Safety, Quality, Finance and reporting remain active throughout the project.</p>
    </div>
  );
}

function StageCard({
  stage,
  modules,
  shown,
  denied,
  favorite,
  onOpen,
  onFavorite,
  arrow,
}: {
  stage: Stage;
  modules: Record<string, LifeModule>;
  shown: Set<string>;
  denied: Set<string>;
  favorite: (id: string) => boolean;
  onOpen: (item: LifeModule) => void;
  onFavorite: (id: string) => void;
  arrow?: "forward" | "back";
}) {
  const chips = stage.chips.filter((chip) => shown.has(chip.id));
  const wide = stage.wide && shown.has(stage.wide) ? modules[stage.wide] : null;
  const Glyph = stage.icon;
  return (
    <>
      <article className={`life-stage${stage.number === "03" ? " life-down" : ""}`}>
        <header>
          <span className="life-num">{stage.number}</span>
          <span className="life-stage-icon">
            <Glyph size={32} strokeWidth={2.4} />
          </span>
          <div>
            <h3>{stage.title}</h3>
            <p>{stage.text}</p>
          </div>
        </header>
        <div className={`life-chips chips-${chips.length}`}>
          {chips.map((chip) => {
            const item = modules[chip.id];
            if (!item) return null;
            return (
              <ChipButton
                key={chip.id}
                label={chip.label}
                tone={chip.tone}
                item={item}
                denied={denied.has(chip.id)}
                favorite={favorite(chip.id)}
                onOpen={onOpen}
                onFavorite={onFavorite}
              />
            );
          })}
        </div>
        {wide ? (
          <ChipButton
            label="Construction"
            tone="peach"
            wide
            item={wide}
            denied={denied.has(wide.id)}
            favorite={favorite(wide.id)}
            onOpen={onOpen}
            onFavorite={onFavorite}
          />
        ) : null}
        {stage.number === "03" ? (
          <span className="life-drop" aria-hidden="true">
            <ArrowDown size={28} strokeWidth={2.6} />
          </span>
        ) : null}
      </article>
      {arrow ? (
        <div className={`life-arrow ${arrow}`} aria-hidden="true">
          {arrow === "forward" ? <ArrowRight size={28} strokeWidth={2.6} /> : <ArrowLeft size={28} strokeWidth={2.6} />}
        </div>
      ) : null}
    </>
  );
}

function ChipButton({
  label,
  tone,
  wide,
  item,
  denied,
  favorite,
  onOpen,
  onFavorite,
}: {
  label: string;
  tone: Chip["tone"];
  wide?: boolean;
  item: LifeModule;
  denied: boolean;
  favorite: boolean;
  onOpen: (item: LifeModule) => void;
  onFavorite: (id: string) => void;
}) {
  const Glyph = item.icon;
  return (
    <div className={`life-chip tone-${tone}${wide ? " is-wide" : ""}${denied ? " is-denied" : ""}`}>
      <button type="button" disabled={denied} title={denied ? "No access for this role" : item.detail} onClick={() => onOpen(item)}>
        <Glyph size={30} strokeWidth={2.4} />
        <span>{label}</span>
      </button>
      <button type="button" className={favorite ? "life-star on" : "life-star"} aria-label={`Favorite ${label}`} onClick={() => onFavorite(item.id)}>
        <Star size={16} strokeWidth={2.4} />
      </button>
    </div>
  );
}
