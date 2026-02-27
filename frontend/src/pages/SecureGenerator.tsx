// Securegenerator.tsx
import { useState } from "react";
import UmlViewerModal, { type DiagramType, type AiUmlStore } from "../components/UmlViewerModal.tsx";
import { FileSearch, CheckCircle2, MinusCircle, Workflow } from "lucide-react";

/* ---------- Types ---------- */
type Finding = {
  check_id?: string;
  severity?: string;
  message?: string;
  path?: string;
  start?: { line?: number };
  has_autofix?: boolean;
};

type SemgrepReport = {
  ok?: boolean;
  initial_findings?: number;
  final_findings?: number;
  autofix_applied?: boolean;
  fixes_applied?: number;
  auto_fixable_count?: number;
  manual_only_count?: number;
  packs?: string[];
  languages?: string[];
  file_count?: number;
  categorized_findings?: {
    initially_auto_fixable?: Finding[];
    initially_manual_only?: Finding[];
    still_remaining?: Finding[];
    remaining_needs_llm?: Finding[];
  };
};

type LlmFixReport = {
  fixed?: boolean;
  attempted?: boolean;
  issues_before?: number;
  issues_after?: number;
  fixes_applied?: number;
  error?: string;
  reason?: string;
};

/* ---------- UML Types (her additions) ---------- */
type UmlValidationEntry = {
  ok: boolean;
  errors: string[];
};

type UmlValidationMap = Partial<
  Record<"class" | "package" | "sequence" | "component" | "activity", UmlValidationEntry>
>;

type UmlReport = {
  ok?: boolean;
  file_count?: number;
  error?: string | null;
  cir?: unknown;
  class_svg?: string | null;
  package_svg?: string | null;
  sequence_svg?: string | null;
  component_svg?: string | null;
  activity_svg?: string | null;
  validation?: UmlValidationMap;
};

type Report = {
  policy_version?: string;
  prompt_after_enhancement?: string;
  semgrep?: SemgrepReport;
  llm_fix?: LlmFixReport;
  uml?: UmlReport;
  total_fixes_applied?: number;
  fix_summary?: {
    initial_issues?: number;
    semgrep_fixed?: number;
    llm_fixed?: number;
    remaining_issues?: number;
    fix_rate_percent?: number;
  };
};

type ApiResult = {
  code: string;
  original_code?: string;
  report: Report;
  decision?: string;
};

/* ---------- API endpoints ---------- */
const API = "http://localhost:8000/api/generate";
const UML_AI_API = "http://localhost:7081/uml/ai";

/* ---------- Styled Components ---------- */
const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div style={{ marginTop: 24 }}>
    <h2 style={{ margin: "0 0 12px 0", fontSize: 18, fontWeight: 600, color: "#1e293b" }}>
      {title}
    </h2>
    <div
      style={{
        background: "#ffffff",
        padding: 20,
        borderRadius: 8,
        border: "1px solid #e2e8f0",
        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
      }}
    >
      {children}
    </div>
  </div>
);

const StatCard = ({ label, value, color }: { label: string; value: number; color: string }) => (
  <div
    style={{
      padding: 16,
      background: "#f8fafc",
      borderRadius: 8,
      border: "1px solid #e2e8f0",
    }}
  >
    <div style={{ fontSize: 12, color: "#64748b", marginBottom: 4 }}>{label}</div>
    <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
  </div>
);

const ProgressBar = ({ current, total }: { current: number; total: number }) => {
  const percentage = total > 0 ? (current / total) * 100 : 0;
  const color = percentage >= 80 ? "#10b981" : percentage >= 50 ? "#f59e0b" : "#ef4444";

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 12 }}>
        <span style={{ color: "#64748b" }}>
          Fixed: {current} / {total}
        </span>
        <span style={{ color, fontWeight: 600 }}>{percentage.toFixed(0)}%</span>
      </div>
      <div
        style={{
          width: "100%",
          height: 8,
          background: "#e2e8f0",
          borderRadius: 4,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${percentage}%`,
            height: "100%",
            background: color,
            transition: "width 0.3s ease",
          }}
        />
      </div>
    </div>
  );
};

/* ---------- Main Component ---------- */
export default function Securegenerator() {
  const [prompt, setPrompt] = useState("");
  const [out, setOut] = useState<ApiResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);

  // UML modal state (her additions)
  const [umlOpen, setUmlOpen] = useState(false);
  const [umlTab, setUmlTab] = useState<DiagramType>("class");
  const [aiUmlCache, setAiUmlCache] = useState<AiUmlStore>({});

  const onGenerate = async () => {
    setLoading(true);
    setOut(null);
    setCopied(false);
    setUmlOpen(false);
    setShowOriginal(false);
    setAiUmlCache({});

    try {
      const res = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      const data = (await res.json()) as ApiResult;
      setOut(data);
    } catch (e) {
      console.error(e);
      alert("Request failed — is the backend running on :8000?");
    } finally {
      setLoading(false);
    }
  };

  const copyCode = async () => {
    if (!out?.code) return;
    await navigator.clipboard.writeText(out.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const fixSummary = out?.report?.fix_summary;
  const semgrep = out?.report?.semgrep;
  const llmFix = out?.report?.llm_fix;
  const uml = out?.report?.uml;

  return (
    <div
      style={{
        width: "100vw",
        minHeight: "100vh",
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        padding: "40px 20px",
        overflowX: "hidden",
      }}
    >
      <main
        style={{
          width: "100%",
          maxWidth: "100%",
          margin: "0 auto",
          fontFamily: "system-ui, -apple-system, sans-serif",
        }}
      >
        {/* Header */}
        <div
          style={{
            background: "white",
            padding: 32,
            borderRadius: 12,
            boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
            marginBottom: 24,
          }}
        >
          <h1 style={{ margin: "0 0 8px 0", fontSize: 28, fontWeight: 700, color: "#1e293b" }}>
            🔒 Secure-by-Design Code Generator
          </h1>
          <p style={{ margin: 0, color: "#64748b", fontSize: 14 }}>
            Hybrid Autofix: Semgrep Native + LLM Intelligence • OWASP Protected • Multi-Language
          </p>
        </div>

        {/* Input Card */}
        <div
          style={{
            background: "white",
            padding: 24,
            borderRadius: 12,
            boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
            marginBottom: 24,
          }}
        >
          <label
            style={{
              display: "block",
              marginBottom: 12,
              fontSize: 14,
              fontWeight: 600,
              color: "#334155",
            }}
          >
            Describe the code you want to generate
          </label>
          <textarea
            rows={5}
            style={{
              width: "100%",
              padding: 16,
              borderRadius: 8,
              border: "2px solid #e2e8f0",
              fontSize: 14,
              fontFamily: "inherit",
              resize: "vertical",
              outline: "none",
              boxSizing: "border-box",
            }}
            placeholder="e.g., Build a user authentication API with JWT in Java, or Create a Python Flask app with SQL database"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onFocus={(e) => (e.target.style.borderColor = "#3b82f6")}
            onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")}
          />

          <div style={{ marginTop: 16, display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button
              onClick={onGenerate}
              disabled={loading || !prompt.trim()}
              style={{
                flex: "1 1 220px",
                padding: "14px 24px",
                borderRadius: 8,
                border: "none",
                background: loading || !prompt.trim() ? "#cbd5e1" : "#3b82f6",
                color: "white",
                fontSize: 15,
                fontWeight: 600,
                cursor: loading || !prompt.trim() ? "not-allowed" : "pointer",
              }}
            >
              {loading ? "🔄 Generating..." : "✨ Generate Secure Code"}
            </button>

            {out?.code && (
              <button
                onClick={copyCode}
                style={{
                  padding: "14px 24px",
                  borderRadius: 8,
                  border: "2px solid #3b82f6",
                  background: copied ? "#3b82f6" : "white",
                  color: copied ? "white" : "#3b82f6",
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {copied ? "✓ Copied!" : "📋 Copy Code"}
              </button>
            )}
          </div>
        </div>

        {out && (
          <div
            style={{
              background: "white",
              padding: 24,
              borderRadius: 12,
              boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
            }}
          >
            {/* Auto-Fix Results */}
            {fixSummary && fixSummary.initial_issues! > 0 && (
              <Section title="🔧 Auto-Fix Results">
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                    gap: 12,
                    marginBottom: 16,
                  }}
                >
                  <StatCard label="Initial Issues" value={fixSummary.initial_issues!} color="#ef4444" />
                  <StatCard label="Semgrep Fixed" value={fixSummary.semgrep_fixed!} color="#10b981" />
                  {fixSummary.llm_fixed! > 0 && (
                    <StatCard label="LLM Fixed" value={fixSummary.llm_fixed!} color="#3b82f6" />
                  )}
                  <StatCard
                    label="Remaining"
                    value={fixSummary.remaining_issues!}
                    color={fixSummary.remaining_issues === 0 ? "#10b981" : "#f59e0b"}
                  />
                </div>

                <ProgressBar
                  current={fixSummary.semgrep_fixed! + fixSummary.llm_fixed!}
                  total={fixSummary.initial_issues!}
                />

                <div
                  style={{
                    marginTop: 16,
                    padding: 12,
                    background: "#f8fafc",
                    borderRadius: 6,
                    fontSize: 13,
                  }}
                >
                  <div style={{ marginBottom: 4, color: "#475569" }}>
                    ✅ <strong>Auto-fixable (Semgrep):</strong> {semgrep?.auto_fixable_count || 0} rules
                  </div>
                  <div style={{ color: "#475569" }}>
                    🔧 <strong>Required LLM:</strong> {semgrep?.manual_only_count || 0} rules
                  </div>
                </div>

                {fixSummary.remaining_issues === 0 && fixSummary.initial_issues! > 0 && (
                  <div
                    style={{
                      marginTop: 16,
                      padding: 16,
                      background: "linear-gradient(135deg, #dcfce7 0%, #86efac 100%)",
                      borderRadius: 8,
                      textAlign: "center",
                      fontSize: 15,
                      fontWeight: 600,
                      color: "#166534",
                    }}
                  >
                    🎉 All {fixSummary.initial_issues} vulnerabilities automatically fixed!
                  </div>
                )}

                {llmFix?.attempted && (
                  <div
                    style={{
                      marginTop: 12,
                      padding: 12,
                      background: llmFix.fixed ? "#eff6ff" : "#fef2f2",
                      borderRadius: 6,
                      fontSize: 13,
                    }}
                  >
                    <div
                      style={{
                        fontWeight: 600,
                        color: llmFix.fixed ? "#1e40af" : "#991b1b",
                        marginBottom: 4,
                      }}
                    >
                      {llmFix.fixed ? "🤖 LLM Fix Applied" : "⚠️ LLM Fix Status"}
                    </div>
                    <div style={{ color: llmFix.fixed ? "#1e40af" : "#991b1b" }}>
                      {llmFix.fixed
                        ? `Fixed ${llmFix.fixes_applied} complex issues`
                        : llmFix.error || llmFix.reason || "Not successful"}
                    </div>
                  </div>
                )}
              </Section>
            )}

            {/* Generated Code */}
            <Section title="📝 Generated Code">
              {out.original_code && out.original_code !== out.code && (
                <div style={{ marginBottom: 12 }}>
                  <button
                    onClick={() => setShowOriginal(!showOriginal)}
                    style={{
                      padding: "8px 16px",
                      borderRadius: 6,
                      border: "1px solid #e2e8f0",
                      background: showOriginal ? "#3b82f6" : "white",
                      color: showOriginal ? "white" : "#3b82f6",
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    {showOriginal ? "Show Fixed Code" : "Show Original Code"}
                  </button>
                </div>
              )}
              <pre
                style={{
                  whiteSpace: "pre-wrap",
                  margin: 0,
                  fontSize: 13,
                  lineHeight: 1.6,
                  background: "#0f172a",
                  color: "#e2e8f0",
                  padding: 20,
                  borderRadius: 6,
                  overflow: "auto",
                  maxHeight: 600,
                }}
              >
                {showOriginal ? out.original_code : out.code}
              </pre>
            </Section>

            {/* UML Diagrams — her upgrades: lucide icons, UmlViewerModal, 4 diagram types, AI cache */}
            <Section title="📊 UML Diagrams (Rule-based, AI-based)">
              {!uml || uml.error ? (
                <div
                  style={{
                    padding: 12,
                    background: "#fef2f2",
                    borderRadius: 6,
                    color: "#991b1b",
                    fontSize: 13,
                  }}
                >
                  {uml?.error
                    ? `UML generation: ${uml.error}`
                    : "No UML diagrams available for this generation (e.g. non-Java code)."}
                </div>
              ) : (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 16,
                    flexWrap: "wrap",
                  }}
                >
                  <div style={{ fontSize: 13, color: "#64748b" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <FileSearch size={16} />
                      <span>Files analysed for UML: {uml.file_count ?? 0}</span>
                    </div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 12,
                        flexWrap: "wrap",
                        marginTop: 8,
                      }}
                    >
                      {(
                        [
                          { key: "class_svg" as const, label: "Class diagram" },
                          { key: "package_svg" as const, label: "Package diagram" },
                          { key: "sequence_svg" as const, label: "Sequence diagram" },
                          { key: "component_svg" as const, label: "Component diagram" },
                          { key: "activity_svg" as const, label: "Activity diagram" },
                        ]
                      ).map(({ key, label }, idx, arr) => (
                        <span key={key} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                          {label}:{" "}
                          {uml[key] ? (
                            <CheckCircle2 size={16} color="#16a34a" />
                          ) : (
                            <MinusCircle size={16} color="#94a3b8" />
                          )}
                          {uml[key] ? "available" : "—"}
                          {idx < arr.length - 1 && (
                            <span style={{ opacity: 0.4, marginLeft: 6 }}>•</span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      if (!uml) return;
                      const defaultTab: DiagramType = uml.class_svg
                        ? "class"
                        : uml.package_svg
                        ? "package"
                        : uml.sequence_svg
                        ? "sequence"
                        : uml.component_svg
                        ? "component"
                        : "activity";
                      setUmlTab(defaultTab);
                      setUmlOpen(true);
                    }}
                    style={{
                      padding: "10px 18px",
                      borderRadius: 8,
                      border: "none",
                      background: "#0ea5e9",
                      color: "white",
                      fontSize: 14,
                      fontWeight: 600,
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <Workflow size={16} />
                    Open UML Viewer
                  </button>
                </div>
              )}
            </Section>

            {/* Security Report */}
            <Section title="📋 Security Report">
              <div style={{ marginBottom: 12, fontSize: 12, color: "#64748b" }}>
                Policy: {out.report.policy_version ?? "N/A"}
              </div>
              <details>
                <summary
                  style={{
                    fontWeight: 600,
                    padding: "8px 0",
                    color: "#3b82f6",
                    cursor: "pointer",
                  }}
                >
                  View Enhanced Prompt
                </summary>
                <pre
                  style={{
                    whiteSpace: "pre-wrap",
                    margin: "12px 0 0 0",
                    fontSize: 11,
                    background: "#f8fafc",
                    padding: 16,
                    borderRadius: 6,
                    maxHeight: 400,
                    overflow: "auto",
                    color: "#334155",
                  }}
                >
                  {out.report.prompt_after_enhancement}
                </pre>
              </details>
            </Section>
          </div>
        )}

        {/* Footer */}
        <div
          style={{
            marginTop: 40,
            padding: 20,
            textAlign: "center",
            color: "rgba(255,255,255,0.92)",
            fontSize: 13,
          }}
        >
          Hybrid Autofix: Semgrep Native (~35%) + LLM Intelligence (~65%) • OWASP Protected • Multi-Language
        </div>
      </main>

      {/* UML Modal (her addition) */}
      {uml && !uml.error && (
        <UmlViewerModal
          open={umlOpen}
          uml={uml}
          tab={umlTab}
          setTab={setUmlTab}
          onClose={() => setUmlOpen(false)}
          code={out?.code ?? null}
          cir={uml?.cir ?? null}
          umlAiApi={UML_AI_API}
          aiStore={aiUmlCache}
          setAiStore={setAiUmlCache}
        />
      )}
    </div>
  );
}