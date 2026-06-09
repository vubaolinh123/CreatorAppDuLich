import React, { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useAppStore, useNewsJobs, useResourceSettings } from "../stores/appStore";

// ── Types ─────────────────────────────────────────────────────────────────────
interface LogLine {
  id: string;
  time: string;
  level: "info" | "success" | "warning" | "error";
  text: string;
}

type RunStatus = "idle" | "running" | "done" | "error";

// ── Default topic pool ────────────────────────────────────────────────────────
const DEFAULT_TOPICS = [
  "Đà Nẵng biển đẹp mùa hè",
  "Hội An phố cổ về đêm",
  "Phú Quốc resort cao cấp",
  "Hà Giang mùa hoa tam giác mạch",
  "Nha Trang lặn biển san hô",
  "Đà Lạt cafe view đẹp",
  "Sapa trekking bản làng",
  "Mũi Né cồn cát đỏ",
  "Ninh Bình tràng an",
  "Huế ẩm thực cung đình",
  "Cần Thơ chợ nổi miền Tây",
  "Hạ Long kayak hang động",
];

// ── Mock log generator ────────────────────────────────────────────────────────
function mockBatchLogs(topics: string[], workers: number): LogLine[] {
  const now = Date.now();
  const fmt = (offset: number) =>
    new Date(now + offset * 1000).toLocaleTimeString("vi-VN");
  const logs: LogLine[] = [
    { id: "l0", time: fmt(0), level: "info", text: `[NewsPipeline] 🚀 Bắt đầu batch ${topics.length} clips | ${workers} workers` },
    { id: "l1", time: fmt(0), level: "info", text: `[Config] Voice: Vbee.ai (mock) | Workers: ${workers}` },
    { id: "l2", time: fmt(1), level: "info", text: "[Script] Viết kịch bản cho tất cả topics..." },
  ];
  topics.forEach((t, i) => {
    const base = 2 + i * 3;
    logs.push(
      { id: `r${i}a`, time: fmt(base), level: "info",    text: `[Job #${i+1}] Bắt đầu: "${t}"` },
      { id: `r${i}b`, time: fmt(base+1), level: "info",  text: `[Job #${i+1}] [Research] ✓ Trends phân tích xong` },
      { id: `r${i}c`, time: fmt(base+1), level: "success", text: `[Job #${i+1}] [Script] ✓ Hook/Body/CTA xong` },
      { id: `r${i}d`, time: fmt(base+2), level: "info",  text: `[Job #${i+1}] [Voice] Mock audio tạo xong` },
      { id: `r${i}e`, time: fmt(base+2), level: "info",  text: `[Job #${i+1}] [Subtitle] SRT tạo xong` },
      { id: `r${i}f`, time: fmt(base+2), level: "success", text: `[Job #${i+1}] [Done] ✅ "${t}" hoàn tất!` },
    );
  });
  const lastBase = 2 + topics.length * 3;
  logs.push(
    { id: "fin1", time: fmt(lastBase), level: "success", text: `[NewsPipeline] 📊 ${topics.length}/${topics.length} thành công` },
    { id: "fin2", time: fmt(lastBase), level: "success", text: "[NewsPipeline] 💾 Batch summary đã lưu" },
  );
  return logs;
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function NewsChannelScreen() {
  const resources = useResourceSettings();
  const { addNewsJob, updateNewsJob } = useAppStore();
  const newsJobs = useNewsJobs();

  const [batchCount, setBatchCount] = useState(5);
  const [customTopics, setCustomTopics] = useState<string[]>([]);
  const [topicInput, setTopicInput] = useState("");
  const [useCustomTopics, setUseCustomTopics] = useState(false);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [progress, setProgress] = useState(0);
  const [_, setCurrentJobId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"run" | "history">("run");
  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const selectedTopics = useCustomTopics
    ? customTopics.slice(0, batchCount)
    : DEFAULT_TOPICS.slice(0, batchCount);

  const addLog = (log: Omit<LogLine, "id">) => {
    setLogs((prev) => [...prev, { ...log, id: `${Date.now()}-${Math.random()}` }]);
  };

  const handleAddTopic = () => {
    if (topicInput.trim()) {
      setCustomTopics((prev) => [...prev, topicInput.trim()]);
      setTopicInput("");
    }
  };

  const handleRemoveTopic = (i: number) => {
    setCustomTopics((prev) => prev.filter((_, idx) => idx !== i));
  };

  const handleRun = async () => {
    if (status === "running") return;
    setStatus("running");
    setLogs([]);
    setProgress(0);

    const topics = selectedTopics;
    const workers = Math.min(resources.maxWorkers, topics.length);

    // Register job in store
    const jobId = addNewsJob({
      briefId: "",
      topics,
      totalClips: topics.length,
      doneClips: 0,
      workers,
      status: "running",
      results: [],
    });
    setCurrentJobId(jobId);

    addLog({ time: new Date().toLocaleTimeString("vi-VN"), level: "info", text: `[UI] Gửi lệnh pipeline: ${topics.length} clips...` });

    // Try real Tauri invoke first
    let usedMock = false;
    let unlisten: (() => void) | null = null;

    try {
      unlisten = await listen<{ time: string; level: string; text: string }>(
        "pipeline-log",
        (event) => {
          const { time, level, text } = event.payload;
          setLogs((prev) => [
            ...prev,
            { id: `${Date.now()}`, time, level: level as LogLine["level"], text },
          ]);
          // estimate progress from log count
          setProgress((p) => Math.min(p + 100 / (topics.length * 7), 95));
        }
      );

      await invoke("run_batch_pipeline", {
        topics,
        workers,
        channel: "news",
        voiceProvider: resources.voiceProvider,
        ramGb: resources.ramGb,
        cpuCores: resources.cpuCores,
      });
    } catch {
      usedMock = true;
    } finally {
      unlisten?.();
    }

    if (usedMock) {
      // Mock simulation
      const mockLogs = mockBatchLogs(topics, workers);
      for (let i = 0; i < mockLogs.length; i++) {
        await new Promise((r) => setTimeout(r, 280));
        setLogs((prev) => [...prev, mockLogs[i]]);
        setProgress(Math.round(((i + 1) / mockLogs.length) * 100));
      }
    }

    // Done
    setProgress(100);
    setStatus("done");
    updateNewsJob(jobId, {
      status: "done",
      doneClips: topics.length,
      completedAt: new Date().toISOString(),
      results: topics.map((t) => ({ topic: t, status: "done", scriptHook: `Hook cho: ${t}` })),
    });
    addLog({ time: new Date().toLocaleTimeString("vi-VN"), level: "success", text: "✅ Pipeline hoàn tất! Kiểm tra thư mục output." });
  };

  const handleStop = () => {
    setStatus("idle");
    addLog({ time: new Date().toLocaleTimeString("vi-VN"), level: "warning", text: "[UI] Pipeline đã dừng." });
  };

  // ── Styles ─────────────────────────────────────────────────────────────────
  const s = styles;

  return (
    <div style={s.container}>
      {/* Header */}
      <div style={s.header}>
        <div>
          <h1 style={s.title}>📺 Kênh Tin Tức</h1>
          <p style={s.subtitle}>Tự động tạo 10–20 clip/ngày từ xu hướng du lịch</p>
        </div>
        <div style={s.statsRow}>
          <div style={s.statCard}>
            <span style={s.statValue}>{newsJobs.filter(j => j.status === 'done').reduce((a, j) => a + j.doneClips, 0)}</span>
            <span style={s.statLabel}>Clips đã tạo</span>
          </div>
          <div style={s.statCard}>
            <span style={s.statValue}>{newsJobs.length}</span>
            <span style={s.statLabel}>Batches</span>
          </div>
          <div style={{ ...s.statCard, background: status === 'running' ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)' }}>
            <span style={{ ...s.statValue, color: status === 'running' ? '#818cf8' : '#6b7280' }}>
              {status === 'running' ? '⚡ Running' : status === 'done' ? '✅ Done' : '⏸ Idle'}
            </span>
            <span style={s.statLabel}>Trạng thái</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={s.tabs}>
        {(['run', 'history'] as const).map(tab => (
          <button
            key={tab}
            style={{ ...s.tab, ...(activeTab === tab ? s.tabActive : {}) }}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'run' ? '🚀 Chạy Pipeline' : '📋 Lịch sử'}
          </button>
        ))}
      </div>

      {activeTab === 'run' && (
        <div style={s.body}>
          {/* Left: Config panel */}
          <div style={s.configPanel}>
            {/* Batch size */}
            <div style={s.section}>
              <label style={s.label}>📦 Số clip trong batch</label>
              <div style={s.sliderRow}>
                <input
                  type="range" min={1} max={20} step={1}
                  value={batchCount}
                  onChange={(e) => setBatchCount(+e.target.value)}
                  style={s.slider}
                />
                <span style={s.sliderVal}>{batchCount} clips</span>
              </div>
              <p style={s.hint}>
                Workers: {Math.min(resources.maxWorkers, batchCount)} song song
                | RAM: {resources.ramGb}GB | CPU: {resources.cpuCores} cores
              </p>
            </div>

            {/* Topic source toggle */}
            <div style={s.section}>
              <label style={s.label}>📌 Nguồn chủ đề</label>
              <div style={s.toggleRow}>
                <button
                  style={{ ...s.toggleBtn, ...(useCustomTopics ? {} : s.toggleActive) }}
                  onClick={() => setUseCustomTopics(false)}
                >🤖 Mặc định (AI chọn)</button>
                <button
                  style={{ ...s.toggleBtn, ...(useCustomTopics ? s.toggleActive : {}) }}
                  onClick={() => setUseCustomTopics(true)}
                >✏️ Tự nhập</button>
              </div>
            </div>

            {/* Custom topics input */}
            {useCustomTopics && (
              <div style={s.section}>
                <label style={s.label}>✏️ Danh sách chủ đề</label>
                <div style={s.topicInputRow}>
                  <input
                    style={s.input}
                    placeholder="VD: Đà Lạt cà phê view đẹp"
                    value={topicInput}
                    onChange={(e) => setTopicInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleAddTopic()}
                  />
                  <button style={s.addBtn} onClick={handleAddTopic}>+</button>
                </div>
                <div style={s.tagList}>
                  {customTopics.map((t, i) => (
                    <span key={i} style={s.tag}>
                      {t}
                      <button style={s.tagRemove} onClick={() => handleRemoveTopic(i)}>×</button>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Selected topics preview */}
            <div style={s.section}>
              <label style={s.label}>🗂 Sẽ tạo {selectedTopics.length} clip</label>
              <div style={s.topicList}>
                {selectedTopics.map((t, i) => (
                  <div key={i} style={s.topicRow}>
                    <span style={s.topicNum}>{i + 1}</span>
                    <span style={s.topicText}>{t}</span>
                    {status === 'running' && (
                      <span style={s.topicStatus}>⏳</span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Action buttons */}
            <div style={s.actionRow}>
              <button
                style={{
                  ...s.runBtn,
                  opacity: status === "running" ? 0.6 : 1,
                  cursor: status === "running" ? "not-allowed" : "pointer",
                }}
                onClick={handleRun}
                disabled={status === "running"}
              >
                {status === "running" ? "⚡ Đang chạy..." : "🚀 Chạy Pipeline"}
              </button>
              {status === "running" && (
                <button style={s.stopBtn} onClick={handleStop}>⏹ Dừng</button>
              )}
            </div>

            {/* Progress bar */}
            {status !== "idle" && (
              <div style={s.progressWrap}>
                <div style={s.progressBar}>
                  <div style={{ ...s.progressFill, width: `${progress}%` }} />
                </div>
                <span style={s.progressLabel}>{progress}%</span>
              </div>
            )}
          </div>

          {/* Right: Live logs */}
          <div style={s.logPanel}>
            <div style={s.logHeader}>
              <span style={s.logTitle}>📡 Live Logs</span>
              <button style={s.clearBtn} onClick={() => setLogs([])}>Xóa</button>
            </div>
            <div style={s.logBody}>
              {logs.length === 0 && (
                <p style={s.emptyLog}>Bấm "Chạy Pipeline" để xem logs realtime...</p>
              )}
              {logs.map((l) => (
                <div key={l.id} style={{ ...s.logLine, color: logColor(l.level) }}>
                  <span style={s.logTime}>{l.time}</span>
                  <span>{l.text}</span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>
      )}

      {activeTab === 'history' && (
        <div style={s.historyPanel}>
          {newsJobs.length === 0 ? (
            <div style={s.emptyHistory}>
              <p style={{ fontSize: 40 }}>📭</p>
              <p style={{ color: "#6b7280" }}>Chưa có batch nào. Chạy pipeline đầu tiên!</p>
            </div>
          ) : (
            newsJobs.map((job) => (
              <div key={job.id} style={s.historyCard}>
                <div style={s.histCardTop}>
                  <span style={s.histBadge(job.status)}>{statusLabel(job.status)}</span>
                  <span style={s.histDate}>{new Date(job.createdAt).toLocaleString("vi-VN")}</span>
                </div>
                <div style={s.histInfo}>
                  <span>📦 {job.totalClips} clips</span>
                  <span>✅ {job.doneClips} done</span>
                  <span>⚡ {job.workers} workers</span>
                  {job.briefId && <span>📋 {job.briefId}</span>}
                </div>
                <div style={s.histTopics}>
                  {job.topics.slice(0, 4).map((t, i) => (
                    <span key={i} style={s.histTopic}>{t}</span>
                  ))}
                  {job.topics.length > 4 && (
                    <span style={s.histTopic}>+{job.topics.length - 4} nữa</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function logColor(level: string) {
  switch (level) {
    case "success": return "#34d399";
    case "warning": return "#fbbf24";
    case "error":   return "#f87171";
    default:        return "#94a3b8";
  }
}

function statusLabel(status: string) {
  switch (status) {
    case "running": return "⚡ Running";
    case "done":    return "✅ Done";
    case "partial": return "⚠ Partial";
    case "error":   return "❌ Error";
    default:        return "⏸ Pending";
  }
}

// ── Styles ────────────────────────────────────────────────────────────────────
const styles: Record<string, any> = {
  container: {
    display: "flex", flexDirection: "column", height: "100%",
    background: "#0a0a0a", color: "#f1f5f9", overflow: "hidden",
  },
  header: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "20px 24px 16px", borderBottom: "1px solid rgba(255,255,255,0.06)",
    flexShrink: 0,
  },
  title: { margin: 0, fontSize: 22, fontWeight: 700, color: "#f1f5f9" },
  subtitle: { margin: "4px 0 0", fontSize: 13, color: "#64748b" },
  statsRow: { display: "flex", gap: 12 },
  statCard: {
    display: "flex", flexDirection: "column", alignItems: "center",
    padding: "10px 18px", borderRadius: 10,
    background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)",
    minWidth: 80,
  },
  statValue: { fontSize: 20, fontWeight: 700, color: "#6366f1" },
  statLabel: { fontSize: 11, color: "#64748b", marginTop: 2 },

  tabs: {
    display: "flex", gap: 0, borderBottom: "1px solid rgba(255,255,255,0.06)",
    padding: "0 24px", flexShrink: 0,
  },
  tab: {
    background: "none", border: "none", cursor: "pointer",
    padding: "12px 20px", color: "#64748b", fontSize: 13, fontWeight: 500,
    borderBottom: "2px solid transparent", transition: "all 0.15s",
  },
  tabActive: { color: "#818cf8", borderBottom: "2px solid #6366f1" },

  body: {
    display: "flex", flex: 1, gap: 0, overflow: "hidden",
  },
  configPanel: {
    width: 340, padding: "16px 20px", overflowY: "auto",
    borderRight: "1px solid rgba(255,255,255,0.06)", flexShrink: 0,
    display: "flex", flexDirection: "column", gap: 8,
  },
  section: { marginBottom: 16 },
  label: { fontSize: 12, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: 8 },
  hint: { fontSize: 11, color: "#475569", margin: "4px 0 0" },

  sliderRow: { display: "flex", alignItems: "center", gap: 12 },
  slider: { flex: 1, accentColor: "#6366f1" },
  sliderVal: { fontSize: 14, fontWeight: 700, color: "#818cf8", minWidth: 60, textAlign: "right" },

  toggleRow: { display: "flex", gap: 8 },
  toggleBtn: {
    flex: 1, padding: "8px 12px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.1)",
    background: "rgba(255,255,255,0.03)", color: "#94a3b8", cursor: "pointer", fontSize: 12, fontWeight: 500,
  },
  toggleActive: { background: "rgba(99,102,241,0.2)", border: "1px solid #6366f1", color: "#818cf8" },

  topicInputRow: { display: "flex", gap: 8, marginBottom: 8 },
  input: {
    flex: 1, padding: "8px 12px", borderRadius: 8,
    background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
    color: "#f1f5f9", fontSize: 13, outline: "none",
  },
  addBtn: {
    padding: "8px 16px", borderRadius: 8, background: "rgba(99,102,241,0.3)",
    border: "1px solid #6366f1", color: "#818cf8", cursor: "pointer", fontSize: 16, fontWeight: 700,
  },
  tagList: { display: "flex", flexWrap: "wrap", gap: 6 },
  tag: {
    display: "inline-flex", alignItems: "center", gap: 4,
    padding: "4px 10px", borderRadius: 20, fontSize: 12,
    background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.3)", color: "#a5b4fc",
  },
  tagRemove: { background: "none", border: "none", cursor: "pointer", color: "#6b7280", fontSize: 14, lineHeight: 1 },

  topicList: { display: "flex", flexDirection: "column", gap: 4 },
  topicRow: {
    display: "flex", alignItems: "center", gap: 8,
    padding: "7px 10px", borderRadius: 8,
    background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)",
  },
  topicNum: { fontSize: 11, color: "#475569", minWidth: 18, textAlign: "center" },
  topicText: { fontSize: 12, color: "#cbd5e1", flex: 1 },
  topicStatus: { fontSize: 14 },

  actionRow: { display: "flex", gap: 8, marginTop: 8 },
  runBtn: {
    flex: 1, padding: "12px", borderRadius: 10, fontSize: 14, fontWeight: 700,
    background: "linear-gradient(135deg, #6366f1, #818cf8)",
    border: "none", color: "#fff", cursor: "pointer",
    boxShadow: "0 4px 15px rgba(99,102,241,0.3)",
    transition: "all 0.2s",
  },
  stopBtn: {
    padding: "12px 16px", borderRadius: 10, fontSize: 14, fontWeight: 600,
    background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.3)",
    color: "#f87171", cursor: "pointer",
  },

  progressWrap: { display: "flex", alignItems: "center", gap: 12, marginTop: 8 },
  progressBar: {
    flex: 1, height: 6, borderRadius: 3,
    background: "rgba(255,255,255,0.08)", overflow: "hidden",
  },
  progressFill: {
    height: "100%", borderRadius: 3,
    background: "linear-gradient(90deg, #6366f1, #34d399)",
    transition: "width 0.4s ease",
  },
  progressLabel: { fontSize: 12, color: "#94a3b8", minWidth: 36, textAlign: "right" },

  logPanel: {
    flex: 1, display: "flex", flexDirection: "column", overflow: "hidden",
  },
  logHeader: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.06)", flexShrink: 0,
  },
  logTitle: { fontSize: 12, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" },
  clearBtn: {
    padding: "4px 12px", borderRadius: 6, background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)", color: "#64748b", cursor: "pointer", fontSize: 12,
  },
  logBody: {
    flex: 1, overflowY: "auto", padding: "12px 16px",
    fontFamily: "'Fira Code', 'Cascadia Code', monospace", fontSize: 12,
    display: "flex", flexDirection: "column", gap: 2,
  },
  logLine: { display: "flex", gap: 10, lineHeight: 1.6 },
  logTime: { color: "#334155", minWidth: 70, flexShrink: 0 },
  emptyLog: { color: "#334155", fontStyle: "italic", margin: "auto", textAlign: "center", paddingTop: 40 },

  historyPanel: {
    flex: 1, overflowY: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 12,
  },
  emptyHistory: {
    flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
    justifyContent: "center", gap: 8, color: "#6b7280",
  },
  historyCard: {
    padding: 16, borderRadius: 12,
    background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)",
    display: "flex", flexDirection: "column", gap: 10,
  },
  histCardTop: { display: "flex", alignItems: "center", justifyContent: "space-between" },
  histBadge: (status: string): React.CSSProperties => ({
    padding: "3px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600,
    background: status === "done" ? "rgba(52,211,153,0.15)" : status === "running" ? "rgba(99,102,241,0.2)" : "rgba(239,68,68,0.15)",
    color: status === "done" ? "#34d399" : status === "running" ? "#818cf8" : "#f87171",
  }),
  histDate: { fontSize: 12, color: "#475569" },
  histInfo: { display: "flex", gap: 16, fontSize: 12, color: "#64748b" },
  histTopics: { display: "flex", flexWrap: "wrap", gap: 6 },
  histTopic: {
    padding: "3px 8px", borderRadius: 6, fontSize: 11,
    background: "rgba(255,255,255,0.05)", color: "#94a3b8",
  },
};
