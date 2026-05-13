"use client";

import { useEffect, useMemo, useState } from "react";

type EvidenceSnippet = {
  source: string;
  snippet: string;
  score?: number | null;
};

type ExtractedProcedure = {
  name: string;
  evidence: string;
  confidence: number;
  body_site?: string | null;
  approach?: string | null;
  laterality?: string | null;
};

type CPTCodeCandidate = {
  procedure_name: string;
  code: string;
  description: string;
  modifiers: string[];
  rationale: string;
  confidence: number;
  supported_by_docs: boolean;
  evidence_used: EvidenceSnippet[];
};

type AuditFinding = {
  title?: string | null;
  severity: string;
  category: string;
  message: string;
  explanation?: string | null;
  related_code?: string | null;
  recommendation: string;
  suggested_action?: string | null;
  documentation_improvement?: string | null;
  why_it_matters?: string | null;
  evidence_used: EvidenceSnippet[];
};

type ReimbursementEstimate = {
  code: string;
  allowed_amount: number;
  currency: string;
  source: string;
};

type StructuredOperativeNote = {
  raw_text: string;
  parsed_sections: Record<string, string>;
  detected_procedure_name?: string | null;
  detected_anatomy?: string | null;
  detected_laterality?: string | null;
  missing_sections: string[];
  parsing_confidence: number;
  structure_quality: string;
};

type AnalysisReport = {
  id: string;
  summary: string;
  structured_note?: StructuredOperativeNote | null;
  extracted_procedures: ExtractedProcedure[];
  cpt_candidates: CPTCodeCandidate[];
  audit_findings: AuditFinding[];
  reimbursement_estimates: ReimbursementEstimate[];
  total_estimated_reimbursement: number;
  report: {
    claim_readiness_score: number;
    claim_readiness_status: string;
    claim_readiness_explanation: string;
    claim_readiness_reasons?: string[];
    recommended_action?: string;
    main_issue?: string;
    analysis_mode?: string;
    ai_assist_status?: string;
    audit_issue_count: number;
    procedure_count: number;
    total_estimated_reimbursement: number;
  };
};

type AnalysisHistoryItem = {
  id: string;
  title: string;
  created_at: string;
  top_cpt_code?: string | null;
  total_reimbursement: number;
  claim_readiness_status: string;
  main_issue?: string | null;
};

type EvaluationCase = {
  note_filename: string;
  expected_primary_cpt: string;
  actual_primary_cpt: string | null;
  expected_claim_status: string;
  actual_claim_status: string;
  expected_main_issue: string;
  actual_main_issue: string;
  actual_confidence: number;
  passed: boolean;
};

type EvaluationSummary = {
  total_cases: number;
  cpt_accuracy: number;
  readiness_accuracy: number;
  audit_accuracy: number;
  average_confidence: number;
  last_evaluated_at: string;
  per_case_results: EvaluationCase[];
};

type RevisionImpact = {
  previousClaimStatus?: string;
  newClaimStatus?: string;
  previousReadinessScore: number;
  newReadinessScore: number;
  readinessScoreDelta: number;
  resolvedIssues: string[];
  addedIssues: string[];
  cptChanges: Array<{ from?: string | null; to?: string | null }>;
  previousAverageConfidence: number;
  newAverageConfidence: number;
};

type RevisionHistoryItem = {
  id: string;
  createdAt: string;
  originalNote: string;
  revisedNote: string;
  impact: RevisionImpact;
};

const examples = [
  {
    id: "av-fistula",
    label: "Ready Example: AV Fistula",
    title: "Left radiocephalic AV fistula creation",
    note: `Title: Left radiocephalic AV fistula creation

Indication: Synthetic patient with end-stage renal disease requiring durable hemodialysis access.

Procedure: Left upper extremity radiocephalic arteriovenous fistula creation.

Operative note: After sterile preparation, an incision was made at the left wrist. The cephalic vein and radial artery were dissected. The vein was divided distally, flushed, and an end-to-side anastomosis was created to the radial artery with running suture. A palpable thrill was present at completion. Hemostasis was achieved and the incision was closed.`,
  },
  {
    id: "colonoscopy",
    label: "Ready Example: Colonoscopy",
    title: "Diagnostic colonoscopy",
    note: `Title: Diagnostic colonoscopy

Indication: Synthetic patient with positive screening test.

Procedure: Diagnostic colonoscopy.

Operative note: The colonoscope was advanced to the cecum with identification of the appendiceal orifice and ileocecal valve. The mucosa was inspected on withdrawal. No biopsy, polypectomy, or other therapeutic intervention was performed.`,
  },
  {
    id: "hernia-risk",
    label: "Needs Review: Missing Laterality",
    title: "Open inguinal hernia repair with missing laterality",
    note: `Title: Open inguinal hernia repair with missing laterality

Indication: Synthetic patient with symptomatic inguinal hernia.

Procedure: Open inguinal hernia repair with mesh.

Operative note: An oblique groin incision was made. The hernia sac was dissected from the cord structures and reduced. A mesh repair was completed and secured to the inguinal ligament and conjoint tendon. The note does not clearly document left or right laterality.`,
  },
  {
    id: "bundled-risk",
    label: "High Risk: Bundled Cholecystectomy",
    title: "Ambiguous laparoscopic cholecystectomy with cholangiogram",
    note: `Title: Ambiguous laparoscopic cholecystectomy with cholangiogram

Indication: Synthetic patient with symptomatic gallstones.

Procedure: Laparoscopic cholecystectomy, possible cholangiogram.

Operative note: Four ports were placed and the gallbladder was dissected from the liver bed. The cystic duct and artery were clipped and divided. The note states that a cholangiogram may have been performed but does not clearly document images, catheter placement, or interpretation. This creates ambiguity between cholecystectomy code choices.`,
  },
  {
    id: "ambiguous-note",
    label: "Low Confidence: Ambiguous Note",
    title: "Lower extremity angiogram with incomplete documentation",
    note: `Title: Lower extremity angiogram with incomplete documentation

Indication: Synthetic patient with peripheral arterial disease.

Procedure: Lower extremity angiogram.

Operative note: Percutaneous access was obtained and a catheter was advanced for lower extremity angiogram. Images were obtained, but the dictated note does not clearly document left or right laterality, selected vascular territory, or whether additional interventions were performed.`,
  },
  {
    id: "improved-laterality",
    label: "Improved Example: Laterality Clarified",
    title: "Left open inguinal hernia repair",
    note: `Title: Left open inguinal hernia repair

Indication: Synthetic patient with symptomatic left inguinal hernia.

Procedure: Left open inguinal hernia repair with mesh.

Operative note: A left groin incision was made and carried down to the external oblique fascia. The indirect hernia sac was dissected from the cord structures and reduced. Mesh was placed and secured to the inguinal ligament and conjoint tendon on the left side. Hemostasis was achieved and the incision was closed.`,
  },
  {
    id: "improved-angiogram",
    label: "Improved Example: Documentation Complete",
    title: "Left lower extremity diagnostic angiogram",
    note: `Title: Left lower extremity diagnostic angiogram

Indication: Synthetic patient with left leg claudication.

Procedure: Left lower extremity diagnostic angiogram.

Operative note: Percutaneous access was obtained and a catheter was positioned for imaging of the left lower extremity arterial system. Diagnostic angiographic images were obtained and interpreted for the left leg. No angioplasty, stent placement, or atherectomy was performed.`,
  },
  {
    id: "corrected-chole",
    label: "Corrected Example: Single Chole Code",
    title: "Laparoscopic cholecystectomy without cholangiogram",
    note: `Title: Laparoscopic cholecystectomy without cholangiogram

Indication: Synthetic patient with symptomatic cholelithiasis.

Procedure: Laparoscopic cholecystectomy.

Operative note: Four ports were placed and the gallbladder was dissected from the liver bed. The cystic duct and artery were clipped and divided. The gallbladder was removed in an endoscopic bag. No cholangiogram was performed and no separate duct imaging was obtained.`,
  },
];

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function Home() {
  const [selectedExample, setSelectedExample] = useState(examples[0].id);
  const selected = useMemo(() => examples.find((example) => example.id === selectedExample) ?? examples[0], [selectedExample]);
  const [noteText, setNoteText] = useState(selected.note);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [history, setHistory] = useState<AnalysisHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [evaluation, setEvaluation] = useState<EvaluationSummary | null>(null);
  const [evaluationLoading, setEvaluationLoading] = useState(false);
  const [analysisStarted, setAnalysisStarted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showEvidence, setShowEvidence] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showEvaluation, setShowEvaluation] = useState(false);
  const [showRevisionHistory, setShowRevisionHistory] = useState(false);
  const [showParsedStructure, setShowParsedStructure] = useState(false);
  const [revisionImpact, setRevisionImpact] = useState<RevisionImpact | null>(null);
  const [revisionHistory, setRevisionHistory] = useState<RevisionHistoryItem[]>([]);
  const [lastAnalyzedNote, setLastAnalyzedNote] = useState<string | null>(null);

  useEffect(() => {
    void loadHistory();
    void loadEvaluation();
  }, []);

  function chooseExample(exampleId: string) {
    const example = examples.find((item) => item.id === exampleId) ?? examples[0];
    setSelectedExample(example.id);
    setNoteText(example.note);
    setReport(null);
    setError(null);
    setAnalysisStarted(false);
    setShowEvidence(false);
    setRevisionImpact(null);
    setShowParsedStructure(false);
  }

  async function loadHistory() {
    setHistoryLoading(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/analyses`);
      if (response.ok) setHistory(await response.json());
    } finally {
      setHistoryLoading(false);
    }
  }

  async function loadEvaluation() {
    setEvaluationLoading(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/evaluation/summary`);
      if (response.ok) setEvaluation(await response.json());
    } finally {
      setEvaluationLoading(false);
    }
  }

  async function loadAnalysis(id: string) {
    setError(null);
    const response = await fetch(`${apiBaseUrl}/api/analyses/${id}`);
    const payload = await response.json();
    if (!response.ok) {
      setError("Could not generate report. Check that the backend API is running and try again.");
      return;
    }
    setReport(payload);
    setRevisionImpact(null);
    setLastAnalyzedNote(null);
    setAnalysisStarted(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function clearReport() {
    setReport(null);
    setAnalysisStarted(false);
    setError(null);
    setShowEvidence(false);
    setRevisionImpact(null);
    setRevisionHistory([]);
    setLastAnalyzedNote(null);
    setShowParsedStructure(false);
  }

  async function submitNote() {
    if (noteText.trim().length < 50) {
      setError("Please choose an example or enter a synthetic operative note.");
      return;
    }

    setLoading(true);
    setAnalysisStarted(true);
    setError(null);
    const previousReport = report;
    const previousNote = lastAnalyzedNote ?? noteText;
    try {
      const [response] = await Promise.all([
        fetch(`${apiBaseUrl}/api/notes`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: selected.title, note_text: noteText }),
        }),
        delay(1250),
      ]);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message ?? "API request failed.");
      setReport(payload);
      setLastAnalyzedNote(noteText);
      if (previousReport) {
        const impact = compareReports(previousReport, payload);
        setRevisionImpact(impact);
        setRevisionHistory((items) => [
          {
            id: payload.id,
            createdAt: new Date().toISOString(),
            originalNote: previousNote,
            revisedNote: noteText,
            impact,
          },
          ...items,
        ]);
      } else {
        setRevisionImpact(null);
      }
      await loadHistory();
    } catch {
      setError("Could not generate report. Check that the backend API is running and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f4f1ec] text-[#1f2d33]">
      <ProductHeader />

      <section className="mx-auto max-w-7xl px-5 py-6">
        <WorkflowSteps />

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,0.92fr)_minmax(420px,1.08fr)]">
          <InputPanel
            selectedExample={selectedExample}
            noteText={noteText}
            loading={loading}
            error={error}
            onSelectExample={chooseExample}
            onChangeNote={setNoteText}
            onSubmit={submitNote}
            onClear={clearReport}
            hasReport={Boolean(report) || analysisStarted}
            submitLabel={report ? "Reanalyze Updated Note" : "Analyze Note for Billing"}
          />

          <div className="space-y-5">
            <AnalysisStagePanel visible={analysisStarted || Boolean(report)} loading={loading} complete={Boolean(report)} />
            <RevisionImpactCard impact={revisionImpact} />
            <ResultSummary report={report} loading={loading} />
            <KeyFindings report={report} />
          </div>
        </div>

        <div className="mt-6 space-y-5">
          <Disclosure title="View system evaluation" open={showEvaluation} onToggle={() => setShowEvaluation((value) => !value)}>
            <SystemEvaluation evaluation={evaluation} loading={evaluationLoading} />
          </Disclosure>

          <CptCandidates report={report} />
          <AuditFindings report={report} />
          <ImprovementSuggestions report={report} />

          <Disclosure title="Parsed note structure" open={showParsedStructure} onToggle={() => setShowParsedStructure((value) => !value)}>
            <ParsedNoteStructure report={report} />
          </Disclosure>

          <Disclosure title="Why this result?" open={showEvidence} onToggle={() => setShowEvidence((value) => !value)}>
            <EvidenceUsed report={report} />
          </Disclosure>

          <Disclosure title="Recent analyses" open={showHistory} onToggle={() => setShowHistory((value) => !value)}>
            <RecentAnalyses history={history} loading={historyLoading} onLoad={loadAnalysis} />
          </Disclosure>

          <Disclosure title="Revision history" open={showRevisionHistory} onToggle={() => setShowRevisionHistory((value) => !value)}>
            <RevisionHistoryPanel items={revisionHistory} />
          </Disclosure>
        </div>
      </section>
    </main>
  );
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function ProductHeader() {
  return (
    <header className="border-b border-[#e7ded2] bg-[#fffdfa]">
      <div className="mx-auto max-w-7xl px-5 py-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
          <div>
            <p className="text-sm font-semibold text-[#58716c]">Healthcare revenue cycle demo</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-normal text-[#1f2d33]">AI Clinical Ops Agent</h1>
            <p className="mt-3 max-w-4xl text-base leading-7 text-[#586b69]">
              Turn a synthetic operative note into CPT candidates, billing risk flags, reimbursement estimates, and a claim readiness report.
            </p>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#71817d]">
              Simulates how a billing operations team reviews operative notes before CPT submission.
            </p>
          </div>
          <div className="rounded-2xl border border-[#ead8c0] bg-[#fbf2e6] p-5 shadow-[0_10px_26px_rgba(90,68,45,0.06)]">
            <p className="text-sm font-semibold text-[#7a5428]">Demo only. Do not enter real patient information.</p>
            <p className="mt-2 text-sm leading-6 text-[#776653]">Use the included synthetic examples or paste synthetic text you created for testing.</p>
          </div>
        </div>

        <div className="mt-7 grid gap-4 md:grid-cols-3">
          <ValueCard title="Identify likely CPT codes" text="Extract procedures and suggest billing-code candidates from the note." />
          <ValueCard title="Flag billing/documentation risks" text="Surface missing details, low-confidence coding, and bundling concerns." />
          <ValueCard title="Estimate reimbursement impact" text="Map suggested codes to a local synthetic fee schedule." />
        </div>
      </div>
    </header>
  );
}

function ValueCard({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl border border-[#e5ded5] bg-[#fffaf4] p-5 shadow-[0_10px_28px_rgba(54,42,31,0.04)]">
      <h2 className="text-sm font-semibold text-[#1f2d33]">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-[#667774]">{text}</p>
    </div>
  );
}

function WorkflowSteps() {
  const steps = [
    ["Step 1", "Choose or paste a synthetic operative note"],
    ["Step 2", "Run billing analysis"],
    ["Step 3", "Review claim readiness report"],
  ];
  return (
    <section className="rounded-2xl border border-[#e4ddd2] bg-[#fffdfa] p-5 shadow-[0_12px_32px_rgba(54,42,31,0.04)]">
      <div className="grid gap-4 md:grid-cols-3">
        {steps.map(([label, text]) => (
          <div key={label} className="flex gap-3 rounded-xl bg-[#f7f4ef] p-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#245c52] text-sm font-semibold text-white">
              {label.replace("Step ", "")}
            </span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#7a8a88]">{label}</p>
              <p className="mt-1 text-sm font-medium text-[#34464a]">{text}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function InputPanel({
  selectedExample,
  noteText,
  loading,
  error,
  onSelectExample,
  onChangeNote,
  onSubmit,
  onClear,
  hasReport,
  submitLabel,
}: {
  selectedExample: string;
  noteText: string;
  loading: boolean;
  error: string | null;
  onSelectExample: (value: string) => void;
  onChangeNote: (value: string) => void;
  onSubmit: () => void;
  onClear: () => void;
  hasReport: boolean;
  submitLabel: string;
}) {
  return (
    <section className="rounded-2xl border border-[#e4ddd2] bg-[#fffdfa] p-6 shadow-[0_14px_36px_rgba(54,42,31,0.05)]">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-[#7a8a88]">Step 1</p>
        <h2 className="mt-1 text-xl font-semibold text-[#1f2d33]">Synthetic Operative Note</h2>
        <p className="mt-2 text-sm leading-6 text-[#667774]">
          Use an example note or paste your own synthetic note. The system will extract procedures, suggest CPT codes, check billing risks, and estimate reimbursement.
        </p>
      </div>

      <label className="mt-6 block text-sm font-semibold text-[#34464a]">Example note</label>
      <select
        value={selectedExample}
        onChange={(event) => onSelectExample(event.target.value)}
        className="mt-2 h-11 w-full rounded-xl border border-[#d8d0c4] bg-[#fffefb] px-3 text-sm outline-none focus:border-[#245c52] focus:ring-2 focus:ring-[#d6e5df]"
      >
        {examples.map((example) => (
          <option key={example.id} value={example.id}>
            {example.label}
          </option>
        ))}
      </select>

      <textarea
        value={noteText}
        onChange={(event) => onChangeNote(event.target.value)}
        maxLength={20000}
        className="mt-4 min-h-[410px] w-full resize-y rounded-xl border border-[#d8d0c4] bg-[#fffefb] p-4 font-mono text-sm leading-6 outline-none focus:border-[#245c52] focus:ring-2 focus:ring-[#d6e5df]"
      />
      <div className="mt-3 flex items-center justify-between gap-4 text-xs text-[#71817d]">
        <span>{noteText.length.toLocaleString()} / 20,000 characters</span>
        <span>No PHI</span>
      </div>

      <button
        type="button"
        onClick={onSubmit}
        disabled={loading}
        className="mt-6 w-full rounded-xl bg-[#245c52] px-4 py-3.5 text-sm font-semibold text-white shadow-[0_10px_22px_rgba(36,92,82,0.18)] hover:bg-[#1e4f47] disabled:cursor-not-allowed disabled:bg-[#9bb5ad]"
      >
        {loading ? "Analyzing note..." : submitLabel}
      </button>
      {hasReport ? (
        <button
          type="button"
          onClick={onClear}
          className="mt-3 w-full rounded-xl border border-[#d8d0c4] bg-[#fffefb] px-4 py-3 text-sm font-semibold text-[#34464a] hover:bg-[#f7f4ef]"
        >
          Clear report
        </button>
      ) : null}

      {error ? <div className="mt-4 rounded-xl border border-[#e6c0b5] bg-[#fbefeb] p-3 text-sm font-medium text-[#8f3b2d]">{error}</div> : null}
    </section>
  );
}

function AnalysisStagePanel({ visible, loading, complete }: { visible: boolean; loading: boolean; complete: boolean }) {
  const checks = [
    "Extracting procedures",
    "Mapping CPT candidates",
    "Checking documentation and billing risks",
    "Estimating reimbursement",
    "Calculating claim readiness",
  ];

  if (!visible) {
    return (
      <section className="rounded-2xl border border-[#e4ddd2] bg-[#fffdfa] p-6 shadow-[0_12px_32px_rgba(54,42,31,0.05)]">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#7a8a88]">Step 2</p>
        <h2 className="mt-1 text-xl font-semibold text-[#1f2d33]">Billing analysis will run here</h2>
        <p className="mt-2 text-sm leading-6 text-[#667774]">After you analyze a note, this panel will show the review workflow before the report appears.</p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-[#d8e2dc] bg-[#fbfdfb] p-6 shadow-[0_14px_36px_rgba(39,78,70,0.08)]">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#607a73]">Step 2</p>
          <h2 className="mt-1 text-xl font-semibold text-[#1f2d33]">{loading ? "Running billing analysis" : complete ? "Billing analysis completed" : "Billing analysis ready"}</h2>
          <p className="mt-2 text-sm leading-6 text-[#667774]">Simulating a billing operations review workflow.</p>
        </div>
        <StatusBadge status={loading ? "Running" : "Ready"} />
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {checks.map((item, index) => (
          <div key={item} className="flex items-center gap-3 rounded-xl bg-white/80 px-4 py-3 text-sm text-[#34464a]">
            <span
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                loading && index > 1 ? "bg-[#edf0ec] text-[#84908c]" : "bg-[#dcebe5] text-[#245c52]"
              }`}
            >
              {loading && index > 1 ? "..." : "OK"}
            </span>
            {item}
          </div>
        ))}
      </div>
    </section>
  );
}

function RevisionImpactCard({ impact }: { impact: RevisionImpact | null }) {
  if (!impact) return null;
  return (
    <section className="rounded-2xl border border-[#cfe0d8] bg-[#fbfdfb] p-6 shadow-[0_14px_36px_rgba(39,78,70,0.08)]">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#607a73]">Revision Impact</p>
          <h2 className="mt-1 text-xl font-semibold text-[#1f2d33]">Updated note comparison</h2>
          <p className="mt-2 text-sm leading-6 text-[#667774]">Shows how the revised documentation changed billing readiness and audit risk.</p>
        </div>
        <StatusBadge status={impact.newClaimStatus ?? "Updated"} />
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <ImpactMetric label="Previous status" value={impact.previousClaimStatus ?? "Not available"} />
        <ImpactMetric label="New status" value={impact.newClaimStatus ?? "Not available"} />
        <ImpactMetric label="Previous score" value={`${impact.previousReadinessScore}/100`} />
        <ImpactMetric label="New score" value={`${impact.newReadinessScore}/100`} detail={formatDelta(impact.readinessScoreDelta)} />
      </div>

      <div className="mt-5 rounded-xl bg-[#f7fbf8] p-4">
        <p className="text-sm font-semibold text-[#34464a]">Confidence trend</p>
        <div className="mt-4 space-y-3">
          <ConfidenceBar label="Initial confidence" value={impact.previousAverageConfidence} />
          <ConfidenceBar label="Updated confidence" value={impact.newAverageConfidence} />
        </div>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <ImpactList title="Resolved issues" items={impact.resolvedIssues.map((item) => `Resolved: ${item}`)} empty="No prior issues were resolved." success />
        <ImpactList title="New issues" items={impact.addedIssues} empty="No new issues added." />
        <ImpactList
          title="CPT changes"
          items={impact.cptChanges.map((change) => `${change.from ?? "None"} -> ${change.to ?? "None"}`)}
          empty="Primary CPT did not change."
        />
      </div>
    </section>
  );
}

function ImpactMetric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-xl border border-[#d8e2dc] bg-white/80 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#7a8a88]">{label}</p>
      <p className="mt-2 text-lg font-semibold text-[#1f2d33]">{value}</p>
      {detail ? <p className="mt-1 text-sm font-semibold text-[#245c52]">{detail}</p> : null}
    </div>
  );
}

function ConfidenceBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-[#34464a]">{label}</span>
        <span className="font-semibold text-[#245c52]">{Math.round(value * 100)}%</span>
      </div>
      <div className="mt-2 h-2 rounded-full bg-[#e7eee9]">
        <div className="h-2 rounded-full bg-[#245c52]" style={{ width: `${Math.max(4, Math.round(value * 100))}%` }} />
      </div>
    </div>
  );
}

function ImpactList({ title, items, empty, success = false }: { title: string; items: string[]; empty: string; success?: boolean }) {
  return (
    <div className="rounded-xl border border-[#e4ddd2] bg-[#fffaf4] p-4">
      <p className="text-sm font-semibold text-[#34464a]">{title}</p>
      {items.length ? (
        <ul className="mt-3 space-y-2 text-sm">
          {items.map((item) => (
            <li key={item} className={`rounded-lg px-3 py-2 ${success ? "bg-[#edf6f2] text-[#245c52]" : "bg-[#fffdfa] text-[#586b69]"}`}>
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 rounded-lg bg-[#fffdfa] px-3 py-2 text-sm text-[#71817d]">{empty}</p>
      )}
    </div>
  );
}

function ResultSummary({ report, loading }: { report: AnalysisReport | null; loading: boolean }) {
  const topCode = report?.cpt_candidates[0];
  const reviewItems = (report?.audit_findings ?? []).filter((finding) => finding.severity !== "info");
  return (
    <section className="rounded-2xl border border-[#e4ddd2] bg-[#fffdfa] p-6 shadow-[0_14px_36px_rgba(54,42,31,0.05)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.1em] text-[#7a8a88]">Step 3</p>
          <h2 className="mt-1 text-xl font-semibold text-[#1f2d33]">Claim Readiness Report</h2>
          <p className="mt-2 text-sm leading-6 text-[#667774]">
            A score estimating how safe this note is to code and submit based on confidence, audit issues, and documentation completeness.
          </p>
          {report ? (
            <div className="mt-3 rounded-xl border border-[#d8e2dc] bg-[#f7fbf8] px-4 py-3">
              <p className="text-sm font-semibold text-[#34464a]">Analysis mode: {analysisModeLabel(report.report.analysis_mode)}</p>
              <p className="mt-1 text-xs leading-5 text-[#667774]">
                Hybrid AI mode can better interpret varied synthetic note formats, but all results still require human review.
              </p>
              {report.report.ai_assist_status ? <p className="mt-1 text-xs text-[#71817d]">{report.report.ai_assist_status}</p> : null}
            </div>
          ) : null}
        </div>
        <StatusBadge status={report?.report.claim_readiness_status ?? (loading ? "Running" : "Not run")} />
      </div>

      {report ? (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryMetric label="Claim Status" value={report.report.claim_readiness_status} />
            <SummaryMetric label="Primary CPT" value={topCode?.code ?? "None"} detail={topCode?.description} />
            <SummaryMetric label="Estimated Reimbursement" value={formatCurrency(report.total_estimated_reimbursement)} />
            <SummaryMetric label="Main Issue" value={report.report.main_issue ?? mainIssue(reviewItems)} />
          </div>
          <div className="mt-5 rounded-xl border border-[#d8e2dc] bg-[#f2f8f5] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#607a73]">Recommended action</p>
            <p className="mt-2 text-base font-semibold text-[#1f2d33]">{report.report.recommended_action ?? recommendedAction(report.report.claim_readiness_status)}</p>
          </div>
          <div className="mt-4 rounded-xl bg-[#f7f4ef] p-4">
            <p className="mb-3 text-sm font-semibold text-[#34464a]">Report narrative</p>
            <p className="mb-3 text-sm leading-6 text-[#586b69]">{reportNarrative(report)}</p>
            <p className="text-sm leading-6 text-[#586b69]">{report.report.claim_readiness_explanation}</p>
            <ul className="mt-3 grid gap-2 text-sm text-[#34464a] sm:grid-cols-2">
              {(report.report.claim_readiness_reasons ?? fallbackReasons(report)).map((reason) => (
                <li key={reason} className="rounded-lg bg-[#fffdfa] px-3 py-2">
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : (
        <FriendlyEmpty title="Your report will appear here after analysis." text="Choose an example note to see how the system works." />
      )}
    </section>
  );
}

function KeyFindings({ report }: { report: AnalysisReport | null }) {
  if (!report) {
    return (
      <section className="rounded-2xl border border-[#e4ddd2] bg-[#fffdfa] p-6 shadow-[0_14px_36px_rgba(54,42,31,0.05)]">
        <h2 className="text-lg font-semibold text-[#1f2d33]">Key Findings</h2>
        <FriendlyEmpty title="No findings yet." text="Run an analysis to see procedures, suggested codes, risks, and reimbursement impact." />
      </section>
    );
  }

  const reviewItems = report.audit_findings.filter((finding) => finding.severity !== "info");
  const topCode = report.cpt_candidates[0];
  return (
    <section className="rounded-2xl border border-[#e4ddd2] bg-[#fffdfa] p-6 shadow-[0_14px_36px_rgba(54,42,31,0.05)]">
      <h2 className="text-lg font-semibold text-[#1f2d33]">Key Findings</h2>
      <div className="mt-5 space-y-3">
        <PlainFinding label="Procedure identified" value={report.extracted_procedures.map((item) => item.name).join(", ") || "None"} />
        <PlainFinding label="Primary billing code" value={topCode ? `${topCode.code} - ${topCode.description}` : "No code identified"} />
        <PlainFinding label="Main risk" value={report.report.main_issue ?? mainIssue(reviewItems)} />
        <PlainFinding label="Recommended next step" value={report.report.recommended_action ?? recommendedAction(report.report.claim_readiness_status)} />
      </div>
    </section>
  );
}

function CptCandidates({ report }: { report: AnalysisReport | null }) {
  return (
    <SectionCard title="CPT Candidates" explainer="Possible billing codes identified from the operative note and supporting references.">
      {report ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-[#e4ddd2] text-xs uppercase tracking-[0.08em] text-[#7a8a88]">
                <th className="py-3 pr-4">CPT</th>
                <th className="py-3 pr-4">What it represents</th>
                <th className="py-3 pr-4">Confidence</th>
                <th className="py-3 pr-4">Modifier</th>
                <th className="py-3 pr-4">Support</th>
              </tr>
            </thead>
            <tbody>
              {report.cpt_candidates.map((candidate) => (
                <tr key={`${candidate.code}-${candidate.procedure_name}`} className="border-b border-[#f0e9df]">
                  <td className="py-3 pr-4 font-mono font-semibold text-[#1f2d33]">{candidate.code}</td>
                  <td className="py-3 pr-4">
                    <p className="font-medium text-[#34464a]">{candidate.procedure_name}</p>
                    <p className="mt-1 text-xs leading-5 text-[#71817d]">{candidate.description}</p>
                  </td>
                  <td className="py-3 pr-4">{Math.round(candidate.confidence * 100)}%</td>
                  <td className="py-3 pr-4">{candidate.modifiers.length ? candidate.modifiers.join(", ") : "Needs clarification"}</td>
                  <td className="py-3 pr-4">{candidate.supported_by_docs ? "Reference found" : "Needs support"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <FriendlyEmpty title="CPT candidates will appear after analysis." text="The system will show likely billing codes and confidence levels." />
      )}
    </SectionCard>
  );
}

function SystemEvaluation({ evaluation, loading }: { evaluation: EvaluationSummary | null; loading: boolean }) {
  return (
    <SectionCard
      title="System Evaluation"
      explainer="This evaluation uses synthetic operative notes only. It measures whether the system consistently produces the expected CPT, risk status, and audit findings for known demo cases."
    >
      {evaluation ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <SummaryMetric label="Notes evaluated" value={String(evaluation.total_cases)} />
            <SummaryMetric label="CPT match accuracy" value={formatPercent(evaluation.cpt_accuracy)} />
            <SummaryMetric label="Audit finding accuracy" value={formatPercent(evaluation.audit_accuracy)} />
            <SummaryMetric label="Claim readiness accuracy" value={formatPercent(evaluation.readiness_accuracy)} />
            <SummaryMetric label="Average confidence" value={formatPercent(evaluation.average_confidence)} />
          </div>
          <div className="mt-5 rounded-xl bg-[#f7f4ef] p-4">
            <p className="text-sm font-semibold text-[#34464a]">Demo Dataset</p>
            <p className="mt-2 text-sm leading-6 text-[#667774]">
              These metrics compare deterministic pipeline outputs against a small gold-standard file for the included synthetic notes. They demonstrate consistency for demo cases, not clinical or billing correctness on real patient records.
            </p>
            <p className="mt-2 text-xs text-[#71817d]">Last evaluated: {new Date(evaluation.last_evaluated_at).toLocaleString()}</p>
          </div>
          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead>
                <tr className="border-b border-[#e4ddd2] text-xs uppercase tracking-[0.08em] text-[#7a8a88]">
                  <th className="py-3 pr-4">Synthetic case</th>
                  <th className="py-3 pr-4">Expected CPT</th>
                  <th className="py-3 pr-4">Actual CPT</th>
                  <th className="py-3 pr-4">Expected status</th>
                  <th className="py-3 pr-4">Actual status</th>
                  <th className="py-3 pr-4">Main issue</th>
                  <th className="py-3 pr-4">Result</th>
                </tr>
              </thead>
              <tbody>
                {evaluation.per_case_results.map((item) => (
                  <tr key={item.note_filename} className="border-b border-[#f0e9df]">
                    <td className="py-3 pr-4 font-medium text-[#34464a]">{friendlyFilename(item.note_filename)}</td>
                    <td className="py-3 pr-4 font-mono">{item.expected_primary_cpt}</td>
                    <td className="py-3 pr-4 font-mono">{item.actual_primary_cpt ?? "-"}</td>
                    <td className="py-3 pr-4">{item.expected_claim_status}</td>
                    <td className="py-3 pr-4">{item.actual_claim_status}</td>
                    <td className="py-3 pr-4">{item.actual_main_issue}</td>
                    <td className="py-3 pr-4">
                      <StatusBadge status={item.passed ? "Pass" : "Fail"} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <FriendlyEmpty
          title={loading ? "Loading synthetic evaluation..." : "Evaluation metrics are unavailable."}
          text="The API calculates these metrics by running the synthetic notes through the same pipeline used by the dashboard."
        />
      )}
    </SectionCard>
  );
}

function AuditFindings({ report }: { report: AnalysisReport | null }) {
  return (
    <SectionCard title="Audit Findings" explainer="Documentation or billing concerns that should be reviewed before submission.">
      {report ? (
        <div className="space-y-3">
          {report.audit_findings.map((finding, index) => (
            <div key={`${finding.category}-${index}`} className="rounded-xl border border-[#e4ddd2] bg-[#fffaf4] p-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="font-semibold text-[#34464a]">{finding.title ?? findingTitle(finding.category)}</p>
                  <p className="mt-1 text-sm leading-6 text-[#667774]">{finding.explanation ?? finding.message}</p>
                </div>
                <StatusBadge status={finding.severity === "high" ? "High Risk" : finding.severity === "medium" ? "Needs Review" : "Ready"} />
              </div>
              <div className="mt-3 rounded-lg bg-[#fffdfa] px-3 py-2 text-sm">
                <span className="font-semibold text-[#34464a]">Recommended action: </span>
                <span className="text-[#586b69]">{finding.suggested_action ?? finding.recommendation}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <FriendlyEmpty title="No audit findings yet." text="After analysis, risks such as missing modifiers or bundled-code conflicts will be listed here." />
      )}
    </SectionCard>
  );
}

function ImprovementSuggestions({ report }: { report: AnalysisReport | null }) {
  const findings = (report?.audit_findings ?? []).filter((finding) => finding.category !== "clean_claim");
  return (
    <SectionCard
      title="How to improve this note"
      explainer="Practical documentation changes that would help a billing team review the note more confidently."
    >
      {report ? (
        findings.length ? (
          <div className="grid gap-4 lg:grid-cols-2">
            {findings.map((finding, index) => (
              <div key={`${finding.category}-suggestion-${index}`} className="rounded-xl border border-[#e4ddd2] bg-[#fffaf4] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[#34464a]">{finding.title ?? findingTitle(finding.category)}</p>
                    <p className="mt-2 text-sm leading-6 text-[#586b69]">
                      {finding.documentation_improvement ?? improvementForFinding(finding)}
                    </p>
                  </div>
                  <StatusBadge status={finding.severity === "high" ? "High Risk" : "Needs Review"} />
                </div>
                <div className="mt-4 rounded-lg bg-[#fffdfa] p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#7a8a88]">Why this matters</p>
                  <p className="mt-2 text-sm leading-6 text-[#667774]">{finding.why_it_matters ?? whyImprovementMatters(finding)}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-[#c4dad2] bg-[#edf6f2] p-4">
            <p className="font-semibold text-[#245c52]">No documentation gaps were flagged by the local demo checks.</p>
            <p className="mt-2 text-sm leading-6 text-[#586b69]">A billing team would still perform standard human validation before submission.</p>
          </div>
        )
      ) : (
        <FriendlyEmpty title="Improvement suggestions will appear after analysis." text="If the note has missing details or risk flags, this section will explain how to revise it and why it matters." />
      )}
    </SectionCard>
  );
}

function ParsedNoteStructure({ report }: { report: AnalysisReport | null }) {
  const parsed = report?.structured_note;
  return (
    <SectionCard title="Parsed Note Structure" explainer="A preprocessing view of the operative note sections the system found before coding and audit checks run.">
      {parsed ? (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <SummaryMetric label="Structure quality" value={parsed.structure_quality} />
            <SummaryMetric label="Parsing confidence" value={formatPercent(parsed.parsing_confidence)} />
            <SummaryMetric label="Detected anatomy" value={parsed.detected_anatomy ?? "Not detected"} />
            <SummaryMetric label="Detected laterality" value={parsed.detected_laterality ?? "Not detected"} />
          </div>

          <div className="rounded-xl border border-[#e4ddd2] bg-[#fffaf4] p-4">
            <p className="text-sm font-semibold text-[#34464a]">Detected sections</p>
            {Object.entries(parsed.parsed_sections).length ? (
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                {Object.entries(parsed.parsed_sections).map(([section, text]) => (
                  <div key={section} className="rounded-lg bg-[#fffdfa] p-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#7a8a88]">{section}</p>
                    <p className="mt-2 line-clamp-4 text-sm leading-6 text-[#667774]">{text}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 rounded-lg bg-[#fffdfa] p-3 text-sm text-[#71817d]">No clear section headers were detected.</p>
            )}
          </div>

          <div className="rounded-xl border border-[#e4ddd2] bg-[#fffaf4] p-4">
            <p className="text-sm font-semibold text-[#34464a]">Missing sections</p>
            {parsed.missing_sections.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {parsed.missing_sections.map((section) => (
                  <span key={section} className="rounded-full border border-[#e4cfa8] bg-[#fbf3e4] px-3 py-1 text-xs font-semibold text-[#7a5724]">
                    {section}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-3 rounded-lg bg-[#edf6f2] p-3 text-sm font-medium text-[#245c52]">No critical note sections missing.</p>
            )}
          </div>
        </div>
      ) : (
        <FriendlyEmpty title="Parsed note structure will appear after analysis." text="The parser will show detected sections, anatomy, laterality, and missing critical sections before the billing review output." />
      )}
    </SectionCard>
  );
}

function EvidenceUsed({ report }: { report: AnalysisReport | null }) {
  return (
    <SectionCard title="Why this result?" explainer="Shows the procedure match, risks checked, and references that supported the billing review.">
      {report ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <EvidenceGroup
            title="Why this CPT?"
            rows={report.cpt_candidates.map((candidate) => ({
              heading: `${candidate.code} - ${candidate.procedure_name}`,
              body: candidate.rationale,
              meta: candidate.evidence_used[0]?.source,
            }))}
          />
          <EvidenceGroup
            title="What risks were checked?"
            rows={report.audit_findings.map((finding) => ({
              heading: finding.title ?? findingTitle(finding.category),
              body: finding.explanation ?? finding.message,
              meta: finding.severity,
            }))}
          />
          <EvidenceGroup
            title="What references supported this?"
            rows={report.cpt_candidates.flatMap((candidate) =>
              candidate.evidence_used.length
                ? candidate.evidence_used.map((evidence) => ({
                    heading: evidence.source,
                    body: evidence.snippet,
                    meta: `CPT ${candidate.code}`,
                  }))
                : [
                    {
                      heading: `CPT ${candidate.code}`,
                      body: "No matching reference snippet found in the local demo guidelines.",
                      meta: "Local demo guidelines",
                    },
                  ],
            )}
          />
        </div>
      ) : (
        <FriendlyEmpty title="Evidence will appear after analysis." text="References are hidden by default to keep the first report easy to read." />
      )}
    </SectionCard>
  );
}

function RecentAnalyses({
  history,
  loading,
  onLoad,
}: {
  history: AnalysisHistoryItem[];
  loading: boolean;
  onLoad: (id: string) => void;
}) {
  return (
    <SectionCard title="Recent Analyses" explainer="Previously generated demo reports from this environment.">
      {history.length ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {history.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onLoad(item.id)}
              className="rounded-xl border border-[#e4ddd2] bg-[#fffaf4] p-4 text-left hover:border-[#86aaa0]"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-semibold text-[#34464a]">{item.title}</p>
                <span className="font-mono text-xs text-[#71817d]">{item.top_cpt_code ?? "No CPT"}</span>
              </div>
              <p className="mt-2 text-xs text-[#71817d]">{new Date(item.created_at).toLocaleString()}</p>
              <div className="mt-3 flex items-center justify-between gap-3 text-sm">
                <StatusBadge status={item.claim_readiness_status} />
                <span className="font-mono text-xs text-[#71817d]">{item.top_cpt_code ?? "No CPT"}</span>
              </div>
              <div className="mt-3 grid gap-1 text-xs text-[#667774]">
                <span>Main issue: {item.main_issue ?? "No major issues"}</span>
                <span>Estimated: {formatCurrency(item.total_reimbursement)}</span>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <FriendlyEmpty title={loading ? "Loading recent analyses..." : "No recent analyses yet."} text="Generated reports will appear here after you run examples." />
      )}
    </SectionCard>
  );
}

function RevisionHistoryPanel({ items }: { items: RevisionHistoryItem[] }) {
  return (
    <SectionCard title="Revision History" explainer="Tracks note edits made during this browser session and how each revision changed claim readiness.">
      {items.length ? (
        <div className="space-y-4">
          {items.map((item, index) => (
            <div key={`${item.id}-${item.createdAt}`} className="rounded-xl border border-[#e4ddd2] bg-[#fffaf4] p-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm font-semibold text-[#34464a]">Revision {items.length - index}</p>
                  <p className="mt-1 text-xs text-[#71817d]">{new Date(item.createdAt).toLocaleString()}</p>
                </div>
                <StatusBadge status={item.impact.newClaimStatus ?? "Updated"} />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <SummaryMetric label="Previous score" value={`${item.impact.previousReadinessScore}/100`} />
                <SummaryMetric label="Updated score" value={`${item.impact.newReadinessScore}/100`} />
                <SummaryMetric label="Score change" value={formatDelta(item.impact.readinessScoreDelta)} />
              </div>
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                <NotePreview title="Original note" text={item.originalNote} />
                <NotePreview title="Revised note" text={item.revisedNote} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <FriendlyEmpty title="No revisions yet." text="After a report is generated, edit the note and choose Reanalyze Updated Note to create a revision history entry." />
      )}
    </SectionCard>
  );
}

function NotePreview({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-xl bg-[#fffdfa] p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#7a8a88]">{title}</p>
      <p className="mt-2 line-clamp-5 whitespace-pre-wrap text-xs leading-5 text-[#667774]">{text}</p>
    </div>
  );
}

function Disclosure({ title, open, onToggle, children }: { title: string; open: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-[#e5ded5] bg-[#fffdfa] shadow-[0_12px_30px_rgba(54,42,31,0.045)]">
      <button type="button" onClick={onToggle} className="flex w-full items-center justify-between gap-5 px-6 py-5 text-left transition hover:bg-[#fbf7f1]">
        <span>
          <span className="block text-base font-semibold text-[#1f2d33]">{title}</span>
          <span className="mt-1 block text-xs font-medium uppercase tracking-[0.08em] text-[#7a8a88]">{open ? "Expanded" : "Collapsed"}</span>
        </span>
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[#d8d0c4] bg-[#fffaf4] text-lg font-semibold text-[#245c52] transition-transform ${
            open ? "rotate-45" : ""
          }`}
          aria-hidden="true"
        >
          +
        </span>
      </button>
      {open ? <div className="border-t border-[#efe8df] bg-[#fffdfa] p-6">{children}</div> : null}
    </section>
  );
}

function SectionCard({ title, explainer, children }: { title: string; explainer: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-[#e4ddd2] bg-[#fffdfa] p-6 shadow-[0_14px_36px_rgba(54,42,31,0.05)]">
      <h2 className="text-lg font-semibold text-[#1f2d33]">{title}</h2>
      <p className="mt-1 text-sm leading-6 text-[#667774]">{explainer}</p>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function SummaryMetric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-xl border border-[#e4ddd2] bg-[#fffaf4] p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#7a8a88]">{label}</p>
      <p className="mt-2 text-lg font-semibold text-[#1f2d33]">{value}</p>
      {detail ? <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#71817d]">{detail}</p> : null}
    </div>
  );
}

function PlainFinding({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-[#f7f4ef] p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#7a8a88]">{label}</p>
      <p className="mt-2 text-sm leading-6 text-[#34464a]">{value}</p>
    </div>
  );
}

function FriendlyEmpty({ title, text }: { title: string; text: string }) {
  return (
    <div className="mt-4 rounded-xl border border-dashed border-[#d8d0c4] bg-[#fffaf4] p-5">
      <p className="font-semibold text-[#34464a]">{title}</p>
      <p className="mt-2 text-sm leading-6 text-[#71817d]">{text}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const styles = normalized.includes("high")
    ? "border-[#e7bdb4] bg-[#fbefeb] text-[#8f3b2d]"
    : normalized.includes("review") || normalized.includes("running")
      ? "border-[#e4cfa8] bg-[#fbf3e4] text-[#7a5724]"
      : normalized.includes("ready") || normalized.includes("pass")
        ? "border-[#c4dad2] bg-[#edf6f2] text-[#245c52]"
        : normalized.includes("fail")
          ? "border-[#e7bdb4] bg-[#fbefeb] text-[#8f3b2d]"
        : "border-[#e4ddd2] bg-[#f7f4ef] text-[#71817d]";
  return <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${styles}`}>{status}</span>;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function friendlyFilename(value: string) {
  return value.replace(".txt", "").replaceAll("_", " ");
}

function readableCategory(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function EvidenceGroup({ title, rows }: { title: string; rows: Array<{ heading: string; body: string; meta?: string }> }) {
  return (
    <div className="rounded-xl border border-[#e4ddd2] bg-[#fffaf4] p-4">
      <h3 className="font-semibold text-[#1f2d33]">{title}</h3>
      <div className="mt-3 space-y-3">
        {rows.map((row, index) => (
          <div key={`${row.heading}-${index}`} className="rounded-lg bg-[#fffdfa] p-3">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-semibold text-[#34464a]">{row.heading}</p>
              {row.meta ? <span className="text-xs text-[#71817d]">{row.meta}</span> : null}
            </div>
            <p className="mt-2 text-sm leading-6 text-[#667774]">{row.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function recommendedAction(status: string) {
  if (status === "Ready") return "Proceed with standard billing review.";
  if (status === "Needs Review") return "Clarify documentation before submission.";
  if (status === "High Risk") return "Do not submit until billing conflicts or documentation gaps are resolved.";
  return "Run analysis to generate a recommended action.";
}

function mainIssue(findings: AuditFinding[]) {
  const categories = findings.map((finding) => finding.category);
  if (categories.includes("bundling_conflict")) return "Bundling conflict";
  if (categories.includes("missing_laterality")) return "Missing laterality";
  if (categories.includes("low_confidence")) return "Ambiguous documentation";
  if (categories.includes("unsupported_code")) return "Unsupported procedure";
  return "No major issues";
}

function fallbackReasons(report: AnalysisReport) {
  return [
    report.cpt_candidates[0]?.confidence >= 0.85 ? "Strong procedure match." : "Procedure match needs review.",
    report.cpt_candidates.every((candidate) => candidate.supported_by_docs) ? "Supporting guideline found." : "Missing supporting guideline.",
    (report.report.main_issue ?? "No major issues") === "No major issues" ? "Documentation appears complete for the demo checks." : `Documentation issue: ${report.report.main_issue}.`,
    report.report.claim_readiness_status === "High Risk" ? "Audit risk high." : report.report.claim_readiness_status === "Needs Review" ? "Audit risk medium." : "Audit risk low.",
  ];
}

function reportNarrative(report: AnalysisReport) {
  const issue = report.report.main_issue ?? mainIssue(report.audit_findings.filter((finding) => finding.severity !== "info"));
  const action = report.report.recommended_action ?? recommendedAction(report.report.claim_readiness_status);
  if (report.report.claim_readiness_status === "Ready") {
    return `The note is currently marked as Ready because the primary procedure is documented clearly and the local demo audit checks did not find major billing risks. Recommended next step: ${action}`;
  }
  if (issue === "Missing laterality") {
    return `The note is currently marked as ${report.report.claim_readiness_status} because laterality was not clearly documented. Clarifying whether the procedure was performed on the left or right side would likely improve coding confidence and reduce modifier ambiguity.`;
  }
  if (issue === "Bundling conflict") {
    return `The note is currently marked as High Risk because the documentation produced a possible bundled-code conflict. Resolving which service should be billed would reduce denial and compliance risk.`;
  }
  return `The note is currently marked as ${report.report.claim_readiness_status} because the billing review found ${issue.toLowerCase()}. Recommended next step: ${action}`;
}

function findingTitle(category: string) {
  if (category === "bundling_conflict") return "Bundling conflict detected";
  if (category === "low_confidence") return "Low confidence coding";
  if (category === "missing_laterality") return "Missing laterality";
  if (category === "unsupported_code") return "Unsupported procedure";
  if (category === "clean_claim") return "No major billing risks found";
  return readableCategory(category);
}

function improvementForFinding(finding: AuditFinding) {
  if (finding.category === "missing_laterality") return "Document whether the procedure was performed on the left or right side.";
  if (finding.category === "low_confidence") return "Clarify the exact procedure performed and whether it was diagnostic or therapeutic.";
  if (finding.category === "bundling_conflict") return "Review whether both procedures should be billed together or select the single supported definitive code.";
  if (finding.category === "unsupported_code") return "Confirm the correct billable procedure and supporting reference before coding.";
  return finding.suggested_action ?? finding.recommendation;
}

function whyImprovementMatters(finding: AuditFinding) {
  if (finding.category === "missing_laterality") return "Billing teams need laterality to select LT or RT modifiers and avoid payer follow-up.";
  if (finding.category === "low_confidence") return "Clear procedure intent improves CPT selection, coding confidence, and reimbursement predictability.";
  if (finding.category === "bundling_conflict") return "Bundled services may be denied or create billing compliance risk if both codes are submitted.";
  if (finding.category === "unsupported_code") return "Unsupported codes create denial and compliance risk during billing review.";
  return "Cleaner documentation helps billing reviewers make a more confident coding decision.";
}

function compareReports(previous: AnalysisReport, current: AnalysisReport): RevisionImpact {
  const previousFindings = issueMap(previous);
  const currentFindings = issueMap(current);
  const previousCpt = primaryCpt(previous);
  const currentCpt = primaryCpt(current);
  const cptChanges = previousCpt === currentCpt ? [] : [{ from: previousCpt, to: currentCpt }];

  return {
    previousClaimStatus: previous.report.claim_readiness_status,
    newClaimStatus: current.report.claim_readiness_status,
    previousReadinessScore: previous.report.claim_readiness_score,
    newReadinessScore: current.report.claim_readiness_score,
    readinessScoreDelta: current.report.claim_readiness_score - previous.report.claim_readiness_score,
    resolvedIssues: [...previousFindings.keys()].filter((key) => !currentFindings.has(key)).map((key) => previousFindings.get(key) ?? key),
    addedIssues: [...currentFindings.keys()].filter((key) => !previousFindings.has(key)).map((key) => currentFindings.get(key) ?? key),
    cptChanges,
    previousAverageConfidence: averageConfidence(previous),
    newAverageConfidence: averageConfidence(current),
  };
}

function issueMap(report: AnalysisReport) {
  const entries = report.audit_findings
    .filter((finding) => finding.category !== "clean_claim")
    .map((finding) => [finding.category || finding.title || finding.message, finding.title ?? findingTitle(finding.category)] as const);
  return new Map(entries);
}

function primaryCpt(report: AnalysisReport) {
  if (!report.cpt_candidates.length) return null;
  return [...report.cpt_candidates].sort((left, right) => right.confidence - left.confidence)[0].code;
}

function averageConfidence(report: AnalysisReport) {
  if (!report.cpt_candidates.length) return 0;
  const total = report.cpt_candidates.reduce((sum, candidate) => sum + candidate.confidence, 0);
  return total / report.cpt_candidates.length;
}

function formatDelta(value: number) {
  return `${value >= 0 ? "+" : ""}${value}`;
}

function analysisModeLabel(value?: string) {
  if (value === "hybrid_ai") return "Hybrid AI mode";
  return "Rules mode";
}
