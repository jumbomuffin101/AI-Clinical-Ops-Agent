"use client";

import { useEffect, useMemo, useState } from "react";

type EvidenceSnippet = {
  source: string;
  snippet: string;
  score?: number | null;
};

type ExtractedProcedure = {
  name: string;
  body_site?: string | null;
  approach?: string | null;
  laterality?: string | null;
  evidence: string;
  confidence: number;
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
  severity: string;
  category: string;
  message: string;
  related_code?: string | null;
  recommendation: string;
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
    claim_readiness: string;
    claim_readiness_score: number;
    claim_readiness_status: string;
    claim_readiness_explanation: string;
    audit_issue_count: number;
    procedure_count: number;
    total_estimated_reimbursement: number;
    coding_summary: Array<{
      procedure: string;
      code: string;
      modifiers: string[];
      confidence: number;
    }>;
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
    label: "AV fistula",
    risk: "Ready",
    title: "Left radiocephalic AV fistula creation",
    note: `Title: Left radiocephalic AV fistula creation

Indication: Synthetic patient with end-stage renal disease requiring durable hemodialysis access.

Procedure: Left upper extremity radiocephalic arteriovenous fistula creation.

Operative note: After sterile preparation, an incision was made at the left wrist. The cephalic vein and radial artery were dissected. The vein was divided distally, flushed, and an end-to-side anastomosis was created to the radial artery with running suture. A palpable thrill was present at completion. Hemostasis was achieved and the incision was closed.`,
  },
  {
    id: "lap-chole",
    label: "Lap chole",
    risk: "Ready",
    title: "Laparoscopic cholecystectomy",
    note: `Title: Laparoscopic cholecystectomy

Indication: Synthetic patient with symptomatic cholelithiasis.

Procedure: Laparoscopic cholecystectomy.

Operative note: Pneumoperitoneum was established and four ports were placed. The gallbladder was retracted, Calot's triangle was dissected, and the cystic duct and artery were clipped and divided. The gallbladder was removed from the liver bed using electrocautery and extracted in a specimen bag. No cholangiogram was performed.`,
  },
  {
    id: "femoral",
    label: "Femoral endarterectomy",
    risk: "Ready",
    title: "Right femoral endarterectomy",
    note: `Title: Right femoral endarterectomy

Indication: Synthetic patient with lifestyle-limiting claudication and high-grade common femoral artery stenosis.

Procedure: Right common femoral endarterectomy with patch angioplasty.

Operative note: A longitudinal incision was made in the right groin. The common femoral artery, profunda, and superficial femoral artery were controlled. Arteriotomy was performed and bulky plaque was removed from the common femoral artery. A bovine patch angioplasty was completed with running suture. Doppler signals were improved at completion.`,
  },
  {
    id: "carotid",
    label: "Carotid endarterectomy",
    risk: "Ready",
    title: "Left carotid endarterectomy",
    note: `Title: Left carotid endarterectomy

Indication: Synthetic patient with high-grade asymptomatic left internal carotid artery stenosis.

Procedure: Left carotid endarterectomy with patch angioplasty.

Operative note: A left neck incision was made along the anterior border of the sternocleidomastoid. The common, internal, and external carotid arteries were controlled. Arteriotomy was performed and plaque was removed from the carotid bifurcation. A patch angioplasty was completed and Doppler signals were satisfactory.`,
  },
  {
    id: "appendectomy",
    label: "Appendectomy",
    risk: "Ready",
    title: "Laparoscopic appendectomy",
    note: `Title: Laparoscopic appendectomy

Indication: Synthetic patient with acute uncomplicated appendicitis.

Procedure: Laparoscopic appendectomy.

Operative note: Three ports were placed. The appendix was inflamed but not perforated. The mesoappendix was divided, the appendix base was stapled, and the appendix was removed in a retrieval bag. Hemostasis was confirmed.`,
  },
  {
    id: "hernia-risk",
    label: "Hernia missing side",
    risk: "Needs Review",
    title: "Open inguinal hernia repair with missing laterality",
    note: `Title: Open inguinal hernia repair with missing laterality

Indication: Synthetic patient with symptomatic inguinal hernia.

Procedure: Open inguinal hernia repair with mesh.

Operative note: An oblique groin incision was made. The hernia sac was dissected from the cord structures and reduced. A mesh repair was completed and secured to the inguinal ligament and conjoint tendon. The note does not clearly document left or right laterality.`,
  },
  {
    id: "colonoscopy",
    label: "Colonoscopy",
    risk: "Ready",
    title: "Diagnostic colonoscopy",
    note: `Title: Diagnostic colonoscopy

Indication: Synthetic patient with positive screening test.

Procedure: Diagnostic colonoscopy.

Operative note: The colonoscope was advanced to the cecum with identification of the appendiceal orifice and ileocecal valve. The mucosa was inspected on withdrawal. No biopsy, polypectomy, or other therapeutic intervention was performed.`,
  },
  {
    id: "angiogram-risk",
    label: "Angiogram incomplete",
    risk: "High Risk",
    title: "Lower extremity angiogram with incomplete documentation",
    note: `Title: Lower extremity angiogram with incomplete documentation

Indication: Synthetic patient with peripheral arterial disease.

Procedure: Lower extremity angiogram.

Operative note: Percutaneous access was obtained and a catheter was advanced for lower extremity angiogram. Images were obtained, but the dictated note does not clearly document left or right laterality, selected vascular territory, or whether additional interventions were performed.`,
  },
  {
    id: "bundled-risk",
    label: "Bundled chole risk",
    risk: "High Risk",
    title: "Ambiguous laparoscopic cholecystectomy with cholangiogram",
    note: `Title: Ambiguous laparoscopic cholecystectomy with cholangiogram

Indication: Synthetic patient with symptomatic gallstones.

Procedure: Laparoscopic cholecystectomy, possible cholangiogram.

Operative note: Four ports were placed and the gallbladder was dissected from the liver bed. The cystic duct and artery were clipped and divided. The note states that a cholangiogram may have been performed but does not clearly document images, catheter placement, or interpretation. This creates ambiguity between cholecystectomy code choices.`,
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
  }

  async function loadHistory() {
    setHistoryLoading(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/analyses`);
      if (response.ok) {
        setHistory(await response.json());
      }
    } finally {
      setHistoryLoading(false);
    }
  }

  async function loadAnalysis(id: string) {
    setError(null);
    const response = await fetch(`${apiBaseUrl}/api/analyses/${id}`);
    const payload = await response.json();
    if (!response.ok) {
      setError(payload?.error?.message ?? "Unable to load analysis.");
      return;
    }
    setReport(payload);
    setCopyState("Copy JSON");
  }

  async function submitNote() {
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
      if (!response.ok) {
        throw new Error(payload?.error?.message ?? `API request failed with ${response.status}`);
      }
      setReport(payload);
      await loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
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
    anchor.download = `analysis-${report.id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function fetchExport(id: string) {
    const response = await fetch(`${apiBaseUrl}/api/analyses/${id}/export`);
    if (!response.ok) return report;
    return response.json();
  }

  return (
    <main className="min-h-screen bg-[#f3f5f7] text-[#172026]">
      <header className="border-b border-[#d8dee4] bg-white">
        <div className="mx-auto flex max-w-[1500px] flex-col gap-3 px-6 py-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#55707c]">Synthetic data only</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-normal">AI Clinical Ops Agent</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#5f6f78]">
              Surgical coding automation with RAG-backed evidence, billing audit checks, reimbursement estimates, and claim readiness scoring.
            </p>
          </div>
          <div className="rounded-md border border-[#d8dee4] bg-[#fbfcfd] px-3 py-2 text-xs text-[#5f6f78]">
            API <span className="font-mono text-[#172026]">{apiBaseUrl}</span>
          </div>
        </div>
      </header>

      <section className="mx-auto grid max-w-[1500px] gap-6 px-6 py-6 xl:grid-cols-[380px_minmax(0,1fr)_330px]">
        <InputPanel
          noteText={noteText}
          selectedExample={selectedExample}
          loading={loading}
          error={error}
          onChangeNote={setNoteText}
          onSelectExample={chooseExample}
          onSubmit={submitNote}
        />

        <div className="space-y-6">
          <ClaimReadinessCard report={report} loading={loading} />
          <ProceduresCard procedures={report?.extracted_procedures ?? []} />
          <CptTable candidates={report?.cpt_candidates ?? []} />
          <AuditTable findings={report?.audit_findings ?? []} />
          <EvidenceCard candidates={report?.cpt_candidates ?? []} findings={report?.audit_findings ?? []} />
          <FinalReportCard report={report} copyState={copyState} onCopy={copyJson} onDownload={downloadJson} />
        </div>

        <RecentAnalysesPanel history={history} loading={historyLoading} onLoad={loadAnalysis} />
      </section>
    </main>
  );
}

function InputPanel({
  noteText,
  selectedExample,
  loading,
  error,
  onChangeNote,
  onSelectExample,
  onSubmit,
}: {
  noteText: string;
  selectedExample: string;
  loading: boolean;
  error: string | null;
  onChangeNote: (value: string) => void;
  onSelectExample: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <section className="rounded-lg border border-[#d8dee4] bg-white p-5 xl:sticky xl:top-6 xl:self-start">
      <div>
        <h2 className="text-lg font-semibold">Operative Note</h2>
        <p className="mt-1 text-sm text-[#8a4b0f]">No PHI. Use synthetic notes only.</p>
      </div>
      <label className="mt-5 block text-xs font-semibold uppercase tracking-[0.1em] text-[#6c7b83]">Example case</label>
      <select
        value={selectedExample}
        onChange={(event) => onSelectExample(event.target.value)}
        className="mt-2 h-10 w-full rounded-md border border-[#c8d1d8] bg-white px-3 text-sm font-medium outline-none focus:border-[#1f7a68] focus:ring-2 focus:ring-[#b9ded5]"
      >
        {examples.map((example) => (
          <option key={example.id} value={example.id}>
            {example.label} - {example.risk}
          </option>
        ))}
      </select>
      <textarea
        value={noteText}
        onChange={(event) => onChangeNote(event.target.value)}
        maxLength={20000}
        className="mt-4 min-h-[470px] w-full resize-y rounded-md border border-[#c8d1d8] bg-[#fbfcfd] p-4 font-mono text-sm leading-6 outline-none focus:border-[#1f7a68] focus:ring-2 focus:ring-[#b9ded5]"
      />
      <div className="mt-3 flex items-center justify-between gap-4 text-xs text-[#5f6f78]">
        <span>{noteText.length.toLocaleString()} / 20,000</span>
        <span>Mock AI + local RAG</span>
      </div>
      <button
        type="button"
        onClick={onSubmit}
        disabled={loading || noteText.trim().length < 50}
        className="mt-4 w-full rounded-md bg-[#1f7a68] px-4 py-3 text-sm font-semibold text-white hover:bg-[#176153] disabled:cursor-not-allowed disabled:bg-[#8aa9a2]"
      >
        {loading ? "Analyzing..." : "Run analysis"}
      </button>
      {error ? <div className="mt-4 rounded-md border border-[#f3b6ad] bg-[#fff4f2] p-3 text-sm font-medium text-[#b42318]">{error}</div> : null}
    </section>
  );
}

function ClaimReadinessCard({ report, loading }: { report: AnalysisReport | null; loading: boolean }) {
  const score = report?.report.claim_readiness_score ?? 0;
  const status = report?.report.claim_readiness_status ?? (loading ? "Scoring" : "Waiting");
  const scoreColor = score >= 85 ? "#1f7a68" : score >= 60 ? "#9a5b13" : "#b42318";
  return (
    <section className="rounded-lg border border-[#d8dee4] bg-white p-5">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#6c7b83]">Claim readiness</p>
          <h2 className="mt-2 text-2xl font-semibold">{status}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[#5f6f78]">
            {report?.report.claim_readiness_explanation ?? "Submit a synthetic note to calculate score, audit risk, and reimbursement readiness."}
          </p>
        </div>
        <div className="flex h-28 w-28 shrink-0 items-center justify-center rounded-full border-[10px] bg-[#fbfcfd]" style={{ borderColor: scoreColor }}>
          <span className="text-3xl font-semibold">{report ? score : "--"}</span>
        </div>
      </div>
      <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Metric label="Procedures" value={report?.extracted_procedures.length ?? 0} />
        <Metric label="CPT codes" value={report?.cpt_candidates.length ?? 0} />
        <Metric label="Audit issues" value={report?.report.audit_issue_count ?? 0} />
        <Metric label="Estimated" value={formatCurrency(report?.total_estimated_reimbursement ?? 0)} />
      </div>
    </section>
  );
}

function ProceduresCard({ procedures }: { procedures: ExtractedProcedure[] }) {
  return (
    <Card title="Procedures">
      {procedures.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {procedures.map((procedure) => (
            <div key={procedure.name} className="rounded-md border border-[#d8dee4] p-4">
              <div className="flex items-start justify-between gap-3">
                <h3 className="font-semibold">{procedure.name}</h3>
                <span className="text-sm font-semibold text-[#1f7a68]">{Math.round(procedure.confidence * 100)}%</span>
              </div>
              <p className="mt-2 text-sm text-[#5f6f78]">{procedure.evidence}</p>
              <p className="mt-3 text-xs uppercase tracking-[0.1em] text-[#6c7b83]">
                {[procedure.approach, procedure.body_site, procedure.laterality].filter(Boolean).join(" / ") || "No attributes"}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState />
      )}
    </Card>
  );
}

function CptTable({ candidates }: { candidates: CPTCodeCandidate[] }) {
  return (
    <Card title="CPT Candidate Table">
      {candidates.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-[#d8dee4] text-xs uppercase tracking-[0.1em] text-[#6c7b83]">
                <th className="py-3 pr-4">Code</th>
                <th className="py-3 pr-4">Procedure</th>
                <th className="py-3 pr-4">Modifiers</th>
                <th className="py-3 pr-4">Confidence</th>
                <th className="py-3 pr-4">Docs</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((candidate) => (
                <tr key={`${candidate.code}-${candidate.procedure_name}`} className="border-b border-[#edf0f2]">
                  <td className="py-3 pr-4 font-mono font-semibold">{candidate.code}</td>
                  <td className="py-3 pr-4">
                    <p className="font-medium">{candidate.procedure_name}</p>
                    <p className="mt-1 text-xs text-[#5f6f78]">{candidate.description}</p>
                  </td>
                  <td className="py-3 pr-4">{candidate.modifiers.length ? candidate.modifiers.join(", ") : "-"}</td>
                  <td className="py-3 pr-4">{Math.round(candidate.confidence * 100)}%</td>
                  <td className="py-3 pr-4">{candidate.supported_by_docs ? "Supported" : "Unsupported"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState />
      )}
    </Card>
  );
}

function AuditTable({ findings }: { findings: AuditFinding[] }) {
  return (
    <Card title="Audit Findings">
      {findings.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-[#d8dee4] text-xs uppercase tracking-[0.1em] text-[#6c7b83]">
                <th className="py-3 pr-4">Severity</th>
                <th className="py-3 pr-4">Category</th>
                <th className="py-3 pr-4">Related code</th>
                <th className="py-3 pr-4">Recommendation</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((finding, index) => (
                <tr key={`${finding.category}-${index}`} className="border-b border-[#edf0f2]">
                  <td className="py-3 pr-4">
                    <span className={severityClass(finding.severity)}>{finding.severity}</span>
                  </td>
                  <td className="py-3 pr-4">
                    <p className="font-medium capitalize">{finding.category.replaceAll("_", " ")}</p>
                    <p className="mt-1 text-xs text-[#5f6f78]">{finding.message}</p>
                  </td>
                  <td className="py-3 pr-4 font-mono">{finding.related_code ?? "-"}</td>
                  <td className="py-3 pr-4">{finding.recommendation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState />
      )}
    </Card>
  );
}

function EvidenceCard({ candidates, findings }: { candidates: CPTCodeCandidate[]; findings: AuditFinding[] }) {
  const evidenceRows = [
    ...candidates.flatMap((candidate) =>
      candidate.evidence_used.map((evidence) => ({
        label: `CPT ${candidate.code}`,
        rationale: candidate.rationale,
        ...evidence,
      })),
    ),
    ...findings.flatMap((finding) =>
      finding.evidence_used.map((evidence) => ({
        label: finding.category.replaceAll("_", " "),
        rationale: finding.message,
        ...evidence,
      })),
    ),
  ];

  return (
    <Card title="Evidence Used">
      {evidenceRows.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {evidenceRows.map((row, index) => (
            <div key={`${row.source}-${index}`} className="rounded-md border border-[#d8dee4] bg-[#fbfcfd] p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold capitalize">{row.label}</p>
                <span className="font-mono text-xs text-[#5f6f78]">{row.source}</span>
              </div>
              <p className="mt-2 text-xs leading-5 text-[#5f6f78]">{row.snippet}</p>
              <p className="mt-3 text-xs font-medium text-[#304852]">{row.rationale}</p>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState />
      )}
    </Card>
  );
}

function FinalReportCard({
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
    <Card
      title="Final Report"
      action={
        <div className="flex gap-2">
          <button type="button" onClick={onCopy} disabled={!report} className="rounded-md border border-[#c8d1d8] px-3 py-2 text-sm font-semibold hover:bg-[#eef2f4] disabled:cursor-not-allowed disabled:text-[#8d9aa1]">
            {copyState}
          </button>
          <button type="button" onClick={onDownload} disabled={!report} className="rounded-md bg-[#172026] px-3 py-2 text-sm font-semibold text-white hover:bg-[#304852] disabled:cursor-not-allowed disabled:bg-[#8d9aa1]">
            Download JSON
          </button>
        </div>
      }
    >
      {report ? (
        <pre className="max-h-[340px] overflow-auto rounded-md bg-[#101820] p-4 text-xs leading-5 text-[#e6edf3]">{JSON.stringify(report.report, null, 2)}</pre>
      ) : (
        <EmptyState />
      )}
    </Card>
  );
}

function RecentAnalysesPanel({
  history,
  loading,
  onLoad,
}: {
  history: AnalysisHistoryItem[];
  loading: boolean;
  onLoad: (id: string) => void;
}) {
  return (
    <aside className="rounded-lg border border-[#d8dee4] bg-white p-5 xl:sticky xl:top-6 xl:self-start">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Recent Analyses</h2>
        <span className="text-xs text-[#5f6f78]">{loading ? "Loading" : `${history.length} shown`}</span>
      </div>
      <div className="mt-4 space-y-3">
        {history.length ? (
          history.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onLoad(item.id)}
              className="w-full rounded-md border border-[#d8dee4] bg-[#fbfcfd] p-3 text-left hover:border-[#1f7a68]"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-semibold">{item.title}</p>
                <span className="font-mono text-xs">{item.top_cpt_code ?? "-"}</span>
              </div>
              <p className="mt-2 text-xs text-[#5f6f78]">{new Date(item.created_at).toLocaleString()}</p>
              <div className="mt-3 flex items-center justify-between gap-3 text-xs">
                <span className="font-semibold">{item.claim_readiness_status}</span>
                <span>{formatCurrency(item.total_reimbursement)}</span>
              </div>
            </button>
          ))
        ) : (
          <EmptyState />
        )}
      </div>
    </aside>
  );
}

function Card({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-[#d8dee4] bg-white p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <h2 className="text-lg font-semibold">{title}</h2>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-[#d8dee4] bg-[#fbfcfd] p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.1em] text-[#6c7b83]">{label}</p>
      <p className="mt-2 text-lg font-semibold capitalize">{value}</p>
    </div>
  );
}

function EmptyState() {
  return <div className="rounded-md border border-dashed border-[#c8d1d8] p-4 text-sm text-[#5f6f78]">Run an analysis to populate this section.</div>;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

function severityClass(severity: string) {
  const base = "rounded px-2 py-1 text-xs font-semibold uppercase";
  if (severity === "high") return `${base} bg-[#fff0ed] text-[#b42318]`;
  if (severity === "medium") return `${base} bg-[#fff7e8] text-[#9a5b13]`;
  if (severity === "low") return `${base} bg-[#eef2f4] text-[#304852]`;
  return `${base} bg-[#e8f3f0] text-[#176153]`;
}
