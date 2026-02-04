import React from "react";

type UmlReport = {
  ok?: boolean;
  file_count?: number;
  error?: string | null;
  class_svg?: string | null;
  package_svg?: string | null;
  sequence_svg?: string | null;
};

export default function UmlViewerModal({
  open,
  uml,
  tab,
  setTab,
  onClose,
}: {
  open: boolean;
  uml: UmlReport;
  tab: "class" | "package" | "sequence";
  setTab: React.Dispatch<React.SetStateAction<"class" | "package" | "sequence">>;
  onClose: () => void;
}) {
  if (!open || !uml || uml.error) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,23,42,0.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 1100,
          maxHeight: "90vh",
          background: "#ffffff",
          borderRadius: 12,
          boxShadow: "0 20px 50px rgba(15,23,42,0.45)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Modal header */}
        <div
          style={{
            padding: "16px 20px 12px 20px",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, color: "#0f172a" }}>UML Viewer</div>
            <div style={{ fontSize: 12, color: "#64748b" }}>View generated diagrams</div>
          </div>
          <button
            onClick={onClose}
            style={{
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: 18,
              color: "#475569",
              padding: 4,
            }}
            aria-label="Close UML viewer"
          >
            ✕
          </button>
        </div>

        {/* Tabs */}
        <div
          style={{
            padding: "8px 16px 4px 16px",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            gap: 8,
          }}
        >
          <button
            onClick={() => uml.class_svg && setTab("class")}
            disabled={!uml.class_svg}
            style={{
              padding: "6px 14px",
              borderRadius: 999,
              border: tab === "class" ? "1px solid #0ea5e9" : "1px solid #cbd5e1",
              background: tab === "class" ? "#e0f2fe" : "#f8fafc",
              color: tab === "class" ? "#0369a1" : "#475569",
              fontSize: 13,
              fontWeight: 600,
              cursor: uml.class_svg ? "pointer" : "not-allowed",
              opacity: uml.class_svg ? 1 : 0.4,
            }}
          >
            Class Diagram
          </button>

          <button
            onClick={() => uml.package_svg && setTab("package")}
            disabled={!uml.package_svg}
            style={{
              padding: "6px 14px",
              borderRadius: 999,
              border: tab === "package" ? "1px solid #0ea5e9" : "1px solid #cbd5e1",
              background: tab === "package" ? "#e0f2fe" : "#f8fafc",
              color: tab === "package" ? "#0369a1" : "#475569",
              fontSize: 13,
              fontWeight: 600,
              cursor: uml.package_svg ? "pointer" : "not-allowed",
              opacity: uml.package_svg ? 1 : 0.4,
            }}
          >
            Package Diagram
          </button>

          <button
            onClick={() => uml.sequence_svg && setTab("sequence")}
            disabled={!uml.sequence_svg}
            style={{
              padding: "6px 14px",
              borderRadius: 999,
              border: tab === "sequence" ? "1px solid #0ea5e9" : "1px solid #cbd5e1",
              background: tab === "sequence" ? "#e0f2fe" : "#f8fafc",
              color: tab === "sequence" ? "#0369a1" : "#475569",
              fontSize: 13,
              fontWeight: 600,
              cursor: uml.sequence_svg ? "pointer" : "not-allowed",
              opacity: uml.sequence_svg ? 1 : 0.4,
            }}
          >
            Sequence Diagram
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: 16, flex: 1, overflow: "auto", background: "#f8fafc" }}>
          {tab === "class" && uml.class_svg && (
            <DiagramCard title="Class Diagram" svg={uml.class_svg} />
          )}
          {tab === "package" && uml.package_svg && (
            <DiagramCard title="Package Diagram" svg={uml.package_svg} />
          )}
          {tab === "sequence" && uml.sequence_svg && (
            <DiagramCard title="Sequence Diagram" svg={uml.sequence_svg} />
          )}
        </div>
      </div>
    </div>
  );
}

function DiagramCard({ title, svg }: { title: string; svg: string }) {
  return (
    <div
      style={{
        background: "#ffffff",
        borderRadius: 8,
        border: "1px solid #e2e8f0",
        padding: 10,
        minHeight: 300,
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, color: "#0f172a", marginBottom: 6 }}>
        {title}
      </div>
      <div
        style={{
          overflow: "auto",
          maxHeight: "70vh",
          borderRadius: 6,
          background: "#ffffff",
        }}
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </div>
  );
}
