import React from "react";
import { X, Box, Boxes, GitBranch, Eye } from "lucide-react";

type UmlReport = {
  ok?: boolean;
  file_count?: number;
  error?: string | null;
  class_svg?: string | null;
  package_svg?: string | null;
  sequence_svg?: string | null;
  component_svg?: string | null;
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
  tab: "class" | "package" | "sequence" | "component";
  setTab: React.Dispatch<
    React.SetStateAction<"class" | "package" | "sequence" | "component">
  >;
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
        alignItems: "stretch",
        justifyContent: "stretch",
        zIndex: 1000,
        padding: 0,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100vw",
          height: "100vh",
          maxWidth: "none",
          maxHeight: "none",
          background: "#ffffff",
          borderRadius: 0,
          boxShadow: "none",
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
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 10,
                background: "#e0f2fe",
                display: "grid",
                placeItems: "center",
                border: "1px solid #bae6fd",
              }}
            >
              <Eye size={18} color="#0369a1" />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, color: "#0f172a" }}>
                UML Viewer
              </div>
              <div style={{ fontSize: 12, color: "#64748b" }}>
                View generated diagrams
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              border: "1px solid #e2e8f0",
              background: "#ffffff",
              cursor: "pointer",
              color: "#475569",
              padding: 8,
              borderRadius: 10,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            aria-label="Close UML viewer"
            title="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div
          style={{
            padding: "10px 16px",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
          }}
        >
          <TabButton
            label="Class Diagram"
            icon={<Box size={16} />}
            active={tab === "class"}
            disabled={!uml.class_svg}
            onClick={() => uml.class_svg && setTab("class")}
          />
          <TabButton
            label="Package Diagram"
            icon={<Boxes size={16} />}
            active={tab === "package"}
            disabled={!uml.package_svg}
            onClick={() => uml.package_svg && setTab("package")}
          />
          <TabButton
            label="Sequence Diagram"
            icon={<GitBranch size={16} />}
            active={tab === "sequence"}
            disabled={!uml.sequence_svg}
            onClick={() => uml.sequence_svg && setTab("sequence")}
          />
          <TabButton
            label="Component Diagram"
            icon={<Box size={16} />}
            active={tab === "component"}
            disabled={!uml.component_svg}
            onClick={() => uml.component_svg && setTab("component")}
          />
        </div>

        {/* Content */}
        <div
          style={{
            padding: 16,
            flex: 1,
            overflow: "hidden",
            background: "#f8fafc",
          }}
        >
          {tab === "class" && uml.class_svg && (
            <DiagramCard title="Class Diagram" svg={uml.class_svg} />
          )}
          {tab === "package" && uml.package_svg && (
            <DiagramCard title="Package Diagram" svg={uml.package_svg} />
          )}
          {tab === "sequence" && uml.sequence_svg && (
            <DiagramCard title="Sequence Diagram" svg={uml.sequence_svg} />
          )}
          {tab === "component" && uml.component_svg && (
            <DiagramCard title="Component Diagram" svg={uml.component_svg} />
          )}
        </div>

        {/* SVG rendering tweaks + remove underline */}
        <style>{`
          .uml-svg svg {
            width: 100% !important;
            height: auto !important;
          }

          /* ✅ Remove underline in PlantUML SVG */
          .uml-svg svg text,
          .uml-svg svg a,
          .uml-svg svg a text {
            text-decoration: none !important;
          }

          /* ✅ Prevent link-like styling */
          .uml-svg svg a:link,
          .uml-svg svg a:visited {
            fill: inherit !important;
            color: inherit !important;
          }
        `}</style>
      </div>
    </div>
  );
}

function TabButton({
  label,
  icon,
  active,
  disabled,
  onClick,
}: {
  label: string;
  icon: React.ReactNode;
  active: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: "8px 14px",
        borderRadius: 999,
        border: active ? "1px solid #0ea5e9" : "1px solid #cbd5e1",
        background: active ? "#e0f2fe" : "#ffffff",
        color: active ? "#0369a1" : "#475569",
        fontSize: 13,
        fontWeight: 600,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.4 : 1,
        display: "flex",
        alignItems: "center",
        gap: 8,
      }}
      title={label}
    >
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {icon}
      </span>
      <span>{label}</span>
    </button>
  );
}

function DiagramCard({ title, svg }: { title: string; svg: string }) {
  return (
    <div
      style={{
        height: "100%",
        background: "#ffffff",
        borderRadius: 10,
        border: "1px solid #e2e8f0",
        padding: 12,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 8,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
          {title}
        </div>
      </div>

      <div
        className="uml-svg"
        style={{
          flex: 1,
          overflow: "auto",
          borderRadius: 8,
          background: "#ffffff",
          border: "1px solid #f1f5f9",
        }}
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </div>
  );
}