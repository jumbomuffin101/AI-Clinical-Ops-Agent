"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { ProductHeader, WorkflowSteps } from "./components/header";
import { Disclosure, FriendlyEmpty, SectionCard, StatusBadge, SummaryMetric, getStatusStyles } from "./components/ui";

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
    review_status?: string;
    claim_readiness_score: number;
    claim_readiness_status: string;
    claim_readiness_explanation: string;
    claim_readiness_reasons?: string[];
    recommended_action?: string;
    recommended_next_step?: string;
    main_issue?: string;
    detected_procedure?: string;
    analysis_mode?: string;
    ai_assist_status?: string;
    ai_provider?: string | null;
    ai_model?: string | null;
    ai_procedure_summary?: string | null;
    ai_reasoning_summary?: string | null;
    ai_documentation_gaps?: string[];
    ai_suggested_clarifications?: string[];
    ai_confidence_reasoning?: string[];
    ai_likely_procedure_family?: string | null;
    ai_likely_cpt_category?: string | null;
    ai_probable_operative_intent?: string | null;
    ai_supporting_texts?: string[];
    ai_cpt_rationales?: string[];
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

const IDENTIFIER_WARNING =
  "Potential patient identifiers detected. Remove MRNs, DOBs, names, contact information, or other patient identifiers before analysis.";

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
  {
    id: "custom-note",
    label: "Custom Note",
    title: "Custom operative note",
    note: "",
  },
];

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const selectorExamples = examples.filter((example) => ["av-fistula", "hernia-risk", "bundled-risk", "custom-note"].includes(example.id));
const SHOW_ADVANCED_DIAGNOSTICS = false;

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
  const [showRevisionHistory, setShowRevisionHistory] = useState(false);
  const [showParsedStructure, setShowParsedStructure] = useState(false);
  const [showBillingDetails, setShowBillingDetails] = useState(false);
  const [revisionImpact, setRevisionImpact] = useState<RevisionImpact | null>(null);
  const [revisionHistory, setRevisionHistory] = useState<RevisionHistoryItem[]>([]);
  const [lastAnalyzedNote, setLastAnalyzedNote] = useState<string | null>(null);
  const inputRef = useRef<HTMLDivElement | null>(null);
  const identifierWarning = containsLikelyIdentifier(`${selected.title}\n${noteText}`) ? IDENTIFIER_WARNING : null;
  const visibleReport = identifierWarning ? null : report;

  useEffect(() => {
    if (SHOW_ADVANCED_DIAGNOSTICS) {
      void loadHistory();
      void loadEvaluation();
    }
  }, []);

  useEffect(() => {
    if (!identifierWarning) return;
    setReport(null);
    setAnalysisStarted(false);
    setRevisionImpact(null);
    setLastAnalyzedNote(null);
    setShowBillingDetails(false);
  }, [identifierWarning]);

  function chooseExample(exampleId: string) {
    const example = examples.find((item) => item.id === exampleId) ?? examples[0];
    setSelectedExample(example.id);
    setNoteText(example.id === "custom-note" ? "" : example.note);
    setReport(null);
    setError(null);
    setAnalysisStarted(false);
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
      setError("Unable to complete review. Please try again.");
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
    setRevisionImpact(null);
    setRevisionHistory([]);
    setLastAnalyzedNote(null);
    setShowParsedStructure(false);
  }

  async function submitNote() {
    if (identifierWarning) {
      setError(identifierWarning);
      return;
    }
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
      if (!response.ok) throw new Error(payload?.error?.message ?? "Review request failed.");
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
      if (SHOW_ADVANCED_DIAGNOSTICS) await loadHistory();
    } catch {
      setError("Unable to complete review. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function scrollToReviewStart() {
    inputRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <main className="min-h-screen bg-[#f4f1ec] text-[#1f2d33]">
      <ProductHeader onStartReview={scrollToReviewStart} />

      <section className="mx-auto max-w-7xl px-5 py-6">
        <WorkflowSteps />

        <div ref={inputRef} className="mt-6 grid gap-6 lg:grid-cols-[minmax(360px,0.82fr)_minmax(0,1.18fr)]">
          <InputPanel
            selectedExample={selectedExample}
            noteText={noteText}
            loading={loading}
            error={error}
            onSelectExample={chooseExample}
            onChangeNote={setNoteText}
            onSubmit={submitNote}
            onClear={clearReport}
            hasReport={Boolean(visibleReport) || analysisStarted}
            submitLabel={visibleReport ? "Reanalyze Updated Note" : "Start Review"}
            identifierWarning={identifierWarning}
          />

          <div className="space-y-5">
            {identifierWarning ? (
              <IdentifierBlockedPanel />
            ) : (
              <>
                <AnalysisStagePanel visible={analysisStarted || Boolean(visibleReport)} loading={loading} complete={Boolean(visibleReport)} />
                <ResultSummary report={visibleReport} loading={loading} />
                {hasSuggestedFixes(visibleReport) ? <ImprovementSuggestions report={visibleReport} /> : null}
              </>
            )}
          </div>
        </div>

        {!identifierWarning ? <div className="mt-6 space-y-5">
          <Disclosure title="View detailed review" open={showBillingDetails} onToggle={() => setShowBillingDetails((value) => !value)}>
            <MoreDetails
              report={visibleReport}
              evaluation={evaluation}
              evaluationLoading={evaluationLoading}
              history={history}
              historyLoading={historyLoading}
              revisionImpact={revisionImpact}
              revisionHistory={revisionHistory}
              reviewMetadata={visibleReport ? reviewMetadata(visibleReport) : null}
              onLoadAnalysis={loadAnalysis}
              sections={{
                parsed: showParsedStructure,
                revision: showRevisionHistory,
              }}
              onToggleSection={(section) => {
                if (section === "parsed") setShowParsedStructure((value) => !value);
                if (section === "revision") setShowRevisionHistory((value) => !value);
              }}
            />
          </Disclosure>
        </div> : null}
      </section>
      <footer className="mx-auto mt-4 border-t border-[#dce9e7] px-5 py-8 text-center text-xs font-medium tracking-[0.04em] text-[#71817d]">
        Created by Aryan Rawat
      </footer>
    </main>
  );
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
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
  identifierWarning,
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
  identifierWarning: string | null;
}) {
  return (
    <section className="rounded-2xl border border-[#dce9e7] bg-white/86 p-6 shadow-[0_14px_36px_rgba(49,84,91,0.05)]">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-[#789093]">Step 1</p>
        <h2 className="mt-1 text-xl font-semibold text-[#17343c]">Note Input</h2>
        <p className="mt-2 text-sm leading-6 text-[#607678]">
          Use an example note or paste your own synthetic note. The system will identify the procedure, flag documentation risks, and suggest what a reviewer should check next.
        </p>
      </div>

      <label className="mt-6 block text-sm font-semibold text-[#34464a]">Start with an example or enter your own note</label>
      <p className="mt-1 text-sm leading-6 text-[#607678]">You can use an example note or enter your own de-identified/synthetic operative note.</p>
      <select
        value={selectedExample}
        onChange={(event) => onSelectExample(event.target.value)}
        className="mt-2 h-11 w-full rounded-xl border border-[#cfe0dd] bg-[#fbfefd] px-3 text-sm outline-none focus:border-[#206b63] focus:ring-2 focus:ring-[#d6ebe8]"
      >
        {selectorExamples.map((example) => (
          <option key={example.id} value={example.id}>
            {example.label}
          </option>
        ))}
      </select>

      <textarea
        value={noteText}
        onChange={(event) => onChangeNote(event.target.value)}
        maxLength={20000}
        placeholder="Paste a de-identified or synthetic operative note here..."
        className="mt-4 min-h-[410px] w-full resize-y rounded-xl border border-[#cfe0dd] bg-[#fbfefd] p-4 font-mono text-sm leading-6 outline-none focus:border-[#206b63] focus:ring-2 focus:ring-[#d6ebe8]"
      />
      <div className="mt-3 flex items-center justify-between gap-4 text-xs text-[#71817d]">
        <span>{noteText.length.toLocaleString()} / 20,000 characters</span>
        <span>Use only de-identified or synthetic notes.</span>
      </div>
      <p className="mt-2 rounded-xl border border-[#d8e8e4] bg-[#f7fbfa] px-3 py-2 text-xs leading-5 text-[#607678]">
        Use only de-identified or synthetic notes. This environment is not configured for patient-identifiable information.
      </p>
      {identifierWarning ? (
        <div className="mt-3 rounded-2xl border border-[#efc2ba] bg-[#fbebe8] p-4 shadow-[0_10px_22px_rgba(159,47,36,0.08)]">
          <p className="text-sm font-semibold text-[#9f2f24]">Analysis blocked</p>
          <p className="mt-1 text-sm leading-6 text-[#8f3b2d]">{identifierWarning}</p>
        </div>
      ) : null}

      <button
        type="button"
        onClick={onSubmit}
        disabled={loading || Boolean(identifierWarning)}
        className="mt-6 w-full rounded-xl bg-[#206b63] px-4 py-3.5 text-sm font-semibold text-white shadow-[0_10px_22px_rgba(32,107,99,0.18)] hover:bg-[#195950] disabled:cursor-not-allowed disabled:bg-[#9bb5ad]"
      >
        {loading ? "Analyzing note..." : submitLabel}
      </button>
      {hasReport ? (
        <button
          type="button"
          onClick={onClear}
          className="mt-3 w-full rounded-xl border border-[#cfe0dd] bg-[#fbfefd] px-4 py-3 text-sm font-semibold text-[#31545b] hover:bg-[#f4fbf9]"
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
    "Identifying procedures",
    "Checking note structure",
    "Reviewing documentation risks",
    "Reviewing coding support",
    "Preparing reviewer next steps",
  ];

  if (!visible) {
    return (
      <section className="rounded-2xl border border-[#dce9e7] bg-white/82 p-6 shadow-[0_12px_32px_rgba(49,84,91,0.05)]">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#789093]">Step 2</p>
        <h2 className="mt-1 text-xl font-semibold text-[#17343c]">Analysis will run here</h2>
        <p className="mt-2 text-sm leading-6 text-[#607678]">After you analyze a note, this panel will show the review workflow before the summary appears.</p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-[#dce9e7] bg-[#fbfefd] p-6 shadow-[0_14px_36px_rgba(49,84,91,0.06)]">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#2d7772]">Step 2</p>
          <h2 className="mt-1 text-xl font-semibold text-[#17343c]">{loading ? "Analyzing note" : complete ? "Analysis completed" : "Analysis ready"}</h2>
          <p className="mt-2 text-sm leading-6 text-[#607678]">Simulating how a clinical operations reviewer checks procedure clarity and documentation risk.</p>
        </div>
        <StatusBadge status={loading ? "Running" : "Ready"} />
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {checks.map((item, index) => (
          <div key={item} className="flex items-center gap-3 rounded-xl bg-white/85 px-4 py-3 text-sm text-[#31545b]">
            <span
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                loading && index > 1 ? "bg-[#eef3f2] text-[#8b9d9e]" : "bg-[#e1f2ef] text-[#206b63]"
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

function IdentifierBlockedPanel() {
  return (
    <section className="rounded-2xl border border-[#efc2ba] bg-[#fffafa] p-6 shadow-[0_14px_36px_rgba(159,47,36,0.06)]">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#9f2f24]">Analysis unavailable</p>
      <h2 className="mt-2 text-xl font-semibold text-[#17343c]">Remove patient identifiers before continuing.</h2>
      <p className="mt-3 text-sm leading-6 text-[#6f5f5d]">
        The current note appears to contain patient-identifiable information. Remove MRNs, DOBs, names, contact information, or other identifiers before analysis.
      </p>
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
          <p className="mt-2 text-sm leading-6 text-[#667774]">Shows how the revised documentation changed review readiness and audit risk.</p>
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
  const status = report ? displayReviewStatus(report) : loading ? "Running" : "Not run";
  const summaryStyles = getStatusStyles(status);
  return (
    <section className={`rounded-2xl border p-6 shadow-[0_14px_36px_rgba(49,84,91,0.05)] ${summaryStyles.summaryCard}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.1em] text-[#789093]">Step 3</p>
          <h2 className="mt-1 text-xl font-semibold text-[#17343c]">Review Summary</h2>
          <p className="mt-2 text-sm leading-6 text-[#607678]">
            Status-first clinical operations review for a human reviewer. This is not a final coding decision.
          </p>
          {report && displayReviewStatus(report) !== "Ready" ? (
            <div className="mt-3 rounded-xl border border-[#dce9e7] bg-[#f7fbfa] px-4 py-3 text-xs leading-5 text-[#607678]">
              <span className="font-semibold text-[#31545b]">{reviewModeMessage(report)}</span>
            </div>
          ) : null}
        </div>
        <StatusBadge status={status} />
      </div>

      {report ? (
        <>
          <div className="mt-6 grid min-w-0 grid-cols-1 auto-rows-fr gap-4 md:grid-cols-2">
            <SummaryMetric label="Review Status" value={displayReviewStatus(report)} status={displayReviewStatus(report)} />
            <SummaryMetric label="Detected Procedure" value={detectedProcedureLabel(report)} title={detectedProcedureLabel(report)} clamp="" />
            <SummaryMetric label="Main Issue" value={reviewMainIssue(report)} clamp="" />
            <SummaryMetric label="Recommended Next Step" value={nextStepLabel(report)} title={nextStepLabel(report)} clamp="" />
          </div>
          <div className="mt-5 rounded-xl border border-[#dce9e7] bg-[#f4fbf9] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#2d7772]">Coding Recommendation</p>
            <p className="mt-2 text-base font-semibold text-[#17343c]">{billingCodeLabel(report)}</p>
            {needsCoderReviewBeforeCodeSelection(report) ? (
              <p className="mt-2 text-sm leading-6 text-[#586b69]">
                {hasProcedureDocumentationConflict(report)
                  ? "Procedure documentation should be clarified before selecting a CPT."
                  : "The system identified the procedure, but coder confirmation is needed before selecting a CPT."}
              </p>
            ) : null}
          </div>
          <div className="mt-4 rounded-xl bg-[#f7fbfa] p-4">
            <p className="mb-3 text-sm font-semibold text-[#31545b]">Plain-English review</p>
            <p className="mb-3 text-sm leading-6 text-[#607678]">{reportNarrative(report)}</p>
          </div>
        </>
      ) : (
        <FriendlyEmpty title="Your report will appear here after analysis." text="Choose an example note to see how the system works." />
      )}
    </section>
  );
}

function CptCandidates({ report }: { report: AnalysisReport | null }) {
  const meaningfulCandidates = (report?.cpt_candidates ?? []).filter(isMeaningfulCpt);
  return (
    <SectionCard title="Coding Recommendation Details" explainer="Shows CPT candidates only when the local review library has enough support to make them useful.">
      {report ? (
        meaningfulCandidates.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-[#e4ddd2] text-xs uppercase tracking-[0.08em] text-[#7a8a88]">
                  <th className="py-3 pr-4">Suggested code</th>
                  <th className="py-3 pr-4">What it represents</th>
                  <th className="py-3 pr-4">Review tier</th>
                  <th className="py-3 pr-4">Modifier</th>
                </tr>
              </thead>
              <tbody>
                {meaningfulCandidates.map((candidate) => (
                  <tr key={`${candidate.code}-${candidate.procedure_name}`} className="border-b border-[#f0e9df]">
                    <td className="py-3 pr-4 font-mono font-semibold text-[#1f2d33]">{candidate.code}</td>
                    <td className="py-3 pr-4">
                      <p className="font-medium text-[#34464a]">{candidate.procedure_name}</p>
                      <p className="mt-1 text-xs leading-5 text-[#71817d]">{candidate.description}</p>
                    </td>
                    <td className="py-3 pr-4">{cptConfidenceTier(candidate)}</td>
                    <td className="py-3 pr-4">{candidate.modifiers.length ? candidate.modifiers.join(", ") : "Needs clarification"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="rounded-xl border border-[#ead8c0] bg-[#fbf2e6] p-4">
            <p className="font-semibold text-[#7a5428]">Coder review is recommended before selecting a CPT code.</p>
          </div>
        )
      ) : (
        <FriendlyEmpty title="Coding recommendation details will appear after analysis." text="Unsupported codes are hidden from the main summary so they do not look like recommendations." />
      )}
    </SectionCard>
  );
}

function MoreDetails({
  report,
  evaluation,
  evaluationLoading,
  history,
  historyLoading,
  revisionImpact,
  revisionHistory,
  reviewMetadata,
  onLoadAnalysis,
  sections,
  onToggleSection,
}: {
  report: AnalysisReport | null;
  evaluation: EvaluationSummary | null;
  evaluationLoading: boolean;
  history: AnalysisHistoryItem[];
  historyLoading: boolean;
  revisionImpact: RevisionImpact | null;
  revisionHistory: RevisionHistoryItem[];
  reviewMetadata: Array<{ label: string; value: string }> | null;
  onLoadAnalysis: (id: string) => void;
  sections: { parsed: boolean; revision: boolean };
  onToggleSection: (section: "parsed" | "revision") => void;
}) {
  const [openSections, setOpenSections] = useState({
    ai: false,
    coding: false,
    risks: false,
    advanced: false,
  });
  const toggleLocalSection = (section: keyof typeof openSections) => {
    setOpenSections((current) => ({ ...current, [section]: !current[section] }));
  };

  return (
    <div className="space-y-3">
      <DetailAccordion title="AI Interpretation" open={openSections.ai} onToggle={() => toggleLocalSection("ai")}>
        <AIReviewInsights report={report} />
      </DetailAccordion>

      <DetailAccordion title="Coding Recommendation Details" open={openSections.coding} onToggle={() => toggleLocalSection("coding")}>
        <CptCandidates report={report} />
      </DetailAccordion>

      <DetailAccordion title="Billing Risks" open={openSections.risks} onToggle={() => toggleLocalSection("risks")}>
        <AuditFindings report={report} />
      </DetailAccordion>

      <DetailAccordion title="Parsed Note Structure" open={sections.parsed} onToggle={() => onToggleSection("parsed")}>
        <ParsedNoteStructure report={report} />
      </DetailAccordion>

      <DetailAccordion title="Revision History" open={sections.revision} onToggle={() => onToggleSection("revision")}>
        {revisionImpact ? <RevisionImpactCard impact={revisionImpact} /> : null}
        <div className={revisionImpact ? "mt-4" : undefined}>
          <RevisionHistoryPanel items={revisionHistory} />
        </div>
      </DetailAccordion>

      {SHOW_ADVANCED_DIAGNOSTICS ? (
        <DetailAccordion title="Advanced Diagnostics" open={openSections.advanced} onToggle={() => toggleLocalSection("advanced")}>
          <div className="space-y-4">
            <RecentAnalyses history={history} loading={historyLoading} onLoad={onLoadAnalysis} />
            <SystemEvaluation evaluation={evaluation} loading={evaluationLoading} />
            <SectionCard title="Technical Analysis Metadata" explainer="Internal run information for local troubleshooting only.">
              <TechnicalMetadata rows={reviewMetadata} />
            </SectionCard>
          </div>
        </DetailAccordion>
      ) : null}
    </div>
  );
}

function DetailAccordion({
  title,
  open,
  onToggle,
  children,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-[#dce9e7] bg-white/70">
      <button
        type="button"
        onClick={onToggle}
        className="flex min-h-14 w-full items-center justify-between gap-4 px-4 py-4 text-left text-sm font-semibold text-[#17343c] transition hover:bg-[#f4fbf9]"
        aria-expanded={open}
      >
        <span>{title}</span>
        <span
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[#cfe4df] bg-[#edf7f5] text-sm font-semibold leading-none text-[#206b63] transition-transform ${
            open ? "rotate-90" : ""
          }`}
          aria-hidden="true"
        >
          &gt;
        </span>
      </button>
      {open ? <div className="border-t border-[#e7efed] bg-[#fbfefd] p-4">{children}</div> : null}
    </div>
  );
}

function TechnicalMetadata({ rows }: { rows: Array<{ label: string; value: string }> | null }) {
  if (!rows) {
    return <FriendlyEmpty title="No analysis metadata yet." text="Run a review to see analysis metadata." />;
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {rows.map((row) => (
        <div key={row.label} className="rounded-xl border border-[#dce9e7] bg-[#f9fcfb] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#789093]">{row.label}</p>
          <p className="mt-2 text-sm font-semibold text-[#31545b]">{row.value}</p>
        </div>
      ))}
    </div>
  );
}

function SystemEvaluation({ evaluation, loading }: { evaluation: EvaluationSummary | null; loading: boolean }) {
  return (
    <SectionCard
      title="System Evaluation"
      explainer="This evaluation uses synthetic operative notes only. It measures whether the system consistently produces the expected CPT, risk status, and audit findings for known review cases."
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
              These metrics compare pipeline outputs against a small gold-standard file for the included synthetic notes. They demonstrate consistency for included cases, not clinical or billing correctness on real patient records.
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
          text="The API calculates these metrics by running the synthetic notes through the same review pipeline used by the app."
        />
      )}
    </SectionCard>
  );
}

function AuditFindings({ report }: { report: AnalysisReport | null }) {
  const findings = (report?.audit_findings ?? []).filter((finding) => finding.category !== "clean_claim" && finding.severity !== "info");
  return (
    <SectionCard title="Billing Risks" explainer="Documentation or billing concerns that should be reviewed before submission.">
      {report ? (
        findings.length ? (
          <div className="space-y-3">
            {findings.map((finding, index) => (
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
          <FriendlyEmpty title="No billing risks were identified for this review." text="No reviewer action is required based on the current billing-risk checks." />
        )
      ) : (
        <FriendlyEmpty title="No review risks yet." text="After analysis, missing details, ambiguity, or clinical operations review concerns will be listed here." />
      )}
    </SectionCard>
  );
}

function ImprovementSuggestions({ report }: { report: AnalysisReport | null }) {
  const findings = suggestedFixFindings(report);
  const reviewStatus = report ? displayReviewStatus(report) : "Needs Review";
  return (
    <SectionCard
      title="Suggested Fixes"
      explainer="Practical documentation changes that would help a reviewer assess the note more confidently."
    >
      {report ? (
        findings.length ? (
          <div className="grid gap-4 lg:grid-cols-2">
            {findings.map((finding, index) => (
              <div key={`${finding.category}-suggestion-${index}`} className="rounded-xl border border-[#e4ddd2] bg-[#fffaf4] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[#34464a]">{displayFindingTitle(finding, report)}</p>
                    <p className="mt-2 text-sm leading-6 text-[#586b69]">{improvementForFinding(finding, report)}</p>
                  </div>
                  <StatusBadge status={suggestionBadgeStatus(finding, reviewStatus)} />
                </div>
                <div className="mt-4 rounded-lg bg-[#fffdfa] p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#7a8a88]">Why this matters</p>
                  <p className="mt-2 text-sm leading-6 text-[#667774]">{whyImprovementMatters(finding, report)}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-[#c4dad2] bg-[#edf6f2] p-4">
            <p className="font-semibold text-[#245c52]">No documentation gaps were flagged by the local review checks.</p>
            <p className="mt-2 text-sm leading-6 text-[#586b69]">A reviewer would still perform standard human validation before submission.</p>
          </div>
        )
      ) : (
        <FriendlyEmpty title="Improvement suggestions will appear after analysis." text="If the note has missing details or risk flags, this section will explain how to revise it and why it matters." />
      )}
    </SectionCard>
  );
}

function suggestionBadgeStatus(finding: AuditFinding, reviewStatus: string) {
  if (reviewStatus === "High Risk" && finding.severity === "high") return "High Risk";
  return "Needs Review";
}

function suggestedFixFindings(report: AnalysisReport | null) {
  if (!report) return [];
  const status = displayReviewStatus(report);
  const limit = status === "High Risk" ? 4 : status === "Needs Review" ? 3 : 0;
  if (limit === 0) {
    return report.audit_findings.filter((finding) => finding.category !== "clean_claim" && finding.severity === "high").slice(0, 1);
  }
  return report.audit_findings
    .filter((finding) => {
      if (finding.category === "clean_claim") return false;
      if (isLateralityFinding(finding) && !isLateralityRelevant(report)) return false;
      if (status === "Needs Review") return finding.severity !== "info";
      return finding.severity === "high" || finding.severity === "medium";
    })
    .sort((left, right) => fixPriority(right, report) - fixPriority(left, report))
    .slice(0, limit);
}

function fixPriority(finding: AuditFinding, report: AnalysisReport) {
  const severity = finding.severity === "high" ? 100 : finding.severity === "medium" ? 70 : finding.severity === "low" ? 30 : 0;
  const actionable = (finding.suggested_action || finding.documentation_improvement || improvementForFinding(finding, report)).length > 24 ? 12 : 0;
  const specific = isSpecificFix(finding, report) ? 10 : 0;
  const genericPenalty = isGenericFix(finding) ? -12 : 0;
  return severity + specific + actionable + genericPenalty;
}

function isSpecificFix(finding: AuditFinding, report: AnalysisReport) {
  if (finding.category === "missing_laterality" || finding.category === "bundling_conflict") return true;
  if (isGiSurgeryReview(report) && ["low_confidence", "unsupported_code"].includes(finding.category)) return true;
  const text = `${finding.title ?? ""} ${finding.message} ${finding.explanation ?? ""} ${finding.suggested_action ?? ""}`.toLowerCase();
  return ["laterality", "cholangiogram", "anastomosis", "resection", "bowel", "additional procedure"].some((term) => text.includes(term));
}

function isGenericFix(finding: AuditFinding) {
  const text = `${finding.category} ${finding.title ?? ""} ${finding.message} ${finding.explanation ?? ""}`.toLowerCase();
  return ["ai_documentation_gap", "ai_audit_concern"].includes(finding.category) || ["incomplete documentation", "documentation gap"].some((term) => text.includes(term));
}

function isLateralityFinding(finding: AuditFinding) {
  const text = `${finding.category} ${finding.title ?? ""} ${finding.message} ${finding.explanation ?? ""} ${finding.suggested_action ?? ""} ${finding.documentation_improvement ?? ""}`.toLowerCase();
  return ["laterality", "left or right", "left/right", "side"].some((term) => text.includes(term));
}

function AIReviewInsights({ report }: { report: AnalysisReport | null }) {
  if (!report) {
    return (
      <section className="rounded-2xl border border-[#dce9e7] bg-white/78 p-5 shadow-[0_12px_30px_rgba(49,84,91,0.045)]">
        <h2 className="text-lg font-semibold text-[#17343c]">AI Interpretation</h2>
        <p className="mt-2 text-sm leading-6 text-[#607678]">AI interpretation appears when additional note understanding is needed.</p>
      </section>
    );
  }

  const usedAI = isAiAssisted(report);
  if (!usedAI) {
    const providerError = report.report.ai_assist_status?.toLowerCase().includes("unavailable");
    return (
      <section className="rounded-2xl border border-[#dce9e7] bg-white/78 p-5 shadow-[0_12px_30px_rgba(49,84,91,0.045)]">
        <h2 className="text-lg font-semibold text-[#17343c]">AI Interpretation</h2>
        <p className="mt-2 text-sm leading-6 text-[#607678]">
          {providerError
            ? "AI interpretation was unavailable for this review. The deterministic review result remains available."
            : "AI was not required for this review. The note matched a deterministic review pattern."}
        </p>
      </section>
    );
  }

  return (
    <SectionCard title="AI Interpretation" explainer="Draft interpretation of the operative note. Deterministic checks still control risks, supported codes, and review status.">
      <div className="grid gap-4 lg:grid-cols-2">
        <InsightBlock
          title="AI interpretation summary"
          body={report.report.ai_procedure_summary ?? report.report.ai_reasoning_summary ?? "No interpretation summary returned."}
          details={[
            report.report.ai_reasoning_summary ?? null,
          ]}
        />
        {report.report.ai_likely_procedure_family || report.report.ai_likely_cpt_category ? (
          <InsightBlock
            title="Procedure classification"
            body="AI-supported classification for reviewer context."
            details={[
              report.report.ai_likely_procedure_family ? `Procedure family: ${report.report.ai_likely_procedure_family}` : null,
              report.report.ai_likely_cpt_category ? `CPT category: ${report.report.ai_likely_cpt_category}` : null,
            ]}
          />
        ) : null}
        {(report.report.ai_supporting_texts ?? []).length ? (
          <InsightBlock title="Supporting evidence" body="Relevant operative note evidence supporting the interpretation." details={report.report.ai_supporting_texts ?? []} />
        ) : null}
        {(report.report.ai_suggested_clarifications ?? []).length ? (
          <InsightBlock title="Suggested clarifications" body="Questions to resolve before relying on the review for coding." details={report.report.ai_suggested_clarifications ?? []} />
        ) : null}
      </div>
    </SectionCard>
  );
}

function InsightBlock({ title, body, details }: { title: string; body: string; details: Array<string | null> }) {
  const visibleDetails = details.filter(Boolean) as string[];
  return (
    <div className="rounded-xl border border-[#e4ddd2] bg-[#fffaf4] p-4">
      <h3 className="text-sm font-semibold text-[#34464a]">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-[#667774]">{body}</p>
      {visibleDetails.length ? (
        <ul className="mt-3 space-y-2 text-sm text-[#34464a]">
          {visibleDetails.map((item) => (
            <li key={item} className="rounded-lg bg-[#fffdfa] px-3 py-2">
              {item}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
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
        <FriendlyEmpty title="Parsed note structure will appear after analysis." text="The parser will show detected sections, anatomy, laterality, and missing critical sections before the review output." />
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
    <SectionCard title="Recent Reviews" explainer="Previously generated reviews from this environment.">
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
                <span className="text-xs text-[#71817d]">{historyCodeLabel(item.top_cpt_code)}</span>
              </div>
              <p className="mt-2 text-xs text-[#71817d]">{new Date(item.created_at).toLocaleString()}</p>
              <div className="mt-3 flex items-center justify-between gap-3 text-sm">
                <StatusBadge status={item.claim_readiness_status} />
                <span className="text-xs text-[#71817d]">{historyCodeLabel(item.top_cpt_code)}</span>
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
    <SectionCard title="Revision History" explainer="Tracks note edits made during this browser session and how each revision changed review status.">
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

function hasSuggestedFixes(report: AnalysisReport | null) {
  return suggestedFixFindings(report).length > 0;
}

function containsLikelyIdentifier(text: string) {
  const patterns = [
    /\bMRN[:\s#-]*\d{4,}\b/i,
    /\bDOB[:\s-]*(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b/i,
    /\b(?:Patient\s+Name|Name)[:\s-]+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b/i,
    /\b\d{3}-\d{2}-\d{4}\b/,
    /\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b/,
    /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i,
    /\b\d{1,6}\s+[A-Za-z0-9.\s]{2,40}\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)\b/i,
  ];
  return patterns.some((pattern) => pattern.test(text));
}

function isMeaningfulCpt(candidate: CPTCodeCandidate) {
  return candidate.code !== "99999" && candidate.supported_by_docs && candidate.confidence >= 0.75;
}

function meaningfulCptCandidate(report: AnalysisReport) {
  return report.cpt_candidates.find(isMeaningfulCpt) ?? null;
}

function billingCodeLabel(report: AnalysisReport) {
  if (hasProcedureDocumentationConflict(report)) return "Coder review needed";
  const candidate = meaningfulCptCandidate(report);
  if (!candidate) return "Coder review needed";
  return `Suggested code: ${candidate.code}`;
}

function needsCoderReviewBeforeCodeSelection(report: AnalysisReport) {
  return hasProcedureDocumentationConflict(report) || !meaningfulCptCandidate(report);
}

function historyCodeLabel(code?: string | null) {
  if (!code || code === "99999") return "Coder review needed";
  return code;
}

function reviewModeMessage(report: AnalysisReport) {
  return isAiAssisted(report) ? "AI-assisted review used to interpret the note." : "Standard review completed.";
}

function reviewMetadata(report: AnalysisReport) {
  return [
    { label: "Review type", value: analysisModeLabel(report.report.analysis_mode) },
    { label: "Provider", value: report.report.ai_provider ? providerLabel(report.report.ai_provider) : "Not used" },
    { label: "Model", value: report.report.ai_model ?? "Not used" },
    { label: "AI status", value: report.report.ai_assist_status ?? "No AI status recorded" },
  ];
}

function detectedProcedureLabel(report: AnalysisReport) {
  return report.report.detected_procedure ?? "Procedure not reported";
}

function aiReviewText(report: AnalysisReport) {
  return [
    report.report.ai_procedure_summary ?? "",
    report.report.ai_reasoning_summary ?? "",
    report.report.ai_probable_operative_intent ?? "",
    report.report.ai_likely_procedure_family ?? "",
    report.structured_note?.detected_anatomy ?? "",
    report.structured_note?.raw_text ?? "",
    ...(report.report.ai_supporting_texts ?? []),
    ...report.extracted_procedures.map((procedure) => `${procedure.name} ${procedure.body_site ?? ""} ${procedure.evidence ?? ""}`),
  ]
    .join(" ")
    .toLowerCase();
}

function isGiSurgeryReview(report: AnalysisReport) {
  const text = aiReviewText(report);
  return report.report.ai_likely_procedure_family === "GI surgery" || ["bowel", "ileum", "ileal", "anastomosis", "laparotomy", "colectomy"].some((term) => text.includes(term));
}

function isLateralityRelevant(report: AnalysisReport) {
  const text = [
    aiReviewText(report),
    ...report.cpt_candidates.map((candidate) => `${candidate.procedure_name} ${candidate.description} ${candidate.code}`),
  ].join(" ").toLowerCase();
  if (["bowel", "appendectomy", "appendix", "cholecystectomy", "gallbladder", "colectomy", "laparotomy", "abdominal exploration"].some((term) => text.includes(term))) {
    return false;
  }
  return ["hernia", "fistula", "extremity", "breast", "kidney", "renal", "eye", "orthopedic", "unilateral", "femoral", "carotid", "angiogram"].some((term) => text.includes(term));
}

function keyAnatomyLabel(report: AnalysisReport) {
  const text = aiReviewText(report);
  if (text.includes("distal ileum")) return "the distal ileum";
  if (text.includes("ileum") || text.includes("ileal")) return "the ileum";
  if (text.includes("small bowel") || text.includes("small intestine")) return "the small bowel";
  if (text.includes("colon") || text.includes("colectomy")) return "the colon";
  return report.structured_note?.detected_anatomy ?? "the gastrointestinal tract";
}

function keyOperativeDetails(report: AnalysisReport) {
  const text = aiReviewText(report);
  const details = [];
  if (text.includes("perforation")) details.push("bowel perforation");
  if (text.includes("stapled") && text.includes("anastom")) details.push("stapled anastomosis");
  else if (text.includes("anastom")) details.push("anastomosis");
  return details.join(" and ");
}

function nextStepLabel(report: AnalysisReport) {
  return report.report.recommended_next_step ?? report.report.recommended_action ?? "No recommended next step reported.";
}

function displayReviewStatus(report: AnalysisReport) {
  return report.report.review_status ?? report.report.claim_readiness_status;
}

function reviewIssueLabel(issue: string) {
  if (issue === "Unsupported procedure" || issue === "Billing code review needed") return "Coder review needed";
  return issue;
}

function reviewMainIssue(report: AnalysisReport) {
  return report.report.main_issue ?? "No major issues";
}

function reportNarrative(report: AnalysisReport) {
  const issue = reviewMainIssue(report);
  const action = nextStepLabel(report);
  const procedure = detectedProcedureLabel(report).toLowerCase();
  const family = report.report.ai_likely_procedure_family;
  if (issue === "Procedure documentation conflict") {
    return "The documented procedure and operative details describe different surgeries. Coding should not proceed until documentation is reconciled.";
  }
  if (!meaningfulCptCandidate(report)) {
    if (isGiSurgeryReview(report)) {
      const anatomy = keyAnatomyLabel(report);
      const intent = report.report.ai_probable_operative_intent || "operative management";
      const operativeDetails = keyOperativeDetails(report);
      return `The note describes ${procedure}. The app identified this as a ${family ?? "GI surgery"} case involving ${anatomy}. Operative intent appears to be ${intent}${operativeDetails ? `, with ${operativeDetails}` : ""}. Coder confirmation is needed because bowel surgery coding depends on resection extent, anastomosis details, additional procedures, and final CPT selection.`;
    }
    return `The note describes ${procedure}. The local review library does not contain enough support to assign a confident CPT. Coder confirmation is recommended before a coding decision.`;
  }
  if (displayReviewStatus(report) === "Ready") {
    return `The note is marked Ready for standard clinical operations review because the procedure is documented clearly and the review checks did not find major risks. Recommended next step: ${action}`;
  }
  if (issue === "Missing laterality") {
    return `The note needs review because laterality was not clearly documented. Clarifying whether the procedure was performed on the left or right side would reduce modifier ambiguity.`;
  }
  if (issue === "Bundling conflict") {
    return `The note is high risk because the documentation produced a possible bundled-code conflict. A human reviewer should decide which service should be billed.`;
  }
  return `The note is marked ${displayReviewStatus(report)} because the review found ${issue.toLowerCase()}. Recommended next step: ${action}`;
}

function hasProcedureDocumentationConflict(report: AnalysisReport) {
  return (
    reviewIssueLabel(report.report.main_issue ?? "") === "Procedure documentation conflict" ||
    report.audit_findings.some((finding) =>
      ["procedure_documentation_conflict", "conflicting_documentation", "conflicting_procedures"].includes(finding.category)
    )
  );
}

function findingTitle(category: string) {
  if (category === "bundling_conflict") return "Bundling conflict detected";
  if (category === "procedure_documentation_conflict" || category === "conflicting_documentation" || category === "conflicting_procedures") return "Procedure documentation conflict";
  if (category === "low_confidence") return "Low confidence coding";
  if (category === "missing_laterality") return "Missing laterality";
  if (category === "unsupported_code") return "Coder review needed";
  if (category === "clean_claim") return "No major billing risks found";
  return readableCategory(category);
}

function displayFindingTitle(finding: AuditFinding, report: AnalysisReport) {
  if (finding.category === "unsupported_code" && isGiSurgeryReview(report)) return "Complex procedure requires coder review";
  if (finding.title === "Unsupported procedure" || finding.title === "Unsupported or unclear procedure") return findingTitle(finding.category);
  return finding.title ?? findingTitle(finding.category);
}

function improvementForFinding(finding: AuditFinding, report?: AnalysisReport | null) {
  if (finding.category === "missing_laterality") return "Document whether the procedure was performed on the left or right side.";
  if (finding.category === "low_confidence" && report && isGiSurgeryReview(report)) {
    return "Confirm bowel resection extent, anastomosis details, whether additional procedures were performed, and final CPT selection.";
  }
  if (finding.category === "low_confidence") return "Clarify the exact procedure performed and whether it was diagnostic or therapeutic.";
  if (finding.category === "bundling_conflict") return "Review whether both procedures should be billed together or select the single supported definitive code.";
  if (finding.category === "procedure_documentation_conflict" || finding.category === "conflicting_documentation" || finding.category === "conflicting_procedures") {
    return "Clarify whether the procedure, findings, technique, and postoperative diagnosis describe the same service.";
  }
  if (finding.category === "unsupported_code" && report && isGiSurgeryReview(report)) {
    return "Confirm bowel resection extent, anastomosis details, whether additional procedures were performed, and final CPT selection.";
  }
  if (finding.category === "unsupported_code") return "Confirm the correct billable procedure and supporting reference before coding.";
  return finding.suggested_action ?? finding.recommendation;
}

function whyImprovementMatters(finding: AuditFinding, report?: AnalysisReport | null) {
  if (finding.category === "missing_laterality") return "Reviewers need laterality to select LT or RT modifiers and avoid payer follow-up.";
  if (finding.category === "low_confidence") return "Clear procedure intent improves CPT selection, coding confidence, and reimbursement predictability.";
  if (finding.category === "bundling_conflict") return "Bundled services may be denied or create billing compliance risk if both codes are submitted.";
  if (finding.category === "procedure_documentation_conflict" || finding.category === "conflicting_documentation" || finding.category === "conflicting_procedures") {
    return "Procedure and diagnosis mismatches can produce incorrect coding decisions unless they are resolved first.";
  }
  if (["unsupported_code", "low_confidence"].includes(finding.category) && report && isGiSurgeryReview(report)) {
    return "Bowel surgery coding depends on the segment treated, resection extent, anastomosis, and whether any additional services are separately supported.";
  }
  if (finding.category === "unsupported_code") return "Unsupported codes create denial and compliance risk during review.";
  return "Cleaner documentation helps reviewers make a more confident coding decision.";
}

function compareReports(previous: AnalysisReport, current: AnalysisReport): RevisionImpact {
  const previousFindings = issueMap(previous);
  const currentFindings = issueMap(current);
  const previousCpt = primaryCpt(previous);
  const currentCpt = primaryCpt(current);
  const cptChanges = previousCpt === currentCpt ? [] : [{ from: previousCpt, to: currentCpt }];

  return {
    previousClaimStatus: displayReviewStatus(previous),
    newClaimStatus: displayReviewStatus(current),
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

function cptConfidenceTier(candidate: CPTCodeCandidate) {
  if (candidate.code === "99999" || !candidate.supported_by_docs || candidate.confidence < 0.7) {
    return "Needs human coding review";
  }
  if (candidate.confidence < 0.85) {
    return "Possible CPT candidate";
  }
  return "High confidence CPT match";
}

function formatDelta(value: number) {
  return `${value >= 0 ? "+" : ""}${value}`;
}

function analysisModeLabel(value?: string) {
  if (value === "hybrid_ai" || value === "Hybrid AI mode") return "AI-assisted review";
  return "Standard review";
}

function isAiAssisted(report: AnalysisReport) {
  return report.report.analysis_mode === "hybrid_ai" || report.report.analysis_mode === "Hybrid AI mode";
}

function providerLabel(value: string) {
  if (value === "groq") return "Groq";
  if (value === "openrouter") return "OpenRouter";
  return value;
}
