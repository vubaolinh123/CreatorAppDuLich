import { useState } from "react";

// ── Types ──────────────────────────────────────────────────────────────────
interface StatCard {
  label: string;
  value: number;
  icon: string;
  color: string;
  bg: string;
}

interface RecentPost {
  id: string;
  title: string;
  creator: string;
  status: "pending" | "synced" | "published";
  date: string;
}

interface HomeScreenProps {
  onNavigate: (screen: string) => void;
}

// ── Mock Data ──────────────────────────────────────────────────────────────
const MOCK_RECENT_POSTS: RecentPost[] = [
  {
    id: "1",
    title: "Đà Nẵng - Thiên đường biển miền Trung",
    creator: "Creator 2",
    status: "published",
    date: "2026-06-09",
  },
  {
    id: "2",
    title: "Phú Quốc resort review 2026",
    creator: "Creator 1",
    status: "synced",
    date: "2026-06-08",
  },
  {
    id: "3",
    title: "Hội An - Phố cổ đêm lãng mạn",
    creator: "Creator 3",
    status: "pending",
    date: "2026-06-07",
  },
];

// ── Helpers ────────────────────────────────────────────────────────────────
function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Chào buổi sáng! 👋";
  if (h < 18) return "Chào buổi chiều! 👋";
  return "Chào buổi tối! 👋";
}

function formatDate(): string {
  return new Date().toLocaleDateString("vi-VN", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function statusLabel(s: RecentPost["status"]) {
  const map = {
    pending: { text: "Chờ đồng bộ", color: "#f59e0b" },
    synced: { text: "Đã đồng bộ", color: "#6366f1" },
    published: { text: "Đã đăng", color: "#10b981" },
  };
  return map[s];
}

// ── Component ──────────────────────────────────────────────────────────────
export default function HomeScreen({ onNavigate }: HomeScreenProps) {
  const [pingStatus, setPingStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [venvStatus, setVenvStatus] = useState<"idle" | "loading" | "found" | "missing">("idle");
  const [dashboardUrl] = useState("http://localhost:3000");

  const stats: StatCard[] = [
    { label: "Tổng bài", value: 24, icon: "📦", color: "#a78bfa", bg: "rgba(167,139,250,0.08)" },
    { label: "Chờ đồng bộ", value: 3, icon: "⏳", color: "#f59e0b", bg: "rgba(245,158,11,0.08)" },
    { label: "Đã đồng bộ", value: 18, icon: "☁️", color: "#6366f1", bg: "rgba(99,102,241,0.08)" },
    { label: "Đã đăng", value: 14, icon: "✅", color: "#10b981", bg: "rgba(16,185,129,0.08)" },
  ];

  const testConnection = async () => {
    setPingStatus("loading");
    await new Promise((r) => setTimeout(r, 1200));
    // Mock: 80% chance success
    setPingStatus(Math.random() > 0.2 ? "ok" : "error");
  };

  const checkVenv = async () => {
    setVenvStatus("loading");
    await new Promise((r) => setTimeout(r, 900));
    setVenvStatus("found");
  };

  return (
    <div style={styles.container}>
      {/* ── Header ── */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.greeting}>{getGreeting()}</h1>
          <p style={styles.dateText}>{formatDate()}</p>
        </div>
        <div style={styles.headerRight}>
          <div style={styles.versionBadge}>v1.0.0</div>
        </div>
      </div>

      {/* ── Stat Cards ── */}
      <div style={styles.statsRow}>
        {stats.map((card) => (
          <div key={card.label} style={{ ...styles.statCard, background: card.bg, borderColor: card.color + "30" }}>
            <div style={styles.statIconWrap}>
              <span style={styles.statIcon}>{card.icon}</span>
            </div>
            <div style={styles.statValue}>{card.value}</div>
            <div style={{ ...styles.statLabel, color: card.color }}>{card.label}</div>
          </div>
        ))}
      </div>

      {/* ── Two-column layout ── */}
      <div style={styles.twoCol}>
        {/* Left column */}
        <div style={styles.leftCol}>
          {/* System Status */}
          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>🖥️ Trạng thái hệ thống</h2>

            {/* Dashboard Connection */}
            <div style={styles.statusCard}>
              <div style={styles.statusRow}>
                <div style={styles.statusDot(pingStatus === "ok" ? "#10b981" : pingStatus === "error" ? "#ef4444" : "#6b7280")} />
                <div>
                  <div style={styles.statusName}>Dashboard Connection</div>
                  <div style={styles.statusUrl}>{dashboardUrl}</div>
                </div>
                <button
                  style={{
                    ...styles.testBtn,
                    opacity: pingStatus === "loading" ? 0.6 : 1,
                    cursor: pingStatus === "loading" ? "not-allowed" : "pointer",
                  }}
                  onClick={testConnection}
                  disabled={pingStatus === "loading"}
                >
                  {pingStatus === "loading" ? "Đang kiểm tra…" : "Test kết nối"}
                </button>
              </div>
              {pingStatus === "ok" && (
                <div style={styles.statusMsg("#10b981")}>✅ Kết nối thành công! Dashboard đang online.</div>
              )}
              {pingStatus === "error" && (
                <div style={styles.statusMsg("#ef4444")}>❌ Không thể kết nối. Kiểm tra dashboard URL.</div>
              )}
            </div>

            {/* Python Pipeline */}
            <div style={styles.statusCard}>
              <div style={styles.statusRow}>
                <div style={styles.statusDot(venvStatus === "found" ? "#10b981" : venvStatus === "missing" ? "#ef4444" : "#6b7280")} />
                <div>
                  <div style={styles.statusName}>Python Pipeline</div>
                  <div style={styles.statusUrl}>
                    {venvStatus === "found"
                      ? "✔ .venv đã được cài đặt"
                      : venvStatus === "missing"
                      ? "✘ Không tìm thấy .venv"
                      : "Chưa kiểm tra"}
                  </div>
                </div>
                <button
                  style={{
                    ...styles.testBtn,
                    opacity: venvStatus === "loading" ? 0.6 : 1,
                    cursor: venvStatus === "loading" ? "not-allowed" : "pointer",
                  }}
                  onClick={checkVenv}
                  disabled={venvStatus === "loading"}
                >
                  {venvStatus === "loading" ? "Đang kiểm tra…" : "Kiểm tra"}
                </button>
              </div>
            </div>
          </section>

          {/* Recent Posts */}
          <section style={styles.section}>
            <div style={styles.sectionHeader}>
              <h2 style={styles.sectionTitle}>🕐 Bài gần đây</h2>
              <button style={styles.linkBtn} onClick={() => onNavigate("library")}>
                Xem tất cả →
              </button>
            </div>
            <div style={styles.tableWrap}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    {["Tiêu đề", "Creator", "Ngày", "Trạng thái"].map((h) => (
                      <th key={h} style={styles.th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {MOCK_RECENT_POSTS.map((post) => {
                    const s = statusLabel(post.status);
                    return (
                      <tr key={post.id} style={styles.tr}>
                        <td style={styles.td}>
                          <div style={styles.postTitle}>{post.title}</div>
                        </td>
                        <td style={styles.td}>
                          <span style={styles.creatorTag}>{post.creator}</span>
                        </td>
                        <td style={styles.td}>{post.date}</td>
                        <td style={styles.td}>
                          <span style={{ ...styles.badge, color: s.color, borderColor: s.color + "40", background: s.color + "10" }}>
                            {s.text}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        {/* Right column — Quick Actions */}
        <div style={styles.rightCol}>
          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>⚡ Hành động nhanh</h2>

            {/* Primary CTA */}
            <button style={styles.primaryAction} onClick={() => onNavigate("studio")}>
              <span style={styles.primaryActionIcon}>✨</span>
              <div>
                <div style={styles.primaryActionTitle}>Tạo bài mới</div>
                <div style={styles.primaryActionSub}>Khởi động wizard sản xuất video</div>
              </div>
              <span style={styles.arrowIcon}>→</span>
            </button>

            {/* Secondary actions */}
            <div style={styles.secondaryActions}>
              <button style={styles.secondaryAction} onClick={() => onNavigate("library")}>
                <span style={styles.secIcon}>📋</span>
                <div>
                  <div style={styles.secTitle}>Xem tất cả bài</div>
                  <div style={styles.secSub}>Thư viện & lịch sử</div>
                </div>
              </button>
              <button style={styles.secondaryAction} onClick={() => onNavigate("settings")}>
                <span style={styles.secIcon}>⚙️</span>
                <div>
                  <div style={styles.secTitle}>Cài đặt</div>
                  <div style={styles.secSub}>API keys, creators</div>
                </div>
              </button>
              <button style={styles.secondaryAction} onClick={() => onNavigate("logs")}>
                <span style={styles.secIcon}>📜</span>
                <div>
                  <div style={styles.secTitle}>Xem logs</div>
                  <div style={styles.secSub}>Lịch sử chạy pipeline</div>
                </div>
              </button>
            </div>
          </section>

          {/* Tips */}
          <section style={styles.tipsCard}>
            <div style={styles.tipsTitle}>💡 Mẹo hôm nay</div>
            <p style={styles.tipsText}>
              Thêm địa điểm seeding vào bài để AI tạo nội dung phong phú hơn.
              Ví dụ: "Nhà hàng Phố Cổ Hội An", "Khách sạn Grand World Phú Quốc".
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────
const styles: Record<string, any> = {
  container: {
    padding: "28px 32px",
    height: "100%",
    overflowY: "auto",
    boxSizing: "border-box",
    background: "#0f0f0f",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 28,
  },
  greeting: {
    fontSize: 26,
    fontWeight: 700,
    color: "#f1f1f1",
    margin: 0,
    letterSpacing: -0.5,
  },
  dateText: {
    fontSize: 13,
    color: "#6b7280",
    margin: "4px 0 0",
  },
  headerRight: { display: "flex", gap: 10, alignItems: "center" },
  versionBadge: {
    fontSize: 11,
    color: "#6b7280",
    background: "#1e1e1e",
    border: "1px solid #333",
    borderRadius: 20,
    padding: "3px 10px",
  },

  // Stats
  statsRow: {
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: 16,
    marginBottom: 28,
  },
  statCard: {
    borderRadius: 14,
    padding: "20px 18px",
    border: "1px solid transparent",
    display: "flex",
    flexDirection: "column",
    gap: 6,
    transition: "transform 0.15s",
    cursor: "default",
  },
  statIconWrap: { marginBottom: 4 },
  statIcon: { fontSize: 22 },
  statValue: {
    fontSize: 32,
    fontWeight: 800,
    color: "#f1f1f1",
    lineHeight: 1,
  },
  statLabel: { fontSize: 12, fontWeight: 500 },

  // Layout
  twoCol: {
    display: "grid",
    gridTemplateColumns: "1fr 340px",
    gap: 20,
    alignItems: "start",
  },
  leftCol: { display: "flex", flexDirection: "column", gap: 20 },
  rightCol: { display: "flex", flexDirection: "column", gap: 16 },

  // Section
  section: {
    background: "#161616",
    border: "1px solid #252525",
    borderRadius: 16,
    padding: "20px 22px",
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: "#d1d5db",
    margin: "0 0 16px",
  },
  sectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  linkBtn: {
    background: "none",
    border: "none",
    color: "#818cf8",
    fontSize: 12,
    cursor: "pointer",
    padding: 0,
  },

  // Status cards
  statusCard: {
    background: "#1e1e1e",
    borderRadius: 10,
    padding: "14px 16px",
    marginBottom: 10,
    border: "1px solid #2a2a2a",
  },
  statusRow: {
    display: "flex",
    alignItems: "center",
    gap: 14,
  },
  statusDot: (color: string) => ({
    width: 10,
    height: 10,
    borderRadius: "50%",
    background: color,
    flexShrink: 0,
    boxShadow: `0 0 6px ${color}`,
  }),
  statusName: { fontSize: 13, fontWeight: 600, color: "#e5e7eb" },
  statusUrl: { fontSize: 11, color: "#6b7280", marginTop: 2 },
  testBtn: {
    marginLeft: "auto",
    background: "linear-gradient(135deg, #6366f1, #818cf8)",
    border: "none",
    borderRadius: 8,
    color: "#fff",
    fontSize: 12,
    fontWeight: 600,
    padding: "7px 14px",
    cursor: "pointer",
    flexShrink: 0,
    transition: "opacity 0.2s",
  },
  statusMsg: (color: string) => ({
    fontSize: 12,
    color,
    marginTop: 8,
    paddingTop: 8,
    borderTop: "1px solid #2a2a2a",
  }),

  // Table
  tableWrap: { overflowX: "auto" },
  table: { width: "100%", borderCollapse: "collapse" },
  th: {
    textAlign: "left",
    fontSize: 11,
    fontWeight: 600,
    color: "#6b7280",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    padding: "6px 10px",
    borderBottom: "1px solid #252525",
  },
  tr: {
    borderBottom: "1px solid #1e1e1e",
    transition: "background 0.1s",
  },
  td: {
    padding: "10px 10px",
    fontSize: 13,
    color: "#d1d5db",
    verticalAlign: "middle",
  },
  postTitle: {
    maxWidth: 240,
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
    color: "#e5e7eb",
    fontSize: 13,
  },
  creatorTag: {
    fontSize: 11,
    background: "#1e1e2e",
    color: "#a78bfa",
    borderRadius: 6,
    padding: "3px 8px",
    border: "1px solid #3730a380",
  },
  badge: {
    fontSize: 11,
    fontWeight: 600,
    borderRadius: 20,
    padding: "3px 10px",
    border: "1px solid",
    whiteSpace: "nowrap",
  },

  // Quick actions
  primaryAction: {
    width: "100%",
    background: "linear-gradient(135deg, #6366f1 0%, #818cf8 50%, #38bdf8 100%)",
    border: "none",
    borderRadius: 14,
    padding: "18px 20px",
    display: "flex",
    alignItems: "center",
    gap: 14,
    cursor: "pointer",
    textAlign: "left",
    marginBottom: 14,
    transition: "filter 0.2s, transform 0.15s",
    boxShadow: "0 4px 24px rgba(99,102,241,0.35)",
  },
  primaryActionIcon: { fontSize: 28, flexShrink: 0 },
  primaryActionTitle: { fontSize: 16, fontWeight: 700, color: "#fff" },
  primaryActionSub: { fontSize: 12, color: "rgba(255,255,255,0.75)", marginTop: 2 },
  arrowIcon: { marginLeft: "auto", color: "rgba(255,255,255,0.8)", fontSize: 18, flexShrink: 0 },

  secondaryActions: { display: "flex", flexDirection: "column", gap: 10 },
  secondaryAction: {
    width: "100%",
    background: "#1e1e1e",
    border: "1px solid #2a2a2a",
    borderRadius: 12,
    padding: "14px 16px",
    display: "flex",
    alignItems: "center",
    gap: 12,
    cursor: "pointer",
    textAlign: "left",
    transition: "border-color 0.15s, background 0.15s",
  },
  secIcon: { fontSize: 20, flexShrink: 0 },
  secTitle: { fontSize: 13, fontWeight: 600, color: "#e5e7eb" },
  secSub: { fontSize: 11, color: "#6b7280", marginTop: 2 },

  // Tips
  tipsCard: {
    background: "linear-gradient(135deg, rgba(99,102,241,0.1), rgba(56,189,248,0.06))",
    border: "1px solid rgba(99,102,241,0.25)",
    borderRadius: 14,
    padding: "16px 18px",
  },
  tipsTitle: { fontSize: 13, fontWeight: 600, color: "#a78bfa", marginBottom: 8 },
  tipsText: { fontSize: 12, color: "#9ca3af", lineHeight: 1.6, margin: 0 },
};
