// Securegenerator.tsx 
import { useState } from "react";
import UmlViewerModal, { type DiagramType, type AiUmlStore } from "../components/UmlViewerModal.tsx";
import { 
  CheckCircle2, MinusCircle, Workflow, Shield, Sparkles, 
  Copy, Check, Code2, ChevronDown, Zap, BarChart3, Clock, Settings, ArrowLeft 
} from "lucide-react";

/* ---------- Types (unchanged) ---------- */
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

/* ---------- Main Component ---------- */
export default function Securegenerator() {
  const [prompt, setPrompt] = useState("");
  const [out, setOut] = useState<ApiResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const [securityReportOpen, setSecurityReportOpen] = useState(false);

  // UML modal state
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
    setSecurityReportOpen(false);

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
  const uml = out?.report?.uml;

  return (
    <div
      style={{
        display: "flex",
        width: "100vw",
        height: "100vh",
        background: "#0f172a",
        overflow: "hidden",
      }}
    >
      {/* Sidebar */}
      <div
        style={{
          width: 60,
          background: "#1e1b2e",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          padding: "20px 0",
          gap: 20,
          borderRight: "1px solid #2d2a3d",
        }}
      >
        {/* Back Button */}
<button
  onClick={() => window.history.back()}
  style={{
    width: 40,
    height: 40,
    background: "none",
    border: "none",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    padding: 0,
  }}
>
  <ArrowLeft size={22} color="#e2e8f0" strokeWidth={2.5} />
</button>

        {/* Logo */}
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 12,
            background: "linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Zap size={24} color="#fff" />
        </div>

        {/* Nav Icons */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 16,
            marginTop: 20,
          }}
        >
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 10,
              background: "#8b5cf6",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <Shield size={20} color="#fff" />
          </div>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 10,
              background: "transparent",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              opacity: 0.5,
            }}
          >
            <Clock size={20} color="#94a3b8" />
          </div>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 10,
              background: "transparent",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              opacity: 0.5,
            }}
          >
            <BarChart3 size={20} color="#94a3b8" />
          </div>
        </div>

        {/* Settings at bottom */}
        <div style={{ marginTop: "auto" }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 10,
              background: "transparent",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              opacity: 0.5,
            }}
          >
            <Settings size={20} color="#94a3b8" />
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Top Header */}
        <div
          style={{
            padding: "20px 32px",
            borderBottom: "1px solid #1e293b",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: "#e2e8f0" }}>
            Secure Code Generator
          </h1>
          <div style={{ fontSize: 13, color: "#64748b" }}>•••</div>
        </div>

        {/* Scrollable Content */}
        <div
          style={{
            flex: 1,
            overflow: "auto",
            padding: "32px",
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: out ? "500px 1fr" : "1fr",
              gap: 24,
              maxWidth: 1600,
            }}
          >
            {/* Left Column - Input */}
            <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
              {/* Input Card */}
              <div
                style={{
                  background: "#1a1f2e",
                  borderRadius: 16,
                  padding: 24,
                  border: "1px solid #2d3548",
                }}
              >
                <label
                  style={{
                    display: "block",
                    marginBottom: 12,
                    fontSize: 11,
                    fontWeight: 600,
                    color: "#64748b",
                    textTransform: "uppercase",
                    letterSpacing: "0.1em",
                  }}
                >
                  Describe the code you want to generate
                </label>
                <textarea
                  rows={6}
                  style={{
                    width: "100%",
                    padding: 16,
                    borderRadius: 12,
                    border: "1px solid #2d3548",
                    fontSize: 13,
                    fontFamily: "inherit",
                    resize: "vertical",
                    outline: "none",
                    boxSizing: "border-box",
                    background: "#0f1419",
                    color: "#94a3b8",
                    transition: "border-color 0.2s",
                    lineHeight: 1.6,
                  }}
                  placeholder="e.g., give javascript code for student management system..."
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onFocus={(e) => (e.target.style.borderColor = "#8b5cf6")}
                  onBlur={(e) => (e.target.style.borderColor = "#2d3548")}
                />

                <div style={{ marginTop: 20, display: "flex", gap: 12 }}>
                  <button
                    onClick={onGenerate}
                    disabled={loading || !prompt.trim()}
                    style={{
                      flex: 1,
                      padding: "14px 24px",
                      borderRadius: 10,
                      border: "none",
                      background:
                        loading || !prompt.trim()
                          ? "#2d3548"
                          : "linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)",
                      color: "white",
                      fontSize: 14,
                      fontWeight: 600,
                      cursor: loading || !prompt.trim() ? "not-allowed" : "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 8,
                      transition: "transform 0.2s",
                    }}
                  >
                    <Sparkles size={18} />
                    {loading ? "Generating..." : "Generate Secure Code"}
                  </button>

                  {out?.code && (
                    <button
                      onClick={copyCode}
                      style={{
                        padding: "14px 20px",
                        borderRadius: 10,
                        border: "1px solid #2d3548",
                        background: copied ? "#8b5cf6" : "transparent",
                        color: copied ? "#fff" : "#94a3b8",
                        fontSize: 14,
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      {copied ? <Check size={18} /> : <Copy size={18} />}
                    </button>
                  )}
                </div>
              </div>

              {/* UML Diagrams - Always visible when code is generated */}
              {out && (
                <div
                  style={{
                    background: "#1a1f2e",
                    borderRadius: 16,
                    padding: 24,
                    border: "1px solid #2d3548",
                  }}
                >
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "#64748b",
                      textTransform: "uppercase",
                      letterSpacing: "0.1em",
                      marginBottom: 20,
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <Workflow size={14} color="#ec4899" />
                    UML Diagrams
                  </div>

                  {!uml || uml.error ? (
                    <div
                      style={{
                        padding: 16,
                        background: "#0f1419",
                        borderRadius: 8,
                        border: "1px solid #2d3548",
                        color: "#64748b",
                        fontSize: 13,
                        textAlign: "center",
                      }}
                    >
                      {uml?.error
                        ? `UML generation: ${uml.error}`
                        : "No UML diagrams available for this generation (e.g. non-Java code)."}
                    </div>
                  ) : (
                    <>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "1fr 1fr",
                          gap: 12,
                          marginBottom: 20,
                        }}
                      >
                        {[
                          { key: "class_svg" as const, label: "Class Diagram" },
                          { key: "package_svg" as const, label: "Package Diagram" },
                          { key: "sequence_svg" as const, label: "Sequence Diagram" },
                          { key: "component_svg" as const, label: "Component Diagram" },
                          { key: "activity_svg" as const, label: "Activity Diagram" },
                        ].map(({ key, label }) => (
                          <div
                            key={key}
                            style={{
                              padding: 12,
                              background: "#0f1419",
                              borderRadius: 8,
                              border: `1px solid ${uml[key] ? "#8b5cf6" : "#2d3548"}`,
                              display: "flex",
                              alignItems: "center",
                              gap: 8,
                            }}
                          >
                            {uml[key] ? (
                              <CheckCircle2 size={16} color="#8b5cf6" />
                            ) : (
                              <MinusCircle size={16} color="#475569" />
                            )}
                            <span
                              style={{
                                fontSize: 12,
                                color: uml[key] ? "#8b5cf6" : "#64748b",
                                fontWeight: 500,
                              }}
                            >
                              {label}
                            </span>
                          </div>
                        ))}
                      </div>

                      <button
                        onClick={() => {
                          if (!uml) return;
                          const defaultTab: DiagramType =
                            uml.class_svg ? "class" :
                            uml.package_svg ? "package" :
                            uml.sequence_svg ? "sequence" :
                            uml.component_svg ? "component" : "activity";
                          setUmlTab(defaultTab);
                          setUmlOpen(true);
                        }}
                        style={{
                          width: "100%",
                          padding: "12px 20px",
                          borderRadius: 10,
                          border: "none",
                          background: "linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)",
                          color: "white",
                          fontSize: 13,
                          fontWeight: 600,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: 8,
                        }}
                      >
                        <Workflow size={16} />
                        Open UML Viewer
                      </button>
                    </>
                  )}
                </div>
              )}

              {/* Auto-Fix Results - Below UML, only when vulnerabilities found */}
              {out && fixSummary && fixSummary.initial_issues! > 0 && (
                <div
                  style={{
                    background: "#1a1f2e",
                    borderRadius: 16,
                    padding: 24,
                    border: "1px solid #2d3548",
                  }}
                >
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "#64748b",
                      textTransform: "uppercase",
                      letterSpacing: "0.1em",
                      marginBottom: 20,
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <Shield size={14} color="#8b5cf6" />
                    Auto-Fix Results
                  </div>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: 12,
                      marginBottom: 20,
                    }}
                  >
                    <div
                      style={{
                        padding: 16,
                        background: "#0f1419",
                        borderRadius: 12,
                        border: "1px solid #2d3548",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 10,
                          color: "#64748b",
                          marginBottom: 8,
                          textTransform: "uppercase",
                          fontWeight: 600,
                          letterSpacing: "0.05em",
                        }}
                      >
                        Initial Issues
                      </div>
                      <div style={{ fontSize: 28, fontWeight: 700, color: "#ef4444" }}>
                        {fixSummary.initial_issues}
                      </div>
                    </div>

                    <div
                      style={{
                        padding: 16,
                        background: "#0f1419",
                        borderRadius: 12,
                        border: "1px solid #2d3548",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 10,
                          color: "#64748b",
                          marginBottom: 8,
                          textTransform: "uppercase",
                          fontWeight: 600,
                          letterSpacing: "0.05em",
                        }}
                      >
                        Semgrep Fixed
                      </div>
                      <div style={{ fontSize: 28, fontWeight: 700, color: "#10b981" }}>
                        {fixSummary.semgrep_fixed}
                      </div>
                    </div>

                    <div
                      style={{
                        padding: 16,
                        background: "#0f1419",
                        borderRadius: 12,
                        border: "1px solid #2d3548",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 10,
                          color: "#64748b",
                          marginBottom: 8,
                          textTransform: "uppercase",
                          fontWeight: 600,
                          letterSpacing: "0.05em",
                        }}
                      >
                        LLM Fixed
                      </div>
                      <div style={{ fontSize: 28, fontWeight: 700, color: "#3b82f6" }}>
                        {fixSummary.llm_fixed || 0}
                      </div>
                    </div>

                    <div
                      style={{
                        padding: 16,
                        background: "#0f1419",
                        borderRadius: 12,
                        border: "1px solid #2d3548",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 10,
                          color: "#64748b",
                          marginBottom: 8,
                          textTransform: "uppercase",
                          fontWeight: 600,
                          letterSpacing: "0.05em",
                        }}
                      >
                        Remaining
                      </div>
                      <div
                        style={{
                          fontSize: 28,
                          fontWeight: 700,
                          color: fixSummary.remaining_issues === 0 ? "#10b981" : "#f59e0b",
                        }}
                      >
                        {fixSummary.remaining_issues}
                      </div>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div style={{ marginBottom: 16 }}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginBottom: 8,
                        fontSize: 12,
                      }}
                    >
                      <span style={{ color: "#64748b" }}>
                        Progress: Fixed {fixSummary.semgrep_fixed! + fixSummary.llm_fixed!}/
                        {fixSummary.initial_issues}
                      </span>
                      <span style={{ color: "#10b981", fontWeight: 700 }}>
                        {fixSummary.fix_rate_percent?.toFixed(0)}%
                      </span>
                    </div>
                    <div
                      style={{
                        width: "100%",
                        height: 8,
                        background: "#0f1419",
                        borderRadius: 999,
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: `${fixSummary.fix_rate_percent}%`,
                          height: "100%",
                          background: "#10b981",
                          transition: "width 0.5s ease",
                          borderRadius: 999,
                        }}
                      />
                    </div>
                  </div>

                  {/* Success Message */}
                  {fixSummary.remaining_issues === 0 && (
                    <div
                      style={{
                        padding: 12,
                        background: "rgba(16, 185, 129, 0.1)",
                        borderRadius: 8,
                        border: "1px solid rgba(16, 185, 129, 0.3)",
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        fontSize: 13,
                        color: "#10b981",
                        fontWeight: 500,
                      }}
                    >
                      <CheckCircle2 size={16} />
                      All {fixSummary.initial_issues} vulnerabilities automatically fixed!
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Right Column - Results */}
            {out && (
              <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
                {/* Generated Code */}
                <div
                  style={{
                    background: "#1a1f2e",
                    borderRadius: 16,
                    padding: 24,
                    border: "1px solid #2d3548",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: 16,
                    }}
                  >
                    <div
                      style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: "#64748b",
                        textTransform: "uppercase",
                        letterSpacing: "0.1em",
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <Code2 size={14} color="#8b5cf6" />
                      Generated Code
                    </div>
                    {out.original_code && out.original_code !== out.code && (
                      <button
                        onClick={() => setShowOriginal(!showOriginal)}
                        style={{
                          padding: "6px 12px",
                          borderRadius: 6,
                          border: "1px solid #8b5cf6",
                          background: showOriginal ? "#8b5cf6" : "transparent",
                          color: showOriginal ? "#fff" : "#8b5cf6",
                          fontSize: 11,
                          fontWeight: 600,
                          cursor: "pointer",
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                        }}
                      >
                        {showOriginal ? "Show Fixed" : "Show Original"}
                      </button>
                    )}
                  </div>

                  <pre
                    style={{
                      whiteSpace: "pre-wrap",
                      margin: 0,
                      fontSize: 12,
                      lineHeight: 1.7,
                      background: "#0a0f1a",
                      color: "#e2e8f0",
                      padding: 20,
                      borderRadius: 10,
                      overflow: "auto",
                      maxHeight: 500,
                      fontFamily: "'Fira Code', 'Cascadia Code', monospace",
                    }}
                  >
                    {showOriginal ? out.original_code : out.code}
                  </pre>
                </div>

                {/* Security Report */}
                <div
                  style={{
                    background: "#1a1f2e",
                    borderRadius: 16,
                    padding: 24,
                    border: "1px solid #2d3548",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      cursor: "pointer",
                    }}
                    onClick={() => setSecurityReportOpen(!securityReportOpen)}
                  >
                    <div
                      style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: "#64748b",
                        textTransform: "uppercase",
                        letterSpacing: "0.1em",
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <Shield size={14} color="#a855f7" />
                      Security Report
                    </div>
                    <ChevronDown
                      size={16}
                      color="#64748b"
                      style={{
                        transform: securityReportOpen ? "rotate(180deg)" : "rotate(0deg)",
                        transition: "transform 0.2s",
                      }}
                    />
                  </div>

                  <div style={{ marginTop: 12, fontSize: 11, color: "#64748b" }}>
                    Policy: {out.report.policy_version ?? "LLM01-2025-v1"}
                  </div>

                  {securityReportOpen && (
                    <>
                      <div
                        style={{
                          marginTop: 16,
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          fontSize: 12,
                          color: "#8b5cf6",
                          fontWeight: 500,
                          cursor: "pointer",
                        }}
                      >
                        <Code2 size={14} />
                        View Enhanced Prompt
                      </div>
                      <pre
                        style={{
                          whiteSpace: "pre-wrap",
                          margin: "12px 0 0 0",
                          fontSize: 11,
                          background: "#0a0f1a",
                          color: "#64748b",
                          padding: 16,
                          borderRadius: 8,
                          maxHeight: 300,
                          overflow: "auto",
                          fontFamily: "monospace",
                          lineHeight: 1.6,
                        }}
                      >
                        {out.report.prompt_after_enhancement}
                      </pre>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* UML Modal */}
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