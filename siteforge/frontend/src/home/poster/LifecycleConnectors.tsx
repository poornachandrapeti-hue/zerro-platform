import { ArrowLeft, ArrowRight } from "lucide-react";

export function LifecycleConnectors() {
  return (
    <>
      <span className="zb-arrow zb-a12" aria-hidden="true">
        <ArrowRight />
      </span>
      <span className="zb-arrow zb-a23" aria-hidden="true">
        <ArrowRight />
      </span>
      <span className="zb-arrow zb-a54" aria-hidden="true">
        <ArrowLeft />
      </span>
      <span className="zb-arrow zb-a65" aria-hidden="true">
        <ArrowLeft />
      </span>
      <span className="zb-curve" aria-hidden="true">
        <svg viewBox="0 0 48 180" preserveAspectRatio="none">
          <path
            d="M14 8 H28 Q40 8 40 22 V132 Q40 158 18 158"
            fill="none"
            stroke="currentColor"
            strokeWidth="4"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
          <path d="M30 148 L12 160 L32 168" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        </svg>
      </span>
    </>
  );
}
