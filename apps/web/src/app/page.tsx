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
  evidence_used: EvidenceSnippet[];
};

type ReimbursementEstimate = {
  code: string;
  allowed_amount: number;
  currency: string;
  source: string;
};

type AnalysisReport = {
  id: string;
  summary: string;
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
  const [error, setError] = useState<string | null>(null);
  const [copyState, setCopyState] = useState("Copy JSON");
  const [showEvidence, setShowEvidence] = useState(false);
  const [showJson, setShowJson] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    void loadHistory();
  }, []);

  function chooseExample(exampleId: string) {
    const example = examples.find((item) => item.id === exampleId) ?? examples[0];
    setSelectedExample(example.id);
    setNoteText(example.note);
    setReport(null);
    setError(null);
    setCopyState("Copy JSON");
    setShowEvidence(false);
    setShowJson(false);
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

  async function loadAnalysis(id: string) {
    setError(null);
    const response = await fetch(`${apiBaseUrl}/api/analyses/${id}`);
    const payload = await response.json();
    if (!response.ok) {
      setError("Could not generate report. Check that the backend API is running and try again.");
      return;
    }
    setReport(payload);
    setCopyState("Copy JSON");
  }

  async function submitNote() {
    if (noteText.trim().length < 50) {
      setError("Please choose an example or enter a synthetic operative note.");
      return;
    }

    setLoading(true);
    setError(null);
    setCopyState("Copy JSON");
    try {
      const response = await fetch(`${apiBaseUrl}/api/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: selected.title, note_text: noteText }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message ?? "API request failed.");
      setReport(payload);
      await loadHistory();
    } catch {
      setError("Could not generate report. Check that the backend API is running and try again.");
    } finally {
      setLoading(false);
    }
  }

  async function fetchExport(id: string) {
    const response = await fetch(`${apiBaseUrl}/api/analyses/${id}/export`);
    if (!response.ok) return report;
    return response.json();
  }

  async function copyJson() {
    if (!report) return;
    const exportPayload = await fetchExport(report.id);
    await navigator.clipboard.writeText(JSON.stringify(exportPayload, null, 2));
    setCopyState("Copied");
    window.setTimeout(() => setCopyState("Copy JSON"), 1600);
  }

  async function downloadJson() {
    if (!report) return;
    const exportPayload = await fetchExport(report.id);
    const blob = new Blob([JSON.stringify(exportPayload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `claim-readiness-report-${report.id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="min-h-screen bg-[#f5f7f8] text-[#18242b]">
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
          />

          <div className="space-y-5">
            <ResultSummary report={report} loading={loading} />
            <KeyFindings report={report} />
          </div>
        </div>

        <div className="mt-6 space-y-5">
          <CptCandidates report={report} />
          <AuditFindings report={report} />

          <Disclosure title="Show why this result?" open={showEvidence} onToggle={() => setShowEvidence((value) => !value)}>
            <EvidenceUsed report={report} />
          </Disclosure>

          <Disclosure title="Show technical JSON" open={showJson} onToggle={() => setShowJson((value) => !value)}>
            <FinalReport report={report} copyState={copyState} onCopy={copyJson} onDownload={downloadJson} />
          </Disclosure>

          <Disclosure title="Show recent analyses" open={showHistory} onToggle={() => setShowHistory((value) => !value)}>
            <RecentAnalyses history={history} loading={historyLoading} onLoad={loadAnalysis} />
          </Disclosure>
        </div>
      </section>
    </main>
  );
}

function ProductHeader() {
  return (
    <header className="border-b border-[#dbe3e7] bg-white">
      <div className="mx-auto max-w-7xl px-5 py-7">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
          <div>
            <p className="text-sm font-semibold text-[#44616d]">Healthcare revenue cycle demo</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-normal text-[#14232b]">AI Clinical Ops Agent</h1>
            <p className="mt-3 max-w-4xl text-base leading-7 text-[#4d626d]">
              Turn a synthetic operative note into CPT candidates, billing risk flags, reimbursement estimates, and a claim readiness report.
            </p>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#60757e]">
              Simulates how a billing operations team reviews operative notes before CPT submission.
            </p>
          </div>
          <div className="rounded-lg border border-[#f0c8a2] bg-[#fff8ef] p-4">
            <p className="text-sm font-semibold text-[#8a4b0f]">Demo only. Do not enter real patient information.</p>
            <p className="mt-2 text-sm leading-6 text-[#6d573f]">Use the included synthetic examples or paste synthetic text you created for testing.</p>
          </div>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-3">
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
    <div className="rounded-lg border border-[#dbe3e7] bg-[#fbfcfd] p-4">
      <h2 className="text-sm font-semibold text-[#14232b]">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-[#5d7079]">{text}</p>
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
    <section className="rounded-xl border border-[#dbe3e7] bg-white p-4">
      <div className="grid gap-3 md:grid-cols-3">
        {steps.map(([label, text]) => (
          <div key={label} className="flex gap-3 rounded-lg bg-[#f5f7f8] p-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#1f6f63] text-sm font-semibold text-white">
              {label.replace("Step ", "")}
            </span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#60757e]">{label}</p>
              <p className="mt-1 text-sm font-medium text-[#24353d]">{text}</p>
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
}: {
  selectedExample: string;
  noteText: string;
  loading: boolean;
  error: string | null;
  onSelectExample: (value: string) => void;
  onChangeNote: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <section className="rounded-xl border border-[#dbe3e7] bg-white p-5 shadow-sm">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-[#60757e]">Step 1</p>
        <h2 className="mt-1 text-xl font-semibold text-[#14232b]">Synthetic Operative Note</h2>
        <p className="mt-2 text-sm leading-6 text-[#5d7079]">
          Use an example note or paste your own synthetic note. The system will extract procedures, suggest CPT codes, check billing risks, and estimate reimbursement.
        </p>
      </div>

      <label className="mt-5 block text-sm font-semibold text-[#24353d]">Example note</label>
      <select
        value={selectedExample}
        onChange={(event) => onSelectExample(event.target.value)}
        className="mt-2 h-11 w-full rounded-lg border border-[#cbd7dd] bg-white px-3 text-sm outline-none focus:border-[#1f6f63] focus:ring-2 focus:ring-[#c8e1db]"
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
        className="mt-4 min-h-[390px] w-full resize-y rounded-lg border border-[#cbd7dd] bg-[#fbfcfd] p-4 font-mono text-sm leading-6 outline-none focus:border-[#1f6f63] focus:ring-2 focus:ring-[#c8e1db]"
      />
      <div className="mt-3 flex items-center justify-between gap-4 text-xs text-[#6b7e87]">
        <span>{noteText.length.toLocaleString()} / 20,000 characters</span>
        <span>No PHI</span>
      </div>

      <button
        type="button"
        onClick={onSubmit}
        disabled={loading}
        className="mt-5 w-full rounded-lg bg-[#1f6f63] px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-[#185b51] disabled:cursor-not-allowed disabled:bg-[#8fb5ad]"
      >
        {loading ? "Analyzing note..." : "Analyze Note for Billing"}
      </button>

      {error ? <div className="mt-4 rounded-lg border border-[#f0b5a8] bg-[#fff3f0] p-3 text-sm font-medium text-[#a83220]">{error}</div> : null}
    </section>
  );
}

function ResultSummary({ report, loading }: { report: AnalysisReport | null; loading: boolean }) {
  const topCode = report?.cpt_candidates[0];
  const reviewItems = (report?.audit_findings ?? []).filter((finding) => finding.severity !== "info");
  return (
    <section className="rounded-xl border border-[#dbe3e7] bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.1em] text-[#60757e]">Step 3</p>
          <h2 className="mt-1 text-xl font-semibold text-[#14232b]">Claim Readiness Report</h2>
          <p className="mt-2 text-sm leading-6 text-[#5d7079]">
            A score estimating how safe this note is to code and submit based on confidence, audit issues, and documentation completeness.
          </p>
        </div>
        <StatusBadge status={report?.report.claim_readiness_status ?? (loading ? "Running" : "Not run")} />
      </div>

      {report ? (
        <>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryMetric label="Claim Status" value={report.report.claim_readiness_status} />
            <SummaryMetric label="Primary CPT" value={topCode?.code ?? "None"} detail={topCode?.description} />
            <SummaryMetric label="Estimated Reimbursement" value={formatCurrency(report.total_estimated_reimbursement)} />
            <SummaryMetric label="Main Issue" value={report.report.main_issue ?? mainIssue(reviewItems)} />
          </div>
          <div className="mt-4 rounded-lg border border-[#cbd7dd] bg-[#f5f7f8] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#60757e]">Recommended action</p>
            <p className="mt-2 text-base font-semibold text-[#14232b]">{report.report.recommended_action ?? recommendedAction(report.report.claim_readiness_status)}</p>
          </div>
          <div className="mt-4 rounded-lg bg-[#fbfcfd] p-4">
            <p className="text-sm leading-6 text-[#4d626d]">{report.report.claim_readiness_explanation}</p>
            <ul className="mt-3 grid gap-2 text-sm text-[#24353d] sm:grid-cols-2">
              {(report.report.claim_readiness_reasons ?? fallbackReasons(report)).map((reason) => (
                <li key={reason} className="rounded-md bg-white px-3 py-2">
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
      <section className="rounded-xl border border-[#dbe3e7] bg-white p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[#14232b]">Key Findings</h2>
        <FriendlyEmpty title="No findings yet." text="Run an analysis to see procedures, suggested codes, risks, and reimbursement impact." />
      </section>
    );
  }

  const reviewItems = report.audit_findings.filter((finding) => finding.severity !== "info");
  const topCode = report.cpt_candidates[0];
  return (
    <section className="rounded-xl border border-[#dbe3e7] bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-[#14232b]">Key Findings</h2>
      <div className="mt-4 space-y-3">
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
              <tr className="border-b border-[#dbe3e7] text-xs uppercase tracking-[0.08em] text-[#60757e]">
                <th className="py-3 pr-4">CPT</th>
                <th className="py-3 pr-4">What it represents</th>
                <th className="py-3 pr-4">Confidence</th>
                <th className="py-3 pr-4">Modifier</th>
                <th className="py-3 pr-4">Support</th>
              </tr>
            </thead>
            <tbody>
              {report.cpt_candidates.map((candidate) => (
                <tr key={`${candidate.code}-${candidate.procedure_name}`} className="border-b border-[#edf1f3]">
                  <td className="py-3 pr-4 font-mono font-semibold text-[#14232b]">{candidate.code}</td>
                  <td className="py-3 pr-4">
                    <p className="font-medium text-[#24353d]">{candidate.procedure_name}</p>
                    <p className="mt-1 text-xs leading-5 text-[#60757e]">{candidate.description}</p>
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

function AuditFindings({ report }: { report: AnalysisReport | null }) {
  return (
    <SectionCard title="Audit Findings" explainer="Documentation or billing concerns that should be reviewed before submission.">
      {report ? (
        <div className="space-y-3">
          {report.audit_findings.map((finding, index) => (
            <div key={`${finding.category}-${index}`} className="rounded-lg border border-[#dbe3e7] bg-[#fbfcfd] p-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="font-semibold text-[#24353d]">{finding.title ?? findingTitle(finding.category)}</p>
                  <p className="mt-1 text-sm leading-6 text-[#5d7079]">{finding.explanation ?? finding.message}</p>
                </div>
                <StatusBadge status={finding.severity === "high" ? "High Risk" : finding.severity === "medium" ? "Needs Review" : "Ready"} />
              </div>
              <div className="mt-3 rounded-md bg-white px-3 py-2 text-sm">
                <span className="font-semibold text-[#24353d]">Recommended action: </span>
                <span className="text-[#4d626d]">{finding.suggested_action ?? finding.recommendation}</span>
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

function FinalReport({
  report,
  copyState,
  onCopy,
  onDownload,
}: {
  report: AnalysisReport | null;
  copyState: string;
  onCopy: () => void;
  onDownload: () => void;
}) {
  return (
    <SectionCard title="Final Report" explainer="A structured summary that could be reviewed by an operations or billing team.">
      {report ? (
        <>
          <div className="mb-3 flex flex-wrap gap-2">
            <button type="button" onClick={onCopy} className="rounded-lg border border-[#cbd7dd] px-3 py-2 text-sm font-semibold text-[#24353d] hover:bg-[#f5f7f8]">
              {copyState}
            </button>
            <button type="button" onClick={onDownload} className="rounded-lg bg-[#14232b] px-3 py-2 text-sm font-semibold text-white hover:bg-[#24353d]">
              Download JSON
            </button>
          </div>
          <pre className="max-h-[360px] overflow-auto rounded-lg bg-[#101820] p-4 text-xs leading-5 text-[#e6edf3]">{JSON.stringify(report.report, null, 2)}</pre>
        </>
      ) : (
        <FriendlyEmpty title="Technical report not generated yet." text="Run an analysis first, then expand this section to copy or download the JSON output." />
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
              className="rounded-lg border border-[#dbe3e7] bg-[#fbfcfd] p-4 text-left hover:border-[#1f6f63]"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-semibold text-[#24353d]">{item.title}</p>
                <span className="font-mono text-xs text-[#60757e]">{item.top_cpt_code ?? "No CPT"}</span>
              </div>
              <p className="mt-2 text-xs text-[#60757e]">{new Date(item.created_at).toLocaleString()}</p>
              <div className="mt-3 flex items-center justify-between gap-3 text-sm">
                <StatusBadge status={item.claim_readiness_status} />
                <span className="font-semibold">{formatCurrency(item.total_reimbursement)}</span>
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

function Disclosure({ title, open, onToggle, children }: { title: string; open: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-[#dbe3e7] bg-white shadow-sm">
      <button type="button" onClick={onToggle} className="flex w-full items-center justify-between px-5 py-4 text-left">
        <span className="text-base font-semibold text-[#14232b]">{title}</span>
        <span className="text-sm font-semibold text-[#1f6f63]">{open ? "Hide" : "Show"}</span>
      </button>
      {open ? <div className="border-t border-[#eef2f4] p-5">{children}</div> : null}
    </section>
  );
}

function SectionCard({ title, explainer, children }: { title: string; explainer: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-[#dbe3e7] bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-[#14232b]">{title}</h2>
      <p className="mt-1 text-sm leading-6 text-[#5d7079]">{explainer}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function SummaryMetric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-lg border border-[#dbe3e7] bg-[#fbfcfd] p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#60757e]">{label}</p>
      <p className="mt-2 text-lg font-semibold text-[#14232b]">{value}</p>
      {detail ? <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#60757e]">{detail}</p> : null}
    </div>
  );
}

function PlainFinding({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-[#f5f7f8] p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#60757e]">{label}</p>
      <p className="mt-2 text-sm leading-6 text-[#24353d]">{value}</p>
    </div>
  );
}

function FriendlyEmpty({ title, text }: { title: string; text: string }) {
  return (
    <div className="mt-4 rounded-lg border border-dashed border-[#cbd7dd] bg-[#fbfcfd] p-5">
      <p className="font-semibold text-[#24353d]">{title}</p>
      <p className="mt-2 text-sm leading-6 text-[#60757e]">{text}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const styles = normalized.includes("high")
    ? "border-[#f0b5a8] bg-[#fff3f0] text-[#a83220]"
    : normalized.includes("review") || normalized.includes("running")
      ? "border-[#edd29e] bg-[#fff8e8] text-[#8a5a12]"
      : normalized.includes("ready")
        ? "border-[#b8d8d0] bg-[#edf7f4] text-[#176153]"
        : "border-[#dbe3e7] bg-[#f5f7f8] text-[#60757e]";
  return <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${styles}`}>{status}</span>;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

function readableCategory(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function EvidenceGroup({ title, rows }: { title: string; rows: Array<{ heading: string; body: string; meta?: string }> }) {
  return (
    <div className="rounded-lg border border-[#dbe3e7] bg-[#fbfcfd] p-4">
      <h3 className="font-semibold text-[#14232b]">{title}</h3>
      <div className="mt-3 space-y-3">
        {rows.map((row, index) => (
          <div key={`${row.heading}-${index}`} className="rounded-md bg-white p-3">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-semibold text-[#24353d]">{row.heading}</p>
              {row.meta ? <span className="text-xs text-[#60757e]">{row.meta}</span> : null}
            </div>
            <p className="mt-2 text-sm leading-6 text-[#5d7079]">{row.body}</p>
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

function findingTitle(category: string) {
  if (category === "bundling_conflict") return "Bundling conflict detected";
  if (category === "low_confidence") return "Low confidence coding";
  if (category === "missing_laterality") return "Missing laterality";
  if (category === "unsupported_code") return "Unsupported procedure";
  if (category === "clean_claim") return "No major billing risks found";
  return readableCategory(category);
}
