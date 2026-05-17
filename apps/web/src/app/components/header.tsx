"use client";

export function ProductHeader({ onStartReview }: { onStartReview: () => void }) {
  return (
    <header className="border-b border-[#dce9e7] bg-gradient-to-br from-[#f7fbfa] via-[#fffdfa] to-[#eef7f5]">
      <div className="mx-auto max-w-7xl px-5 py-10">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_380px] lg:items-center">
          <div>
            <p className="text-sm font-semibold text-[#2d7772]">Clinical operations review</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-normal text-[#17343c] md:text-5xl">AI Clinical Ops Agent</h1>
            <p className="mt-3 text-xl font-medium text-[#31545b]">Operative note review for billing teams.</p>
            <p className="mt-4 max-w-3xl text-base leading-7 text-[#5d7375]">
              Identify procedures, surface documentation risks, and prepare coder review next steps from operative notes.
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
              <button
                type="button"
                onClick={onStartReview}
                className="h-12 rounded-xl bg-[#206b63] px-5 text-sm font-semibold text-white shadow-[0_12px_26px_rgba(32,107,99,0.18)] hover:bg-[#195950]"
              >
                Start review
              </button>
              <p className="text-sm text-[#6f8584]">Human review required before billing decisions.</p>
            </div>
            <p className="mt-5 max-w-3xl rounded-2xl border border-[#dce9e7] bg-white/65 px-4 py-3 text-sm leading-6 text-[#617879]">
              Use only de-identified or synthetic notes. Human review is required before billing decisions.
            </p>
          </div>
          <div className="rounded-3xl border border-[#d8e8e4] bg-white/78 p-6 shadow-[0_20px_48px_rgba(49,84,91,0.08)]">
            <p className="text-sm font-semibold text-[#17343c]">Review workflow</p>
            <div className="mt-5 space-y-4">
              <HeroStep number="01" title="Add note" text="Paste an operative note or choose an included example." />
              <HeroStep number="02" title="Analyze" text="Run structured checks and AI-assisted interpretation when needed." />
              <HeroStep number="03" title="Review" text="Use the summary to decide what a coder should verify next." />
            </div>
          </div>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <ValueCard title="Identify the procedure" text="Summarize what operation the note appears to describe." />
          <ValueCard title="Flag documentation risks" text="Surface missing details, ambiguity, and billing-review concerns." />
          <ValueCard title="Prepare reviewer next steps" text="Explain what a human coder or billing reviewer should verify." />
        </div>
      </div>
    </header>
  );
}

export function WorkflowSteps() {
  const steps = [
    ["Step 1", "Add note"],
    ["Step 2", "Analyze"],
    ["Step 3", "Review"],
  ];
  return (
    <section className="rounded-2xl border border-[#dce9e7] bg-white/80 p-3 shadow-[0_12px_32px_rgba(49,84,91,0.04)]">
      <div className="grid gap-2 md:grid-cols-3">
        {steps.map(([label, text]) => (
          <div key={label} className="flex items-center gap-3 rounded-xl px-3 py-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#e6f3f1] text-sm font-semibold text-[#206b63]">
              {label.replace("Step ", "")}
            </span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#789093]">{label}</p>
              <p className="mt-0.5 text-sm font-semibold text-[#31545b]">{text}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function HeroStep({ number, title, text }: { number: string; title: string; text: string }) {
  return (
    <div className="flex gap-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#e6f3f1] text-xs font-semibold text-[#206b63]">{number}</span>
      <div>
        <p className="text-sm font-semibold text-[#17343c]">{title}</p>
        <p className="mt-1 text-sm leading-6 text-[#6b7f80]">{text}</p>
      </div>
    </div>
  );
}

function ValueCard({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl border border-[#dce9e7] bg-white/75 p-5 shadow-[0_10px_28px_rgba(49,84,91,0.04)]">
      <h2 className="text-sm font-semibold text-[#17343c]">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-[#607678]">{text}</p>
    </div>
  );
}
