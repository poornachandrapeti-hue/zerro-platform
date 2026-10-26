import { CraneIcon, BlueprintIcon, CoinStackIcon } from "./designIcons";
import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  Award,
  BarChart3,
  CalendarDays,
  ClipboardCheck,
  ClipboardList,
  Coins,
  FileCog,
  FileText,
  Handshake,
  HardHat,
  Package,
  PenTool,
  RefreshCw,
  Settings,
  Shield,
  ShoppingCart,
  TowerControl,
  Truck,
  UserRound,
  Users,
  Wrench,
} from "lucide-react";

export type TileTone = "blue" | "peach" | "green";

export type TileDef = {
  id: string;
  label: string;
  tone: TileTone;
  icon: LucideIcon;
  wide?: boolean;
};

export type StageDef = {
  number: "01" | "02" | "03" | "04" | "05" | "06";
  title: string;
  text: string;
  icon: LucideIcon;
  columns: 2 | 3;
  tiles: TileDef[];
};

export const STAGES: StageDef[] = [
  {
    number: "01",
    title: "SET UP & PLAN",
    text: "Lay the foundations for a successful project.",
    icon: FileCog,
    columns: 3,
    tiles: [
      { id: "project", label: "Project Details", tone: "blue", icon: FileText },
      { id: "contracts", label: "Contracts", tone: "peach", icon: Handshake },
      { id: "planning", label: "Planning", tone: "green", icon: CalendarDays },
    ],
  },
  {
    number: "02",
    title: "ENGINEER & CONTROL",
    text: "Turn designs into an executable plan with controlled information.",
    icon: BlueprintIcon,
    columns: 2,
    tiles: [
      { id: "engineering", label: "Engineering & Drawing Management", tone: "blue", icon: Settings },
      { id: "documents", label: "Document Control & Correspondence", tone: "peach", icon: FileText },
    ],
  },
  {
    number: "03",
    title: "SOURCE & DELIVER",
    text: "Get the right materials and equipment to the right place at the right time.",
    icon: CraneIcon,
    columns: 2,
    tiles: [
      { id: "requests", label: "Requirements & Requests", tone: "blue", icon: ClipboardList },
      { id: "procurement", label: "Procurement", tone: "peach", icon: ShoppingCart },
      { id: "stores", label: "Stores & Inventory", tone: "green", icon: Package },
      { id: "logistics", label: "Site Logistics", tone: "blue", icon: Truck },
    ],
  },
  {
    number: "06",
    title: "CERTIFY & HAND OVER",
    text: "Complete the project and deliver lasting value.",
    icon: Award,
    columns: 2,
    tiles: [
      { id: "financials", label: "Financials", tone: "blue", icon: CoinStackIcon },
      { id: "commissioning", label: "Commissioning, Completion & Handover", tone: "green", icon: ClipboardCheck },
    ],
  },
  {
    number: "05",
    title: "VERIFY & MEASURE",
    text: "Track performance, assure quality and demonstrate progress.",
    icon: BarChart3,
    columns: 2,
    tiles: [
      { id: "quality", label: "Quality / QAQC", tone: "peach", icon: Award },
      { id: "progress", label: "Progress & Reporting", tone: "green", icon: BarChart3 },
    ],
  },
  {
    number: "04",
    title: "PREPARE & EXECUTE",
    text: "Mobilise people, equipment and processes to build safely and deliver on plan.",
    icon: HardHat,
    columns: 2,
    tiles: [
      { id: "hr", label: "HR", tone: "blue", icon: Users },
      { id: "manpower", label: "Manpower", tone: "peach", icon: UserRound },
      { id: "equipment", label: "Equipment & Tools", tone: "green", icon: Wrench },
      { id: "safety", label: "Safety / HSE", tone: "blue", icon: Shield },
      { id: "construction", label: "Construction", tone: "peach", icon: CraneIcon, wide: true },
    ],
  },
];

export const SUPPORT: { id: string; label: string; icon: LucideIcon }[] = [
  { id: "administration", label: "Administration & Shared Services", icon: Users },
  { id: "risks", label: "Project Risks & Issues", icon: AlertTriangle },
  { id: "change", label: "Change Management", icon: RefreshCw },
  { id: "meetings", label: "Meetings & Actions", icon: Users },
];
