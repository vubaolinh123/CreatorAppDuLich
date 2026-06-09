import { useState, useRef, useEffect } from "react";

type LogLevel = "info" | "success" | "warning" | "error";
type LogFilter = "all" | LogLevel;

interface LogLine {
  id: string;
  time: string;
  level: LogLevel;
  text: string;
}

function genId() {
  return Math.random().toString(36).slice(2, 9);
}

// ── Mock Logs ──────────────────────────────────────────────────────────────
const INITIAL_LOGS: LogLine[] = [
  { id: genId(), time: "17:30:01", level: "info", text: "[System] DuLichApp Desktop v0.1.0 đã khởi động" },
  { id: genId(), time: "17:30:01", level: "info", text: "[System] Đang đọc cấu hình từ settings.json..." },
  { id: genId(), time: "17:30:02", level: "success", text: "[System] ✓ Cấu hình đã tải thành công" },
  { id: genId(), time: "17:30:02", level: "info", text: "[DB] Đang kết nối local database..." },
  { id: genId(), time: "17:30:02", level: "success", text: "[DB] ✓ Đã tải 4 bài viết từ library.json" },
  { id: genId(), time: "17:31:15", level: "info", text: "[Pipeline] Nhận yêu cầu tạo bài: \"Đà Nẵng travel 2026\"" },
  { id: genId(), time: "17:31:15", level: "info", text: "[Pipeline] Creator: Nguyễn Thành Nam — Template: 9:16" },
  { id: genId(), time: "17:31:16", level: "info", text: "[Trend] Phân tích xu hướng cho chủ đề Đà Nẵng..." },
  { id: genId(), time: "17:31:17", level: "success", text: "[Trend] ✓ Phát hiện 3 xu hướng phù hợp" },
  { id: genId(), time: "17:31:17", level: "info", text: "[Script] Gọi Claude claude-3-5-sonnet để viết kịch bản..." },
  { id: genId(), time: "17:31:17", level: "warning", text: "[Script] ANTHROPIC_API_KEY không có — chuyển sang Mock mode" },
  { id: genId(), time: "17:31:18", level: "success", text: "[Script] ✓ Kịch bản Mock đã tạo xong (247 từ)" },
  { id: genId(), time: "17:31:19", level: "info", text: "[Captions] Tạo caption ngắn và dài..." },
  { id: genId(), time: "17:31:19", level: "success", text: "[Captions] ✓ Caption + 12 hashtags đã tạo" },
  { id: genId(), time: "17:31:20", level: "info", text: "[Images] Tạo 5 image prompts cho Midjourney/DALL-E..." },
  { id: genId(), time: "17:31:20", level: "success", text: "[Images] ✓ Image prompts đã tạo" },
  { id: genId(), time: "17:31:21", level: "info", text: "[Voice] Kết nối ElevenLabs API..." },
  { id: genId(), time: "17:31:21", level: "warning", text: "[Voice] ELEVENLABS_API_KEY trống — dùng silent mock audio" },
  { id: genId(), time: "17:31:22", level: "success", text: "[Voice] ✓ Audio mock đã tạo: output/audio/danang_mock.wav" },
  { id: genId(), time: "17:31:23", level: "info", text: "[Video] Khởi động render với FFmpeg..." },
  { id: genId(), time: "17:31:25", level: "success", text: "[Video] ✓ Video đã render: output/videos/danang_mock.mp4" },
  { id: genId(), time: "17:31:26", level: "success", text: "[Pipeline] ✅ Pipeline hoàn tất! Tổng thời gian: 11s" },
  { id: genId(), time: "17:32:00", level: "info", text: "[Sync] Đang gửi metadata lên Dashboard: http://localhost:3000" },
  { id: genId(), time: "17:32:01", level: "error", text: "[Sync] ❌ Lỗi kết nối: ECONNREFUSED http://localhost:3000/api/videos" },
  { id: genId(), time: "17:32:01", level: "warning", text: "[Sync] Sẽ tự động thử lại lần sau khi Dashboard online" },
];

const LOG_COLORS: Record<LogLevel, string> = {
  info: "#9ca3af",
  success: "#10b981",
  warning: "#f59e0b",
  error: "#ef4444",
};

const LOG_PREFIXES: Record<LogLevel, string> = {
  info: "INFO",
  success: "OK  ",
  warning: "WARN",
  error: "ERR ",
};

export default function LogsScreen() {
  const [logs, setLogs] = useState<LogLine[]>(INITIAL_LOGS);
  const [filter, setFilter] = useState<LogFilter>("all");
  const [autoScroll, setAutoScroll] = useState(true);
  const consoleRef = useRef<HTMLDivElement>(null);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const clearLogs = () => setLogs([]);

  const exportLogs = () => {
    const content = logs
      .map((l) => `[${l.time}] [${LOG_PREFIXES[l.level]}] ${l.text}`)
      .join("\n");
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `dulichapp-logs-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const filteredLogs = filter === "all" ? logs : logs.filter((l) => l.level === filter);

  const counts: Record<LogFilter, number> = {
    all: logs.length,
    info: logs.filter((l) => l.level === "info").length,
    success: logs.filter((l) => l.level === "success").length,
    warning: logs.filter((l) => l.level === "warning").length,
    error: logs.filter((l) => l.level === "error").length,
  };

  const FILTER_OPTIONS: { id: LogFilter; label: string; color: string }[] = [
    { id: "all", label: "Tất cả", color: "#6b7280" },
    { id: "info", label: "Info", color: "#9ca3af" },
    { id: "success", label: "Thành công", color: "#10b981" },
    { id: "warning", label: "Cảnh báo", color: "#f59e0b" },
    { id: "error", label: "Lỗi", color: "#ef4444" },
  ];

  return (
    <div style={s.container}>
      {/* Header */}
      <div style={s.header}>
        <div>
          <h1 style={s.title}>📊 Nhật ký hệ thống</h1>
          <p style={s.subtitle}>{logs.length} dòng logs</p>
        </div>
        <div style={s.headerActions}>
          <button
            style={{ ...s.actionBtn, ...(autoScroll ? s.actionBtnActive : {}) }}
            onClick={() => setAutoScroll((p) => !p)}
            title="Tự động cuộn xuống"
          >
            {autoScroll ? "🔒 Đang theo dõi" : "▶️ Theo dõi"}
          </button>
          <button style={s.actionBtn} onClick={exportLogs}>
            ⬇️ Export .txt
          </button>
          <button style={{ ...s.actionBtn, ...s.dangerBtn }} onClick={clearLogs}>
            🗑️ Xóa logs
          </button>
        </div>
      </div>

      {/* Filter + Count badges */}
      <div style={s.filterBar}>
        {FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.id}
            style={{
              ...s.filterBtn,
              ...(filter === opt.id
                ? { borderColor: opt.color + "60", background: opt.color + "12", color: opt.color }
                : {}),
            }}
            onClick={() => setFilter(opt.id)}
          >
            {opt.label}
            <span
              style={{
                ...s.countBadge,
                background: filter === opt.id ? opt.color + "20" : "#1e1e1e",
                color: filter === opt.id ? opt.color : "#6b7280",
              }}
            >
              {counts[opt.id]}
            </span>
          </button>
        ))}
      </div>

      {/* Console */}
      <div ref={consoleRef} style={s.console}>
        {filteredLogs.length === 0 ? (
          <div style={s.emptyConsole}>
            <div style={{ fontSize: 40, marginBottom: 12, opacity: 0.4 }}>📭</div>
            <div style={{ color: "#4b5563", fontSize: 13 }}>
              {filter === "all" ? "Chưa có logs nào..." : `Không có logs loại "${filter}"`}
            </div>
          </div>
        ) : (
          filteredLogs.map((log) => (
            <div key={log.id} style={s.logLine}>
              <span style={s.logTime}>{log.time}</span>
              <span
                style={{
                  ...s.logLevel,
                  color: LOG_COLORS[log.level],
                  background: LOG_COLORS[log.level] + "18",
                }}
              >
                {LOG_PREFIXES[log.level]}
              </span>
              <span style={{ ...s.logText, color: LOG_COLORS[log.level] }}>
                {log.text}
              </span>
            </div>
          ))
        )}
        {/* Bottom anchor for auto-scroll */}
        <div style={{ height: 1 }} />
      </div>

      {/* Status bar */}
      <div style={s.statusBar}>
        <div style={{ display: "flex", gap: 16 }}>
          <span style={s.statusItem}>
            <span style={{ color: "#9ca3af" }}>●</span> {counts.info} info
          </span>
          <span style={s.statusItem}>
            <span style={{ color: "#10b981" }}>●</span> {counts.success} ok
          </span>
          <span style={s.statusItem}>
            <span style={{ color: "#f59e0b" }}>●</span> {counts.warning} warn
          </span>
          <span style={{ ...s.statusItem, color: counts.error > 0 ? "#ef4444" : "#6b7280" }}>
            <span style={{ color: "#ef4444" }}>●</span> {counts.error} error
          </span>
        </div>
        <div style={s.statusAutoScroll}>
          {autoScroll ? "🟢 Auto-scroll bật" : "⏸️ Auto-scroll tắt"}
        </div>
      </div>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────
const s: Record<string, any> = {
  container: {
    padding: "28px 32px 0",
    height: "100%",
    boxSizing: "border-box",
    background: "#0f0f0f",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
    flexShrink: 0,
  },
  title: { fontSize: 24, fontWeight: 700, color: "#f1f1f1", margin: 0 },
  subtitle: { fontSize: 13, color: "#6b7280", margin: "4px 0 0" },
  headerActions: { display: "flex", gap: 8 },
  actionBtn: {
    background: "#161616",
    border: "1px solid #252525",
    borderRadius: 8,
    color: "#9ca3af",
    fontSize: 12,
    fontWeight: 500,
    padding: "8px 14px",
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  actionBtnActive: {
    background: "rgba(99,102,241,0.12)",
    borderColor: "rgba(99,102,241,0.35)",
    color: "#818cf8",
  },
  dangerBtn: { color: "#ef4444", borderColor: "#ef444430" },
  filterBar: {
    display: "flex",
    gap: 6,
    marginBottom: 12,
    flexShrink: 0,
  },
  filterBtn: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    background: "#161616",
    border: "1px solid #252525",
    borderRadius: 8,
    color: "#6b7280",
    fontSize: 12,
    fontWeight: 500,
    padding: "6px 12px",
    cursor: "pointer",
    transition: "all 0.15s",
  },
  countBadge: {
    borderRadius: 20,
    padding: "1px 7px",
    fontSize: 11,
    fontWeight: 600,
    transition: "all 0.15s",
  },
  console: {
    flex: 1,
    background: "#050505",
    border: "1px solid #1a1a1a",
    borderRadius: 12,
    padding: "14px 16px",
    overflowY: "auto",
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace",
    fontSize: 12,
    lineHeight: 1.7,
    display: "flex",
    flexDirection: "column",
    gap: 2,
  },
  logLine: {
    display: "flex",
    gap: 10,
    alignItems: "baseline",
  },
  logTime: {
    color: "#404040",
    fontSize: 11,
    flexShrink: 0,
    fontVariantNumeric: "tabular-nums",
  },
  logLevel: {
    fontSize: 10,
    fontWeight: 700,
    padding: "1px 6px",
    borderRadius: 4,
    flexShrink: 0,
    letterSpacing: "0.03em",
  },
  logText: {
    fontSize: 12,
    wordBreak: "break-word",
  },
  emptyConsole: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
  },
  statusBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "8px 0 12px",
    flexShrink: 0,
    borderTop: "1px solid #1a1a1a",
    marginTop: 8,
  },
  statusItem: {
    display: "flex",
    alignItems: "center",
    gap: 5,
    fontSize: 11,
    color: "#6b7280",
  },
  statusAutoScroll: {
    fontSize: 11,
    color: "#6b7280",
  },
};
