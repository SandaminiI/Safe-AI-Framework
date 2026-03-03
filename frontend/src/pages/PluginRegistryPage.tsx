// SAFE-AI-FRAMEWORK/frontend/src/PluginRegistryPage.tsx

import { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8012";

type Plugin = {
  id: string;
  role: string;
  intent: string;
  trustScore: number;
  status: "trusted" | "restricted" | "blocked" | "anomalous";
  anomalyFlag?: boolean;
  lastActive: string;
  reqRate: string;
};

/** Map backend status to the union the UI expects. */
function normaliseStatus(
  status: string,
  anomalyFlag?: boolean
): Plugin["status"] {
  if (anomalyFlag) return "anomalous";
  const map: Record<string, Plugin["status"]> = {
    trusted: "trusted",
    restricted: "restricted",
    blocked: "blocked",
  };
  return map[status] ?? "blocked";
}

export default function PluginRegistryPage() {
  const [view, setView] = useState<"card" | "table">("card");
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchPlugins() {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`${API}/registry/plugins`);
        if (!res.ok) throw new Error(`Server responded ${res.status}`);
        const data: any[] = await res.json();
        if (cancelled) return;

        setPlugins(
          data.map((d) => ({
            id: d.id,
            role: d.role,
            intent: d.intent,
            trustScore: d.trustScore,
            status: normaliseStatus(d.status, d.anomalyFlag),
            anomalyFlag: d.anomalyFlag,
            lastActive: d.lastActive,
            reqRate: d.reqRate,
          }))
        );
      } catch (err: any) {
        if (!cancelled) setError(err.message ?? "Failed to load plugins");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchPlugins();
    const interval = setInterval(fetchPlugins, 5000); // auto-refresh every 5s
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div style={page}>
      <div style={container}>
        {/* HEADER */}
        <div style={header}>
          <div>
            <div style={titleRow}>
              <span style={shield}>🛡</span>
              <h1 style={title}>Plugin Registry & Trust Monitor</h1>
            </div>
            <div style={subtitle}>
              Real-time Zero Trust Observability for Active AI Plugins
            </div>
          </div>

          <div style={viewSwitch}>
            <button
              style={view === "card" ? activeTab : tab}
              onClick={() => setView("card")}
            >
              Card View
            </button>
            <button
              style={view === "table" ? activeTab : tab}
              onClick={() => setView("table")}
            >
              Table View
            </button>
          </div>
        </div>

        {/* METRICS */}
        <div style={metricsGrid}>
          {(() => {
            const total = plugins.length;
            const avg = total
              ? (plugins.reduce((s, p) => s + p.trustScore, 0) / total).toFixed(1)
              : "0.0";
            const active = plugins.filter((p) => p.status === "trusted").length;
            const restricted = plugins.filter((p) => p.status === "restricted").length;
            const blocked = plugins.filter(
              (p) => p.status === "blocked" && !p.anomalyFlag
            ).length;
            const revoked = plugins.filter((p) => p.anomalyFlag && p.status === "blocked").length;

            const entries: [string, string | number][] = [
              ["TOTAL PLUGINS", total],
              ["AVG TRUST SCORE", avg],
              ["ACTIVE", active],
              ["RESTRICTED", restricted],
              ["BLOCKED", blocked],
              ["REVOKED", revoked],
            ];

            return entries.map(([label, value], i) => (
              <div key={i} style={metricCard}>
                <div style={metricLabel}>{label}</div>
                <div style={metricValue}>{value}</div>
              </div>
            ));
          })()}
        </div>

        {/* LOADING / ERROR */}
        {loading && plugins.length === 0 && (
          <div style={centeredMsg}>Loading plugins…</div>
        )}
        {error && (
          <div style={{ ...centeredMsg, color: "#ef4444" }}>
            ⚠ {error}
          </div>
        )}

        {/* CARD VIEW */}
        {view === "card" && (
          <div style={cardGrid}>
            {plugins.map((p) => (
              <PluginCard key={p.id} plugin={p} />
            ))}
          </div>
        )}

        {/* TABLE VIEW */}
        {view === "table" && (
          <div style={tableWrapper}>
            <table style={table}>
              <thead>
                <tr>
                  <th style={th}>PLUGIN ID</th>
                  <th style={th}>STATUS</th>
                  <th style={th}>TRUST SCORE</th>
                  <th style={th}>ROLE</th>
                  <th style={th}>INTENT</th>
                  <th style={th}>REQ RATE</th>
                  <th style={th}>LAST ACTIVE</th>
                </tr>
              </thead>
              <tbody>
                {plugins.map((p) => (
                  <tr key={p.id} style={tr}>
                    <td style={tdId}>{p.id}</td>

                    <td style={td}>
                      <StatusBadge status={p.status} />
                    </td>

                    <td style={td}>
                      <div style={{ minWidth: 140 }}>
                        <div style={tableTrustBg}>
                          <div
                            style={{
                              ...tableTrustFill,
                              width: `${p.trustScore}%`,
                              background:
                                p.trustScore >= 70
                                  ? "#22c55e"
                                  : p.trustScore >= 40
                                  ? "#f59e0b"
                                  : "#ef4444",
                            }}
                          />
                        </div>
                        <div style={{ fontSize: 11, opacity: 0.6, marginTop: 4 }}>
                          {p.trustScore}/100
                        </div>
                      </div>
                    </td>

                    <td style={td}>{p.role}</td>
                    <td style={td}>{p.intent}</td>
                    <td style={td}>{p.reqRate}</td>
                    <td style={td}>{p.lastActive}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* FOOTER STATUS BAR */}
      <div style={footer}>
        <div style={{ color: "#22c55e" }}>● REGISTRY ONLINE</div>
        <div style={{ opacity: 0.6 }}>ZERO TRUST ENFORCED</div>
        <div style={{ opacity: 0.6 }}>SCAN FREQUENCY: 5s</div>
        <div style={{ color: "#a855f7" }}>v4.2.0-SECURE</div>
      </div>
    </div>
  );
}

/* ================= COMPONENTS ================= */

function PluginCard({ plugin }: { plugin: Plugin }) {
  const color =
    plugin.trustScore >= 70
      ? "#22c55e"
      : plugin.trustScore >= 40
      ? "#f59e0b"
      : "#ef4444";

  return (
    <div style={pluginCard}>
      <div style={cardTop}>
        <div style={pluginId}>{plugin.id}</div>
        <StatusBadge status={plugin.status} />
      </div>

      <div style={metaRow}>
        <div>
          <div style={metaLabel}>Role:</div>
          <div>{plugin.role}</div>
        </div>
        <div>
          <div style={metaLabel}>Declared Intent:</div>
          <div>{plugin.intent}</div>
        </div>
      </div>

      <div style={{ marginTop: 20 }}>
        <div style={metaLabel}>TRUST SCORE</div>
        <div style={trustBarBg}>
          <div
            style={{
              ...trustBarFill,
              width: `${plugin.trustScore}%`,
              background: color,
              boxShadow: `0 0 12px ${color}`,
            }}
          />
        </div>
        <div style={{ marginTop: 6, fontSize: 12, opacity: 0.6 }}>
          {plugin.trustScore}/100
        </div>
      </div>

      <div style={bottomRow}>
        <div style={{ opacity: 0.6 }}>
          {plugin.reqRate} · Last active: {plugin.lastActive}
        </div>
        <button style={detailsBtn}>View Details</button>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, { bg: string; color: string }> = {
    trusted: { bg: "#22c55e33", color: "#22c55e" },
    restricted: { bg: "#f59e0b33", color: "#f59e0b" },
    anomalous: { bg: "#eab30833", color: "#eab308" },
    blocked: { bg: "#ef444433", color: "#ef4444" },
  };
  const s = styles[status] ?? styles.blocked;

  return (
    <div
      style={{
        padding: "4px 10px",
        borderRadius: 20,
        fontSize: 11,
        fontWeight: 600,
        background: s.bg,
        color: s.color,
      }}
    >
      {status.toUpperCase()}
    </div>
  );
}

/* ================= STYLES ================= */

const page: React.CSSProperties = {
  minHeight: "100vh",
  width: "100vw", // FULL WIDTH FIX
  background: "linear-gradient(180deg, #140d2a, #0c0818)",
  color: "white",
  fontFamily: "Inter, sans-serif",
  display: "flex",
  flexDirection: "column",
  overflowX: "hidden",
};

const container: React.CSSProperties = {
  width: "100%",
  padding: "50px 80px",
  boxSizing: "border-box",
  flex: 1,
};

const header: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  flexWrap: "wrap",
  marginBottom: 40,
};

const titleRow = {
  display: "flex",
  alignItems: "center",
  gap: 12,
};

const shield = {
  fontSize: 22,
};

const title = {
  margin: 0,
  fontSize: 26,
  fontWeight: 700,
};

const subtitle = {
  marginTop: 8,
  opacity: 0.6,
  fontSize: 14,
};

const viewSwitch = {
  display: "flex",
  gap: 10,
  alignItems: "center",
};

const tab = {
  padding: "6px 14px",
  borderRadius: 8,
  border: "1px solid #4F0C87",
  background: "transparent",
  color: "white",
  cursor: "pointer",
};

const activeTab = {
  ...tab,
  background: "#4F0C87",
};

const metricsGrid: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 25,
  marginBottom: 50,
};

const metricCard: React.CSSProperties = {
  background: "#1a1335",
  padding: 25,
  borderRadius: 20,
  border: "1px solid #2d1f55",
};

const metricLabel = {
  fontSize: 11,
  opacity: 0.6,
  letterSpacing: 1,
};

const metricValue = {
  marginTop: 10,
  fontSize: 24,
  fontWeight: 700,
};

const cardGrid: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))",
  gap: 35,
};

const pluginCard: React.CSSProperties = {
  background: "#1a1335",
  padding: 28,
  borderRadius: 24,
  border: "1px solid #2d1f55",
};

const cardTop = {
  display: "flex",
  justifyContent: "space-between",
};

const pluginId = {
  fontSize: 18,
  fontWeight: 600,
};

const metaRow = {
  display: "flex",
  justifyContent: "space-between",
  marginTop: 18,
  fontSize: 14,
  opacity: 0.8,
};

const metaLabel = {
  fontSize: 11,
  opacity: 0.5,
  marginBottom: 4,
};

const trustBarBg = {
  height: 6,
  borderRadius: 6,
  background: "#2d1f55",
  marginTop: 8,
};

const trustBarFill = {
  height: "100%",
  borderRadius: 6,
};

const bottomRow = {
  marginTop: 24,
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  fontSize: 13,
};

const detailsBtn = {
  padding: "6px 16px",
  borderRadius: 10,
  border: "1px solid #7c3aed",
  background: "transparent",
  color: "#c084fc",
  cursor: "pointer",
};

const footer = {
  height: 45,
  background: "#0f0b1f",
  display: "flex",
  justifyContent: "space-around",
  alignItems: "center",
  fontSize: 12,
};

const centeredMsg: React.CSSProperties = {
  textAlign: "center",
  padding: "40px 0",
  fontSize: 16,
  opacity: 0.7,
};



const tableWrapper: React.CSSProperties = {
  marginTop: 10,
  background: "#1a1335",
  borderRadius: 24,
  border: "1px solid #2d1f55",
  padding: 30,
  overflowX: "auto",
};

const table: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  minWidth: 900,
};

const th: React.CSSProperties = {
  textAlign: "left",
  padding: "14px 16px",
  fontSize: 12,
  letterSpacing: 1,
  opacity: 0.6,
};

const td: React.CSSProperties = {
  padding: "18px 16px",
  borderTop: "1px solid #2d1f55",
  fontSize: 14,
};

const tdId: React.CSSProperties = {
  ...td,
  fontWeight: 600,
};

const tr: React.CSSProperties = {
  transition: "background 0.2s ease",
};

const tableTrustBg: React.CSSProperties = {
  height: 6,
  borderRadius: 6,
  background: "#2d1f55",
};

const tableTrustFill: React.CSSProperties = {
  height: "100%",
  borderRadius: 6,
  transition: "width 0.3s ease",
};