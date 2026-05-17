"use client";

import type { ReactNode } from "react";

export function getStatusStyles(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes("high") || normalized.includes("fail")) {
    return {
      text: "text-[#9f2f24]",
      badge: "border-[#efc2ba] bg-[#fbebe8] text-[#9f2f24]",
      metricCard: "border-[#efc2ba] bg-[#fff6f4]",
      summaryCard: "border-[#efc2ba] bg-[#fffafa]",
    };
  }
  if (normalized.includes("review") || normalized.includes("running")) {
    return {
      text: "text-[#8a5b12]",
      badge: "border-[#e8d19b] bg-[#fff6dc] text-[#8a5b12]",
      metricCard: "border-[#e8d19b] bg-[#fffaf0]",
      summaryCard: "border-[#e8d19b] bg-[#fffdf8]",
    };
  }
  if (normalized.includes("ready") || normalized.includes("pass")) {
    return {
      text: "text-[#1f6b54]",
      badge: "border-[#b9ddcf] bg-[#eaf7f1] text-[#1f6b54]",
      metricCard: "border-[#b9ddcf] bg-[#f4fbf8]",
      summaryCard: "border-[#b9ddcf] bg-[#fbfffd]",
    };
  }
  return {
    text: "text-[#5f7374]",
    badge: "border-[#dce9e7] bg-[#f7fbfa] text-[#5f7374]",
    metricCard: "border-[#dce9e7] bg-[#f9fcfb]",
    summaryCard: "border-[#dce9e7] bg-white/86",
  };
}

export function StatusBadge({ status }: { status: string }) {
  const styles = getStatusStyles(status);
  return (
    <span className={`inline-flex items-center justify-center whitespace-nowrap rounded-full border px-3.5 py-1.5 text-xs font-semibold leading-none ${styles.badge}`}>
      {status}
    </span>
  );
}

export function SummaryMetric({
  label,
  value,
  detail,
  status,
  className = "",
  title,
  clamp = "line-clamp-2",
}: {
  label: string;
  value: string;
  detail?: string;
  status?: string;
  className?: string;
  title?: string;
  clamp?: string;
}) {
  const statusStyles = status ? getStatusStyles(status) : null;
  return (
    <div className={`flex h-full min-w-0 flex-col rounded-xl border p-4 ${statusStyles?.metricCard ?? "border-[#dce9e7] bg-[#f9fcfb]"} ${className}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#789093]">{label}</p>
      <p
        title={title ?? value}
        className={`mt-2 min-w-0 whitespace-normal break-words [word-break:break-word] text-lg font-semibold leading-6 ${clamp} ${statusStyles?.text ?? "text-[#17343c]"}`}
      >
        {value}
      </p>
      {detail ? <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#6f8584]">{detail}</p> : null}
    </div>
  );
}

export function SectionCard({ title, explainer, children }: { title: string; explainer: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-[#dce9e7] bg-white/82 p-6 shadow-[0_14px_36px_rgba(49,84,91,0.05)]">
      <h2 className="text-lg font-semibold text-[#17343c]">{title}</h2>
      <p className="mt-1 text-sm leading-6 text-[#607678]">{explainer}</p>
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function FriendlyEmpty({ title, text }: { title: string; text: string }) {
  return (
    <div className="mt-4 rounded-xl border border-dashed border-[#d8d0c4] bg-[#fffaf4] p-5">
      <p className="font-semibold text-[#34464a]">{title}</p>
      <p className="mt-2 text-sm leading-6 text-[#71817d]">{text}</p>
    </div>
  );
}

export function Disclosure({ title, open, onToggle, children }: { title: string; open: boolean; onToggle: () => void; children: ReactNode }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-[#dce9e7] bg-white/82 shadow-[0_12px_30px_rgba(49,84,91,0.045)]">
      <button type="button" onClick={onToggle} className="flex w-full items-center justify-between gap-5 px-6 py-5 text-left transition hover:bg-[#f4fbf9]">
        <span>
          <span className="block text-base font-semibold text-[#17343c]">{title}</span>
          <span className="mt-1 block text-xs font-medium uppercase tracking-[0.08em] text-[#789093]">{open ? "Expanded" : "Collapsed"}</span>
        </span>
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[#cfe4df] bg-[#edf7f5] text-lg font-semibold text-[#206b63] transition-transform ${
            open ? "rotate-45" : ""
          }`}
          aria-hidden="true"
        >
          +
        </span>
      </button>
      {open ? <div className="border-t border-[#e7efed] bg-[#fbfefd] p-6">{children}</div> : null}
    </section>
  );
}
