import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

const NAVY = "#1a2744";
const ORANGE = "#f5a018";

const navy = {
  stroke: NAVY,
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  fill: "none" as const,
};
const orange = { ...navy, stroke: ORANGE };

function Frame({ size = 22, children }: { size?: number; children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      {children}
    </svg>
  );
}

function asIcon(render: (size: number) => ReactNode): LucideIcon {
  return (({ size = 22 }: { size?: number }) => <>{render(size)}</>) as LucideIcon;
}

export const ProjectIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" {...navy} />
    <path d="M14 2v4a2 2 0 0 0 2 2h4" {...orange} />
    <path d="M10 9H8M16 13H8M16 17H8" {...navy} />
  </Frame>
));

export const GearIcon = asIcon((size) => (
  <Frame size={size}>
    <path
      d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
      {...navy}
    />
    <circle cx="12" cy="12" r="2.2" stroke={ORANGE} strokeWidth="2" fill={ORANGE} />
  </Frame>
));

export const PlanningIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="M8 2v4M16 2v4" {...navy} />
    <rect x="3" y="4" width="18" height="18" rx="2" {...navy} />
    <path d="M3 10h18" {...orange} />
  </Frame>
));

export const ProgressIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="M6 20v-6M12 20V9" {...navy} />
    <path d="M18 20V4" {...orange} />
  </Frame>
));

export const ProcurementIcon = asIcon((size) => (
  <Frame size={size}>
    <circle cx="8" cy="21" r="1" stroke={NAVY} strokeWidth="2" />
    <circle cx="19" cy="21" r="1" stroke={ORANGE} strokeWidth="2" fill={ORANGE} />
    <path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12" {...navy} />
  </Frame>
));

export const StoresIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z" {...navy} />
    <path d="M12 22V12M3.3 7l8.7 5 8.7-5" {...navy} />
    <path d="m3.3 7 8.7-4.7 8.7 4.7" {...orange} />
  </Frame>
));

export const ConstructionIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="M3 21h18M8 21V4.5" {...navy} />
    <path d="M8 5h13M19.5 5v6.2M17.2 11.2h4.2" {...orange} />
    <path d="M8 8.5h4" {...navy} />
  </Frame>
));

export const ManpowerIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" {...navy} />
    <circle cx="9" cy="7" r="4" {...navy} />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87" {...navy} />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" {...orange} />
  </Frame>
));

export const EquipmentIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" {...navy} />
    <circle cx="18.6" cy="5.4" r="1.7" stroke={ORANGE} strokeWidth="2" fill={ORANGE} />
  </Frame>
));

export const LogisticsIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2" {...navy} />
    <path d="M15 18H9" {...navy} />
    <path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14" {...orange} />
    <circle cx="17" cy="18" r="2" stroke={ORANGE} strokeWidth="2" />
    <circle cx="7" cy="18" r="2" {...navy} />
  </Frame>
));

export const QualityIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" {...navy} />
    <path d="m9 12 2 2 4-4" {...orange} />
  </Frame>
));

export const SafetyIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="M10 10V5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5" {...navy} />
    <path d="M14 6a6 6 0 0 1 6 6v3M4 15v-3a6 6 0 0 1 6-6" {...navy} />
    <path d="M2 18a1 1 0 0 0 1 1h18a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1z" {...orange} />
  </Frame>
));

export const CommissioningIcon = asIcon((size) => (
  <Frame size={size}>
    <rect x="8" y="2" width="8" height="4" rx="1" stroke={ORANGE} strokeWidth="2" />
    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" {...navy} />
    <path d="M12 11h4M12 16h4M8 11h.01M8 16h.01" {...navy} />
  </Frame>
));

export const FinancialsIcon = asIcon((size) => (
  <Frame size={size}>
    <ellipse cx="12" cy="6.5" rx="7" ry="2.5" {...navy} />
    <path d="M5 6.5v4.2c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V6.5" {...navy} />
    <path d="M5 10.7v4.2c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-4.2" {...orange} />
  </Frame>
));

export const ContractsIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" {...navy} />
    <path d="M14 2v4a2 2 0 0 0 2 2h4" {...navy} />
    <path d="M8 13h5" {...navy} />
    <circle cx="15.5" cy="16.5" r="2" stroke={ORANGE} strokeWidth="2" />
  </Frame>
));

export const HrIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" {...navy} />
    <circle cx="12" cy="7" r="4" stroke={ORANGE} strokeWidth="2" />
  </Frame>
));

export const RequestsIcon = asIcon((size) => (
  <Frame size={size}>
    <rect x="8" y="2" width="8" height="4" rx="1" {...navy} />
    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" {...navy} />
    <path d="M12 11h4M12 16h4" {...navy} />
    <path d="M8 11h.01M8 16h.01" {...orange} />
  </Frame>
));

export const DocumentsIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" {...navy} />
    <path d="M9.6 3.9 11.2 6H4.2" {...orange} />
  </Frame>
));

export const RisksIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" {...navy} />
    <path d="M12 9v4M12 17h.01" {...orange} />
  </Frame>
));

export const ChangeIcon = asIcon((size) => (
  <Frame size={size}>
    <path d="m16 3 4 4-4 4M20 7H4" {...navy} />
    <path d="m8 21-4-4 4-4M4 17h16" {...orange} />
  </Frame>
));

export const MeetingsIcon = ManpowerIcon;

export const AdminIcon = GearIcon;
