import React, { useState, useEffect, useRef } from "react";
import { useAppStore } from "../stores/appStore";

// ── Types ──────────────────────────────────────────────────────────────────
interface Creator {
  id: string;
  emoji: string;
  name: string;
  specialty: string;
}

interface Template {
  id: string;
  ratio: string;
  label: string;
  desc: string;
  icon: string;
}

interface SeedingItem {
  id: string;
  value: string;
  type: "restaurant" | "hotel";
}

interface SceneSpec {
  scene_id: string;
  description: string;
  min_duration_sec: number;
  type: "clip" | "image";
  uploaded: boolean;
  file_path: string | null;      // Absolute path (Tauri mode)
  file_object?: File | null;     // Actual File object (browser mode)
  file_name?: string | null;     // Display name
}

interface CustomSceneDraft {
  id: string;
  description: string;
  min_duration_sec: number;
  type: "clip" | "image";
}

interface ScriptResult {
  hook: string;
  body: string;
  cta: string;
}

interface PipelineResult {
  script: ScriptResult;
  captions: {
    caption_short: string;
    caption_long: string;
    hashtags: string[];
  };
  imagePrompts: string[];
  videoPath: string;
  audioPath: string;
}

interface LogLine {
  id: string;
  time: string;
  type: "info" | "success" | "warn" | "error";
  text: string;
}

type Step = 1 | 2 | 3 | 4 | 5 | 6;
type SceneMode = "ai" | "preset" | "custom";
type VoiceMode = "edge" | "api" | "mock";

// ── Constants ──────────────────────────────────────────────────────────────
const CREATORS: Creator[] = [
  { id: "c1", emoji: "👩‍🦱", name: "Lan Anh", specialty: "Ẩm thực & Du lịch" },
  { id: "c2", emoji: "🧑‍💻", name: "Minh Tuấn", specialty: "Phượt & Khám phá" },
  { id: "c3", emoji: "👩‍🎤", name: "Thu Hà", specialty: "Resort & Nghỉ dưỡng" },
  { id: "c4", emoji: "🧔", name: "Đức Anh", specialty: "Backpacker" },
  { id: "c5", emoji: "👩‍🌾", name: "Ngọc Mai", specialty: "Làng quê & Bản địa" },
];

const TEMPLATES: Template[] = [
  { id: "9:16", ratio: "9:16", label: "TikTok / Reels", desc: "Dọc — phù hợp mobile", icon: "📱" },
  { id: "1:1",  ratio: "1:1",  label: "Vuông",          desc: "Instagram feed",        icon: "⬜" },
  { id: "16:9", ratio: "16:9", label: "YouTube",         desc: "Ngang — màn hình rộng", icon: "🖥️" },
];

const TRANSITION_OPTIONS = [
  { value: "fade",       label: "Fade — Mờ dần" },
  { value: "dissolve",   label: "Dissolve — Tan biến" },
  { value: "wipeleft",   label: "Wipe Left — Quét trái" },
  { value: "slideright", label: "Slide Right — Trượt phải" },
  { value: "circleopen", label: "Circle Open — Mở vòng tròn" },
];

const PRESET_SCENE_COUNTS: Record<string, number[]> = {
  "9:16":  [3, 4, 5],
  "1:1":   [2, 3, 4],
  "16:9":  [4, 5, 6, 7],
};

const SCRIPT_STAGES = ["Phân tích chủ đề", "Viết kịch bản", "Tạo scene plan", "Hoàn tất"];

// ── Helper: generate mock scene plan ──────────────────────────────────────
function generateMockScenes(
  topic: string,
  ratio: string,
  mode: SceneMode,
  count: number,
  custom: CustomSceneDraft[]
): SceneSpec[] {
  if (mode === "custom" && custom.length > 0) {
    return custom.map((c, i) => ({
      scene_id: `scene_${i + 1}`,
      description: c.description || `Scene ${i + 1}`,
      min_duration_sec: c.min_duration_sec,
      type: c.type,
      uploaded: false,
      file_path: null,
    }));
  }

  const presets: Record<string, SceneSpec[]> = {
    "9:16": [
      { scene_id: "scene_1", description: `Cảnh mở đầu hook — toàn cảnh ${topic} gây tò mò`, min_duration_sec: 5, type: "clip", uploaded: false, file_path: null },
      { scene_id: "scene_2", description: `Giới thiệu ${topic} — cảnh đẹp đặc trưng nổi bật`, min_duration_sec: 12, type: "clip", uploaded: false, file_path: null },
      { scene_id: "scene_3", description: `Trải nghiệm tại ${topic} — ẩm thực, hoạt động`, min_duration_sec: 18, type: "clip", uploaded: false, file_path: null },
      { scene_id: "scene_4", description: `Kết thúc CTA — cảnh đẹp nhất kèm thông tin`, min_duration_sec: 10, type: "clip", uploaded: false, file_path: null },
      { scene_id: "scene_5", description: `Khám phá thêm góc ít ai biết của ${topic}`, min_duration_sec: 10, type: "clip", uploaded: false, file_path: null },
    ],
    "1:1": [
      { scene_id: "scene_1", description: `Hook ngắn — khoảnh khắc đặc sắc nhất tại ${topic}`, min_duration_sec: 5, type: "clip", uploaded: false, file_path: null },
      { scene_id: "scene_2", description: `Điểm nhấn — trải nghiệm nổi bật nhất`, min_duration_sec: 15, type: "clip", uploaded: false, file_path: null },
      { scene_id: "scene_3", description: `Kết thúc — thông tin creator`, min_duration_sec: 8, type: "clip", uploaded: false, file_path: null },
      { scene_id: "scene_4", description: `Cảnh bổ sung ${topic} — góc nhìn đặc biệt`, min_duration_sec: 8, type: "clip", uploaded: false, file_path: null },
    ],
    "16:9": [
      { scene_id: "scene_1", description: `Intro hook — teaser cảnh đẹp nhất ${topic}`, min_duration_sec: 8, type: "clip", uploaded: false, file_path: null },
      { scene_id: "scene_2", description: `Tổng quan điểm đến — drone shot hoặc cảnh rộng`, min_duration_sec: 15, type: "clip", uploaded: false, file_path: null },
      { scene_id: "scene_3", description: `Ẩm thực đặc sản — cận cảnh món ăn địa phương`, min_duration_sec: 20, type: "clip", uploaded: false, file_path: null },
      { scene_id: "scene_4", description: `Hoạt động vui chơi — cảnh đặc trưng ${topic}`, min_duration_sec: 20, type: "clip", uploaded: false, file_path: null },
      { scene_id: "scene_5", description: `Lưu trú — không gian khách sạn, resort`, min_duration_sec: 15, type: "clip", uploaded: false, file_path: null },
      { scene_id: "scene_6", description: `Outro & CTA — highlight tổng hợp`, min_duration_sec: 12, type: "clip", uploaded: false, file_path: null },
      { scene_id: "scene_7", description: `Cảnh bonus — hậu trường hoặc góc ít người biết`, min_duration_sec: 10, type: "clip", uploaded: false, file_path: null },
    ],
  };

  const base = presets[ratio] ?? presets["9:16"];
  const n = count > 0 ? Math.min(count, base.length) : base.length;
  return base.slice(0, n);
}

function generateMockScript(topic: string, creatorName: string): ScriptResult {
  return {
    hook: `Bạn đã biết ${topic} có điều này chưa? 😱 Mình shock thật sự khi lần đầu đến đây!`,
    body: `Hôm nay ${creatorName} sẽ review toàn bộ hành trình khám phá ${topic} — từ chỗ ăn, chỗ ngủ cho đến những góc chụp cực đẹp. Đây là nơi mình ở 3 ngày 2 đêm và thật sự không muốn về. Thức ăn ngon, người dân thân thiện, phong cảnh thì miễn chê!`,
    cta: `Follow để không bỏ lỡ series du lịch ${topic} nhé! Link đặt phòng trong bio 👇`,
  };
}

// ── Log Console Component ──────────────────────────────────────────────────
function LogConsole({ logs }: { logs: LogLine[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [logs.length]);
  const logColor = (t: LogLine["type"]) => {
    if (t === "success") return "#10b981";
    if (t === "warn")    return "#f59e0b";
    if (t === "error")   return "#ef4444";
    return "#9ca3af";
  };
  return (
    <div style={sty.logConsole}>
      <div style={sty.logHeader}>
        <span style={sty.logTitle}>📟 Live Logs</span>
        <span style={sty.logCount}>{logs.length} dòng</span>
      </div>
      <div style={sty.logBody}>
        {logs.map((l) => (
          <div key={l.id} style={{ ...sty.logLine, color: logColor(l.type) }}>
            <span style={sty.logTime}>{l.time}</span>
            <span style={sty.logText}>{l.text}</span>
          </div>
        ))}
        {logs.length === 0 && <div style={{ color: "#4b5563", fontSize: 12, padding: "10px 0" }}>Chưa có logs...</div>}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ── Step Indicator ─────────────────────────────────────────────────────────
function StepIndicator({ current }: { current: Step }) {
  const steps = [
    { num: 1, label: "Cấu hình" },
    { num: 2, label: "AI viết kịch bản" },
    { num: 3, label: "Upload Scene" },
    { num: 4, label: "Ghép video" },
    { num: 5, label: "Kết quả" },
    { num: 6, label: "Đồng bộ" },
  ];
  return (
    <div style={sty.stepBar}>
      {steps.map((s, idx) => (
        <React.Fragment key={s.num}>
          <div style={sty.stepItem}>
            <div style={{
              ...sty.stepCircle,
              background: current === s.num ? "linear-gradient(135deg,#6366f1,#38bdf8)" : current > s.num ? "#10b981" : "#2a2a2a",
              color: current >= s.num ? "#fff" : "#6b7280",
              boxShadow: current === s.num ? "0 0 12px rgba(99,102,241,0.5)" : "none",
            }}>
              {current > s.num ? "✓" : s.num}
            </div>
            <span style={{ ...sty.stepLabel, color: current === s.num ? "#a78bfa" : current > s.num ? "#10b981" : "#4b5563" }}>
              {s.label}
            </span>
          </div>
          {idx < steps.length - 1 && (
            <div style={{ ...sty.stepLine, background: current > s.num ? "#10b981" : "#252525" }} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// ── Pulsing Dots ───────────────────────────────────────────────────────────
function PulsingDots() {
  return (
    <span style={{ display: "inline-flex", gap: 3, marginLeft: 6 }}>
      {[0, 1, 2].map((i) => (
        <span key={i} style={{
          width: 5, height: 5, borderRadius: "50%", background: "#6366f1",
          display: "inline-block",
          animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
        }} />
      ))}
    </span>
  );
}

// ── File Path Row ──────────────────────────────────────────────────────────
function FilePathRow({ icon, label, path, ext }: { icon: string; label: string; path: string; ext: string }) {
  const [copied, setCopied] = React.useState(false);
  const [opening, setOpening] = React.useState(false);
  const [openError, setOpenError] = React.useState("");

  const handleOpenFolder = async () => {
    if (!path) return;
    setOpening(true);
    setOpenError("");

    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;

    if (isTauri) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("show_in_folder", { path });
      } catch (err) {
        setOpenError("Tauri error: " + String(err));
      }
    } else {
      // Browser mode: ask Python server to open Explorer
      try {
        const res = await fetch("http://localhost:7788/open-folder", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path }),
        });
        if (!res.ok) {
          const t = await res.text();
          setOpenError(`Server lỗi: ${t}`);
        }
      } catch (err: any) {
        if (err.message?.includes("fetch") || err.message?.includes("Failed")) {
          setOpenError("Server chưa chạy. Khởi động: python server.py");
        } else {
          setOpenError(String(err));
        }
      }
    }
    setOpening(false);
  };

  const handleCopyPath = () => {
    if (!path) return;
    navigator.clipboard?.writeText(path).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleDownload = async () => {
    // In browser mode: request a download URL from the server
    if (!path) return;
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    if (isTauri) {
      handleOpenFolder(); // In desktop mode, just open the folder
      return;
    }
    try {
      const res = await fetch("http://localhost:7788/download-file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      if (res.ok) {
        const blob = await res.blob();
        const fileName = path.split("\\").pop() || path.split("/").pop() || "video.mp4";
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = fileName;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        setOpenError("Không thể tải file từ server");
      }
    } catch {
      setOpenError("Server chưa chạy. Dùng nút 📋 để copy đường dẫn.");
    }
  };

  return (
    <div>
      <div style={sty.fileRow}>
        <span style={sty.fileIcon}>{icon}</span>
        <div style={sty.fileInfo}>
          <div style={sty.fileLabel}>{label}</div>
          <div style={sty.filePath} title={path}>{path || "—"}</div>
        </div>
        <span style={sty.fileExt}>{ext}</span>

        {/* Copy path */}
        <button
          style={{ ...sty.openFolderBtn, fontSize: 13 }}
          title="Copy đường dẫn"
          onClick={handleCopyPath}
        >
          {copied ? "✓" : "📋"}
        </button>

        {/* Download file (browser) / Open folder (Tauri) */}
        <button
          style={{ ...sty.openFolderBtn, fontSize: 13, opacity: opening ? 0.5 : 1 }}
          title="Tải file về"
          onClick={handleDownload}
          disabled={opening}
        >
          ⬇️
        </button>

        {/* Open Explorer */}
        <button
          style={{ ...sty.openFolderBtn, fontSize: 16, opacity: opening ? 0.5 : 1 }}
          title="Mở thư mục chứa file"
          onClick={handleOpenFolder}
          disabled={opening}
        >
          {opening ? "⏳" : "📂"}
        </button>
      </div>
      {openError && (
        <div style={{
          fontSize: 11, color: "#f59e0b", background: "rgba(245,158,11,0.08)",
          border: "1px solid #f59e0b30", borderRadius: 8, padding: "6px 12px",
          marginTop: 4, display: "flex", alignItems: "center", gap: 6,
        }}>
          ⚠️ {openError}
        </div>
      )}
    </div>
  );
}


// ── MAIN COMPONENT ─────────────────────────────────────────────────────────
export default function StudioScreen() {
  const [step, setStep] = useState<Step>(1);

  // ─ Step 1: Basic config ─
  const [topic, setTopic] = useState("");
  const [selectedCreator, setSelectedCreator] = useState("c1");
  const [selectedTemplate, setSelectedTemplate] = useState("9:16");
  const [voiceMode, setVoiceMode] = useState<VoiceMode>("edge");
  const [hookStyle, setHookStyle] = useState("zoom_in");
  const [hookText, setHookText] = useState("");
  const [scriptText, setScriptText] = useState("");
  const [transition, setTransition] = useState("fade");
  const [seedingItems, setSeedingItems] = useState<SeedingItem[]>([
    { id: "s1", value: "", type: "restaurant" },
  ]);

  // ─ Step 1: Scene Config ─
  const [sceneMode, setSceneMode] = useState<SceneMode>("ai");
  const [presetSceneCount, setPresetSceneCount] = useState(0); // 0 = use default for ratio
  const [customScenes, setCustomScenes] = useState<CustomSceneDraft[]>([
    { id: "cs1", description: "", min_duration_sec: 10, type: "clip" },
  ]);

  // ─ Step 2: Script generation ─
  const [scriptLogs, setScriptLogs] = useState<LogLine[]>([]);
  const [scriptStep, setScriptStep] = useState(0);
  const [generatedScript, setGeneratedScript] = useState<ScriptResult | null>(null);
  const [jobId, setJobId] = useState("");

  // ─ Step 3: Scene upload ─
  const [scenes, setScenes] = useState<SceneSpec[]>([]);
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  // ─ Step 4: Assembly ─
  const [assemblyLogs, setAssemblyLogs] = useState<LogLine[]>([]);
  const [assemblyStep, setAssemblyStep] = useState(0);
  const [isCancelled, setIsCancelled] = useState(false);
  const cancelRef = useRef(false);

  // ─ Step 5: Result ─
  const [result, setResult] = useState<PipelineResult | null>(null);

  // ─ Step 6: Sync ─
  const [syncStatus, setSyncStatus] = useState<"loading" | "ok" | "error" | null>(null);
  const [syncedUrl, setSyncedUrl] = useState("");

  // Fetch creator hook preference
  useEffect(() => { fetchCreatorSettings(selectedCreator); }, [selectedCreator]);

  const fetchCreatorSettings = async (cid: string) => {
    const idMap: Record<string, string> = { c1: "lan_anh", c2: "minh_tuan", c3: "thu_ha", c4: "duc_anh", c5: "ngoc_mai" };
    const mappedId = idMap[cid] || cid;
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    if (!isTauri) return;
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const resStr = await invoke<string>("get_creators");
      const res = JSON.parse(resStr);
      if (res.success && Array.isArray(res.data)) {
        const creator = res.data.find((c: any) => c.id === mappedId);
        if (creator?.hook_preference) setHookStyle(creator.hook_preference);
      }
    } catch (e) { /* silent */ }
  };

  // ── Seeding helpers ──
  const addSeeding = () => setSeedingItems((p) => [...p, { id: `s${Date.now()}`, value: "", type: "restaurant" }]);
  const removeSeeding = (id: string) => setSeedingItems((p) => p.filter((i) => i.id !== id));
  const updateSeeding = (id: string, field: keyof SeedingItem, val: string) =>
    setSeedingItems((p) => p.map((i) => (i.id === id ? { ...i, [field]: val } : i)));

  // ── Custom scene helpers ──
  const addCustomScene = () => setCustomScenes((p) => [...p, { id: `cs${Date.now()}`, description: "", min_duration_sec: 10, type: "clip" }]);
  const removeCustomScene = (id: string) => setCustomScenes((p) => p.filter((s) => s.id !== id));
  const updateCustomScene = (id: string, field: keyof CustomSceneDraft, val: any) =>
    setCustomScenes((p) => p.map((s) => (s.id === id ? { ...s, [field]: val } : s)));

  // ── Stage 1: AI generates script + scene plan ──
  const runResearchAndScript = async () => {
    if (!topic.trim()) return;
    cancelRef.current = false;
    setIsCancelled(false);
    setScriptLogs([]);
    setScriptStep(0);
    setStep(2);

    const newJobId = `job_${Date.now()}`;
    setJobId(newJobId);

    const idMap: Record<string, string> = { c1: "lan_anh", c2: "minh_tuan", c3: "thu_ha", c4: "duc_anh", c5: "ngoc_mai" };
    const mappedCreatorId = idMap[selectedCreator] || selectedCreator;
    const creatorName = CREATORS.find((c) => c.id === selectedCreator)?.name || "Creator";

    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;

    const addLog = (type: LogLine["type"], text: string) =>
      setScriptLogs((prev) => [...prev, {
        id: Math.random().toString(), time: new Date().toLocaleTimeString("vi-VN"), type, text
      }]);

    if (isTauri) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const { listen } = await import("@tauri-apps/api/event");

        const unlisten = await listen<any>("pipeline-log", (event) => {
          const p = event.payload;
          const type = p.level === "warning" ? "warn" : p.level as LogLine["type"];
          setScriptLogs((prev) => [...prev, { id: Math.random().toString(), time: p.time, type, text: p.text }]);
          const t = p.text;
          if (t.includes("[Stage 1]") || t.includes("[Script]")) setScriptStep(1);
          if (t.includes("kịch bản")) setScriptStep(2);
          if (t.includes("[Scenes]")) setScriptStep(3);
          if (t.includes("scene")) setScriptStep(4);
        });

        const customScenesJson = sceneMode === "custom"
          ? JSON.stringify(customScenes.map(s => ({ description: s.description, min_duration_sec: s.min_duration_sec, type: s.type })))
          : "[]";

        const resultStr = await invoke<string>("generate_scene_plan", {
          jobId: newJobId,
          creatorId: mappedCreatorId,
          scriptText: scriptText || topic,
          sceneMode,
          templateRatio: selectedTemplate,
          sceneCount: presetSceneCount,
          hookStyle,
          hookText: hookText || "",
          voiceProvider: voiceMode === "api" ? "" : voiceMode,
          customScenesJson,
        });

        unlisten();

        const res = JSON.parse(resultStr);
        if (res.success && res.data) {
          const data = res.data;
          setGeneratedScript(data.script);
          setScenes(data.scenes || []);
          setScriptStep(4);
          setStep(3);
        } else {
          addLog("error", `Lỗi: ${res.data}`);
        }
      } catch (err: any) {
        addLog("error", `❌ Lỗi: ${err.message || err}`);
      }
    } else {
      // ── Mock fallback ──
      const mockSteps = [
        { type: "info" as const,    text: `[Stage 1] Bắt đầu Research & Script cho Creator: ${mappedCreatorId}` },
        { type: "info" as const,    text: `[Script] Nhận diện đầu vào là chủ đề: '${topic}'...` },
        { type: "info" as const,    text: "[Script] Không có Anthropic API key — Dùng mock script." },
        { type: "success" as const, text: `[Script] ✓ Kịch bản hoàn thiện — Hook: 'Bạn đã biết ${topic} có điều này chưa?...'` },
        { type: "info" as const,    text: `[Scenes] Đang tạo kịch bản scene (mode=${sceneMode}, ratio=${selectedTemplate})...` },
        { type: "success" as const, text: `[Scenes] ✓ Đã tạo scene plan thành công. Đang chờ user upload media...` },
      ];

      for (let i = 0; i < mockSteps.length; i++) {
        if (cancelRef.current) { setIsCancelled(true); return; }
        await new Promise((r) => setTimeout(r, 400 + Math.random() * 300));
        addLog(mockSteps[i].type, mockSteps[i].text);
        setScriptStep(Math.floor((i / mockSteps.length) * 4) + 1);
      }

      const mockScript = generateMockScript(topic, creatorName);
      const mockScenes = generateMockScenes(topic, selectedTemplate, sceneMode, presetSceneCount, customScenes);

      setGeneratedScript(mockScript);
      setScenes(mockScenes);
      setScriptStep(4);
      await new Promise((r) => setTimeout(r, 300));
      setStep(3);
    }
  };

  // ── Pick file for a specific scene ──
  const handlePickSceneFile = (sceneId: string) => {
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;

    if (isTauri) {
      // Tauri: use native file dialog to get absolute path
      import("@tauri-apps/api/core").then(({ invoke }) => {
        invoke<string | null>("select_single_file", {
          allowedExtensions: ["mp4", "mkv", "avi", "mov", "webm", "jpg", "jpeg", "png", "gif"],
        }).then((file) => {
          if (file) {
            setScenes((prev) => prev.map((s) =>
              s.scene_id === sceneId
                ? { ...s, uploaded: true, file_path: file, file_name: file.split("\\").pop() || file.split("/").pop() || file }
                : s
            ));
          }
        }).catch(console.error);
      });
    } else {
      // Browser: trigger a real <input type="file"> — no fake paths
      const scene = scenes.find(s => s.scene_id === sceneId);
      const accept = scene?.type === "image"
        ? "image/jpeg,image/png,image/gif,image/webp"
        : "video/mp4,video/x-matroska,video/avi,video/quicktime,video/webm";

      const input = document.createElement("input");
      input.type = "file";
      input.accept = accept;
      input.onchange = (e) => {
        const file = (e.target as HTMLInputElement).files?.[0];
        if (file) {
          setScenes((prev) => prev.map((s) =>
            s.scene_id === sceneId
              ? { ...s, uploaded: true, file_path: null, file_object: file, file_name: file.name }
              : s
          ));
        }
      };
      input.click();
    }
  };

  const handleRemoveSceneFile = (sceneId: string) => {
    setScenes((prev) => prev.map((s) =>
      s.scene_id === sceneId ? { ...s, uploaded: false, file_path: null, file_object: null, file_name: null } : s
    ));
  };

  // Check cả file_path (Tauri mode) lẫn file_object (browser mode)
  const uploadedCount = scenes.filter((s) => s.uploaded && (s.file_path || s.file_object)).length;
  const allUploaded = scenes.length > 0 && uploadedCount === scenes.length;


  // ── Stage 2: Assemble video ──
  const runAssembleVideo = async (_skipMissing = false) => {
    cancelRef.current = false;
    setIsCancelled(false);
    setAssemblyLogs([]);
    setAssemblyStep(0);
    setStep(4);

    const creatorName = CREATORS.find((c) => c.id === selectedCreator)?.name || "Creator";
    const addLog = (type: LogLine["type"], text: string) =>
      setAssemblyLogs((prev) => [...prev, {
        id: Math.random().toString(), time: new Date().toLocaleTimeString("vi-VN"), type, text
      }]);

    const sceneUploads = scenes.map((s) => ({
      scene_id: s.scene_id,
      file_path: s.file_path || "",
    }));

    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;

    if (isTauri) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const { listen } = await import("@tauri-apps/api/event");

        const unlisten = await listen<any>("pipeline-log", (event) => {
          const p = event.payload;
          const type = p.level === "warning" ? "warn" : p.level as LogLine["type"];
          setAssemblyLogs((prev) => [...prev, { id: Math.random().toString(), time: p.time, type, text: p.text }]);
          const t = p.text;
          if (t.includes("[Voice]"))    setAssemblyStep(1);
          if (t.includes("[Subtitle]")) setAssemblyStep(2);
          if (t.includes("[Assembly]")) setAssemblyStep(3);
          if (t.includes("[FFmpeg]"))   setAssemblyStep(4);
          if (t.includes("✅"))         setAssemblyStep(5);
        });

        const resultStr = await invoke<string>("assemble_from_scenes", {
          jobId,
          sceneUploadsJson: JSON.stringify(sceneUploads),
          transition,
        });

        unlisten();

        const res = JSON.parse(resultStr);
        if (res.success && res.data) {
          const data = res.data;
          finishWithResult(data.video_path, data.audio_path, creatorName);
        } else {
          addLog("error", `Lỗi ghép video: ${res.data}`);
        }
      } catch (err: any) {
        addLog("error", `❌ Lỗi: ${err.message || err}`);
        setIsCancelled(true);
      }
    } else {
      // Browser mode: send real files to Python local server for actual FFmpeg processing
      addLog("info", "[Browser Mode] Đang chuẩn bị upload files lên Python server local...");
      setAssemblyStep(1);

      // Check if any scene has a real File object
      const hasRealFiles = scenes.some(s => s.file_object);
      if (!hasRealFiles && scenes.every(s => !s.file_path)) {
        addLog("error", "❌ Không có file nào được upload. Vui lòng chọn file video/ảnh cho từng scene trước.");
        setIsCancelled(true);
        return;
      }

      try {
        // Build FormData with real files + metadata
        const formData = new FormData();
        formData.append("job_id", jobId || `job_${Date.now()}`);
        formData.append("transition", transition);
        formData.append("voice_mode", voiceMode);
        formData.append("script", JSON.stringify(generatedScript || { hook: "", body: topic, cta: "" }));

        const idMap: Record<string, string> = { c1: "lan_anh", c2: "minh_tuan", c3: "thu_ha", c4: "duc_anh", c5: "ngoc_mai" };
        formData.append("creator_id", idMap[selectedCreator] || selectedCreator);
        formData.append("template_ratio", selectedTemplate);
        formData.append("hook_style", hookStyle);
        formData.append("hook_text", hookText || "");

        // Attach each scene's file
        const scenesMeta = scenes.map((s) => ({
          scene_id: s.scene_id,
          description: s.description,
          min_duration_sec: s.min_duration_sec,
          type: s.type,
          has_file: !!(s.file_object || s.file_path),
        }));
        formData.append("scenes_meta", JSON.stringify(scenesMeta));

        for (const s of scenes) {
          if (s.file_object) {
            formData.append(s.scene_id, s.file_object, s.file_object.name);
            addLog("info", `  📎 Scene [${s.scene_id}]: ${s.file_object.name} (${(s.file_object.size / 1024 / 1024).toFixed(1)}MB)`);
          } else if (s.file_path) {
            // Already a local path (shouldn't happen in browser mode, but handle gracefully)
            addLog("warn", `  ⚠ Scene [${s.scene_id}]: path-only, không thể upload trong browser mode`);
          } else {
            addLog("warn", `  ⚠ Scene [${s.scene_id}]: Không có file → sẽ dùng placeholder màu đen`);
          }
        }

        addLog("info", "[Server] Đang gửi lên Python server tại http://localhost:7788/assemble ...");
        setAssemblyStep(2);

        const response = await fetch("http://localhost:7788/assemble", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const errText = await response.text();
          throw new Error(`Server trả về lỗi ${response.status}: ${errText}`);
        }

        setAssemblyStep(3);
        addLog("info", "[Server] ✓ Upload thành công, đang chờ FFmpeg xử lý...");

        // Poll for progress / wait for result
        const result = await response.json();

        if (result.success && result.video_path) {
          setAssemblyStep(5);
          addLog("success", `[FFmpeg] ✅ Video hoàn chỉnh: ${result.video_path}`);
          finishWithResult(result.video_path, result.audio_path || "", creatorName);
        } else {
          throw new Error(result.error || "Server không trả về video path");
        }

      } catch (err: any) {
        const msg = err.message || String(err);
        if (msg.includes("fetch") || msg.includes("NetworkError") || msg.includes("Failed to fetch")) {
          addLog("error", "❌ Không thể kết nối đến Python server tại http://localhost:7788");
          addLog("warn",  "💡 Để ghép video thật, hãy khởi động Python server:");
          addLog("info",  "   cd dulich-pipeline");
          addLog("info",  "   python server.py");
          addLog("warn",  "💡 Hoặc build và chạy Desktop App (Tauri) để dùng FFmpeg trực tiếp.");
        } else {
          addLog("error", `❌ Lỗi ghép video: ${msg}`);
        }
        setIsCancelled(true);
      }
    }
  };

  const finishWithResult = (videoPath: string, audioPath: string, creatorName: string) => {
    const finalResult: PipelineResult = {
      script: generatedScript || { hook: "", body: "", cta: "" },
      captions: {
        caption_short: `Video cá nhân từ ${creatorName} 🌟`,
        caption_long: `Hành trình du lịch ${topic} được sản xuất bởi ${creatorName} với AI Voice và Scene Assembly.`,
        hashtags: ["#dulich", `#${topic.replace(/\s+/g, "")}`, "#travel", "#vietnam", "#review"],
      },
      imagePrompts: [],
      videoPath,
      audioPath,
    };
    setResult(finalResult);

    const addToLibrary = useAppStore.getState().addToLibrary;
    addToLibrary({
      id: `lib-${Date.now()}`, topic, creator: creatorName, status: "local",
      createdAt: new Date().toISOString(),
      result: {
        script: finalResult.script,
        captions: { hooks: [], caption_short: finalResult.captions.caption_short, caption_long: finalResult.captions.caption_long, hashtags: finalResult.captions.hashtags },
        images: { description: topic, prompts: [] },
        videoPath, audioPath,
      }
    });
    setStep(5);
  };

  const syncDashboard = async () => {
    setStep(6);
    setSyncStatus("loading");
    await new Promise((r) => setTimeout(r, 2000));
    const ok = Math.random() > 0.15;
    if (ok) { setSyncStatus("ok"); setSyncedUrl("http://localhost:3000/videos/abc123"); }
    else setSyncStatus("error");
  };

  const resetAll = () => {
    setStep(1); setTopic(""); setScriptLogs([]); setAssemblyLogs([]);
    setScriptStep(0); setAssemblyStep(0); setResult(null); setSyncStatus(null);
    setSyncedUrl(""); setIsCancelled(false); setScenes([]); setGeneratedScript(null); setJobId("");
  };

  // ══════════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════════
  return (
    <div style={sty.container}>
      <div style={sty.header}>
        <div>
          <h1 style={sty.title}>🎬 Studio</h1>
          <p style={sty.subtitle}>Sản xuất video du lịch bằng AI — Scene-based Assembly</p>
        </div>
      </div>

      <StepIndicator current={step} />

      {/* ════ STEP 1 ════ */}
      {step === 1 && (
        <div style={sty.card}>
          <h2 style={sty.cardTitle}>Bước 1 — Cấu hình sản xuất</h2>

          {/* Topic */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>🗺️ Chủ đề video <span style={sty.required}>*</span></label>
            <input
              style={sty.topicInput}
              placeholder="VD: Đà Nẵng travel, Phú Quốc resort, Hội An đêm…"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
            />
          </div>

          {/* Creator */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>👤 Chọn Creator</label>
            <div style={sty.creatorGrid}>
              {CREATORS.map((c) => (
                <div key={c.id} onClick={() => setSelectedCreator(c.id)}
                  style={{ ...sty.creatorCard, ...(selectedCreator === c.id ? sty.creatorCardActive : {}) }}>
                  <div style={sty.creatorEmoji}>{c.emoji}</div>
                  <div style={sty.creatorName}>{c.name}</div>
                  <div style={sty.creatorSpec}>{c.specialty}</div>
                  {selectedCreator === c.id && <div style={sty.creatorCheck}>✓</div>}
                </div>
              ))}
            </div>
          </div>

          {/* Template */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>📐 Định dạng video</label>
            <div style={sty.templateRow}>
              {TEMPLATES.map((t) => (
                <div key={t.id} onClick={() => { setSelectedTemplate(t.id); setPresetSceneCount(0); }}
                  style={{ ...sty.templateCard, ...(selectedTemplate === t.id ? sty.templateCardActive : {}) }}>
                  <span style={sty.templateIcon}>{t.icon}</span>
                  <div style={sty.templateRatio}>{t.ratio}</div>
                  <div style={sty.templateLabel}>{t.label}</div>
                  <div style={sty.templateDesc}>{t.desc}</div>
                </div>
              ))}
            </div>
          </div>

          {/* ═══ SCENE CONFIG ═══ */}
          <div style={{ ...sty.fieldGroup, ...sty.sceneConfigBox }}>
            <div style={sty.sceneConfigHeader}>
              <span style={sty.sceneConfigIcon}>🎞️</span>
              <div>
                <div style={sty.sceneConfigTitle}>Cấu hình Scene</div>
                <div style={sty.sceneConfigSub}>Chọn cách AI tạo các scene trong kịch bản video</div>
              </div>
            </div>

            {/* Mode tabs */}
            <div style={sty.sceneModeRow}>
              {[
                { key: "ai" as SceneMode,     label: "🤖 AI tự chọn",   desc: "AI phân tích kịch bản và tự quyết định số scene + mô tả phù hợp nhất" },
                { key: "preset" as SceneMode,  label: "📋 Chọn số scene", desc: "Bạn chọn số lượng scene, AI điền mô tả theo template chuẩn" },
                { key: "custom" as SceneMode,  label: "✏️ Tự nhập scene",  desc: "Bạn tự nhập tên và mô tả từng scene theo ý muốn" },
              ].map((opt) => (
                <div key={opt.key} onClick={() => setSceneMode(opt.key)}
                  style={{ ...sty.sceneModeCard, ...(sceneMode === opt.key ? sty.sceneModeCardActive : {}) }}>
                  <div style={sty.sceneModeBadge}>{opt.label}</div>
                  <div style={sty.sceneModeDesc}>{opt.desc}</div>
                  {sceneMode === opt.key && <div style={sty.sceneModeCheck}>✓</div>}
                </div>
              ))}
            </div>

            {/* Preset count picker */}
            {sceneMode === "preset" && (
              <div style={{ marginTop: 16 }}>
                <label style={sty.label}>Số scene</label>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" as const }}>
                  <div
                    onClick={() => setPresetSceneCount(0)}
                    style={{ ...sty.countChip, ...(presetSceneCount === 0 ? sty.countChipActive : {}) }}
                  >
                    Mặc định ({selectedTemplate === "9:16" ? "4" : selectedTemplate === "1:1" ? "3" : "6"})
                  </div>
                  {(PRESET_SCENE_COUNTS[selectedTemplate] || [3, 4, 5]).map((n) => (
                    <div key={n} onClick={() => setPresetSceneCount(n)}
                      style={{ ...sty.countChip, ...(presetSceneCount === n ? sty.countChipActive : {}) }}>
                      {n} scene
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Custom scene builder */}
            {sceneMode === "custom" && (
              <div style={{ marginTop: 16 }}>
                <label style={sty.label}>Danh sách scene của bạn</label>
                {customScenes.map((cs, i) => (
                  <div key={cs.id} style={sty.customSceneRow}>
                    <div style={sty.customSceneNum}>{i + 1}</div>
                    <input
                      style={{ ...sty.seedingInput, flex: 1 }}
                      placeholder={`Mô tả scene ${i + 1} (VD: Cảnh drone bay qua bãi biển lúc hoàng hôn)`}
                      value={cs.description}
                      onChange={(e) => updateCustomScene(cs.id, "description", e.target.value)}
                    />
                    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      <input
                        type="number"
                        min={3}
                        max={60}
                        style={{ ...sty.seedingInput, width: 64, textAlign: "center" as const }}
                        value={cs.min_duration_sec}
                        onChange={(e) => updateCustomScene(cs.id, "min_duration_sec", parseInt(e.target.value) || 5)}
                        title="Thời lượng tối thiểu (giây)"
                      />
                      <span style={{ fontSize: 11, color: "#6b7280", whiteSpace: "nowrap" as const }}>giây</span>
                    </div>
                    <select
                      style={{ ...sty.seedingType, fontSize: 12 }}
                      value={cs.type}
                      onChange={(e) => updateCustomScene(cs.id, "type", e.target.value)}
                    >
                      <option value="clip">🎥 Video</option>
                      <option value="image">🖼️ Ảnh</option>
                    </select>
                    <button style={sty.seedingRemove} onClick={() => removeCustomScene(cs.id)}
                      disabled={customScenes.length === 1}>✕</button>
                  </div>
                ))}
                <button style={sty.addSeedingBtn} onClick={addCustomScene}>
                  + Thêm scene
                </button>
                <div style={sty.hint}>Nhập thời lượng tối thiểu cho từng scene. User có thể upload clip dài hơn — vẫn sẽ ghép bình thường.</div>
              </div>
            )}
          </div>

          {/* Script Text */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>📝 Kịch bản / Nội dung chi tiết (tuỳ chọn)</label>
            <textarea
              style={sty.textarea}
              placeholder="Nhập kịch bản gồm 3 phần (Hook, Body, CTA) phân cách bằng xuống dòng. Nếu bỏ trống, AI sẽ tự viết dựa trên Chủ đề ở trên..."
              value={scriptText}
              onChange={(e) => setScriptText(e.target.value)}
            />
          </div>

          {/* Hook Style */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>🎣 Hiệu ứng Hook (Mở đầu video)</label>
            <div style={{ display: "flex", gap: 12 }}>
              <select style={sty.select} value={hookStyle} onChange={(e) => setHookStyle(e.target.value)}>
                <option value="zoom_in">Zoom In (Phóng to chậm)</option>
                <option value="zoom_out">Zoom Out (Thu nhỏ chậm)</option>
                <option value="glitch">RGB Glitch (Nhiễu sóng màu)</option>
                <option value="cinematic_vignette">Cinematic Vignette (Tối góc điện ảnh)</option>
                <option value="text_slide">Animated Hook Text (Chữ chạy thu hút)</option>
              </select>
            </div>
          </div>

          {/* Hook Text */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>🔤 Chữ chạy Hook (Tiêu đề nổi bật)</label>
            <input
              style={sty.topicInput}
              placeholder="VD: Đừng đi Đà Nẵng nếu chưa biết điều này! (Mặc định dùng Hook của kịch bản)"
              value={hookText}
              onChange={(e) => setHookText(e.target.value)}
            />
          </div>

          {/* Transition */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>✨ Hiệu ứng chuyển cảnh (Transition)</label>
            <select style={sty.select} value={transition} onChange={(e) => setTransition(e.target.value)}>
              {TRANSITION_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>

          {/* Voice mode */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>🎙️ Giọng đọc AI</label>
            <div style={sty.modeToggle}>
              <button style={{ ...sty.modeBtn, ...(voiceMode === "edge" ? sty.modeBtnActive : {}) }} onClick={() => setVoiceMode("edge")}>
                🌐 Edge TTS (Miễn phí)
              </button>
              <button style={{ ...sty.modeBtn, ...(voiceMode === "api" ? sty.modeBtnActive : {}) }} onClick={() => setVoiceMode("api")}>
                🔑 Vbee / ElevenLabs API
              </button>
              <button style={{ ...sty.modeBtn, ...(voiceMode === "mock" ? sty.modeBtnActive : {}) }} onClick={() => setVoiceMode("mock")}>
                🔇 Mock (Không tiếng)
              </button>
            </div>
            <div style={sty.hint}>
              {voiceMode === "edge" ? "Sử dụng Microsoft Edge TTS miễn phí để lồng tiếng chất lượng cao & phụ đề đồng bộ chính xác." :
               voiceMode === "api" ? "Sử dụng Vbee.ai hoặc ElevenLabs để tạo giọng đọc AI thật (cần API key trong Cài đặt)." :
               "Mock mode: video ghép từ các file thô của bạn nhưng không lồng tiếng (im lặng)."}
            </div>
          </div>

          {/* Seeding */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>📍 Địa điểm Seeding (tuỳ chọn)</label>
            {seedingItems.map((item) => (
              <div key={item.id} style={sty.seedingRow}>
                <select style={sty.seedingType} value={item.type} onChange={(e) => updateSeeding(item.id, "type", e.target.value)}>
                  <option value="restaurant">🍜 Quán</option>
                  <option value="hotel">🏨 Khách sạn</option>
                </select>
                <input style={sty.seedingInput} placeholder="Nhập tên địa điểm…" value={item.value} onChange={(e) => updateSeeding(item.id, "value", e.target.value)} />
                <button style={sty.seedingRemove} onClick={() => removeSeeding(item.id)} disabled={seedingItems.length === 1}>✕</button>
              </div>
            ))}
            <button style={sty.addSeedingBtn} onClick={addSeeding}>+ Thêm địa điểm</button>
          </div>

          <button
            style={{ ...sty.primaryBtn, opacity: !topic.trim() ? 0.5 : 1, cursor: !topic.trim() ? "not-allowed" : "pointer" }}
            onClick={runResearchAndScript}
            disabled={!topic.trim()}
          >
            ✨ Bắt đầu — AI Research & Viết kịch bản
          </button>
        </div>
      )}

      {/* ════ STEP 2 ════ */}
      {step === 2 && (
        <div style={sty.card}>
          <h2 style={sty.cardTitle}>Bước 2 — AI đang viết kịch bản & tạo Scene Plan</h2>

          {isCancelled ? (
            <div style={sty.cancelledBox}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🛑</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#ef4444", marginBottom: 8 }}>Đã dừng</div>
              <button style={sty.secondaryBtn} onClick={resetAll}>← Quay lại bước 1</button>
            </div>
          ) : (
            <>
              <div style={sty.spinnerWrap}>
                <div style={sty.spinner} />
                <div style={sty.spinnerText}>{SCRIPT_STAGES[Math.min(scriptStep, SCRIPT_STAGES.length - 1)]}…</div>
              </div>
              <div style={sty.pipelineSteps}>
                {SCRIPT_STAGES.map((s, i) => (
                  <div key={s} style={sty.pipelineStepRow}>
                    <div style={{
                      ...sty.pipelineStepDot,
                      background: i < scriptStep ? "#10b981" : i === scriptStep ? "#6366f1" : "#2a2a2a",
                      boxShadow: i === scriptStep ? "0 0 8px #6366f1" : "none",
                    }}>
                      {i < scriptStep ? "✓" : i + 1}
                    </div>
                    <span style={{ ...sty.pipelineStepLabel, color: i < scriptStep ? "#10b981" : i === scriptStep ? "#a78bfa" : "#4b5563", fontWeight: i === scriptStep ? 600 : 400 }}>
                      {s}
                    </span>
                    {i === scriptStep && <div style={sty.pipelineDots}><PulsingDots /></div>}
                  </div>
                ))}
              </div>
              <LogConsole logs={scriptLogs} />
              <button style={sty.dangerBtn} onClick={() => { cancelRef.current = true; setIsCancelled(true); }}>
                🛑 Dừng
              </button>
            </>
          )}
        </div>
      )}

      {/* ════ STEP 3 ════ */}
      {step === 3 && (
        <div style={sty.card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
            <h2 style={{ ...sty.cardTitle, margin: 0 }}>Bước 3 — Upload Media cho từng Scene</h2>
            <div style={sty.successBadge}>🤖 AI đã tạo {scenes.length} scene</div>
          </div>

          {/* Script preview */}
          {generatedScript && (
            <div style={{ ...sty.resultSection, marginBottom: 28 }}>
              <div
                style={{ ...sty.expandable, marginBottom: 0 }}
                onClick={() => setExpandedSection(expandedSection === "script" ? null : "script")}
              >
                <span>📝 Kịch bản AI đã viết</span>
                <span>{expandedSection === "script" ? "▲" : "▼"}</span>
              </div>
              {expandedSection === "script" && (
                <div style={{ ...sty.scriptGrid, marginTop: 12 }}>
                  <div style={{ ...sty.scriptBlock, borderColor: "#818cf840", background: "rgba(129,140,248,0.06)" }}>
                    <div style={{ ...sty.scriptBlockLabel, color: "#818cf8" }}>🎣 Hook</div>
                    <p style={sty.scriptBlockText}>{generatedScript.hook}</p>
                  </div>
                  <div style={{ ...sty.scriptBlock, borderColor: "#34d39940", background: "rgba(52,211,153,0.06)" }}>
                    <div style={{ ...sty.scriptBlockLabel, color: "#34d399" }}>📖 Body</div>
                    <p style={sty.scriptBlockText}>{generatedScript.body}</p>
                  </div>
                  <div style={{ ...sty.scriptBlock, borderColor: "#fb923c40", background: "rgba(251,146,60,0.06)" }}>
                    <div style={{ ...sty.scriptBlockLabel, color: "#fb923c" }}>📣 CTA</div>
                    <p style={sty.scriptBlockText}>{generatedScript.cta}</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Upload progress */}
          <div style={sty.uploadProgress}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#d1d5db" }}>
                {uploadedCount}/{scenes.length} scene đã upload
              </span>
              <span style={{ fontSize: 12, color: allUploaded ? "#10b981" : "#f59e0b", fontWeight: 600 }}>
                {allUploaded ? "✅ Đã sẵn sàng ghép" : "⏳ Chờ upload đủ các scene"}
              </span>
            </div>
            <div style={sty.progressTrack}>
              <div style={{
                ...sty.progressFill,
                width: `${scenes.length > 0 ? (uploadedCount / scenes.length) * 100 : 0}%`,
                background: allUploaded ? "#10b981" : "linear-gradient(90deg,#6366f1,#38bdf8)",
              }} />
            </div>
          </div>

          {/* Scene cards */}
          <div style={sty.sceneGrid}>
            {scenes.map((scene, i) => (
              <div key={scene.scene_id} style={{ ...sty.sceneCard, ...(scene.uploaded ? sty.sceneCardUploaded : {}) }}>
                <div style={sty.sceneCardHeader}>
                  <div style={sty.sceneNum}>
                    {scene.uploaded ? "✓" : i + 1}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={sty.sceneId}>Scene {i + 1}</div>
                    <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                      <span style={sty.sceneDurationBadge}>⏱ min {scene.min_duration_sec}s</span>
                      <span style={{ ...sty.sceneDurationBadge, background: scene.type === "image" ? "rgba(251,146,60,0.15)" : "rgba(99,102,241,0.15)", color: scene.type === "image" ? "#fb923c" : "#818cf8", borderColor: scene.type === "image" ? "#fb923c40" : "#818cf840" }}>
                        {scene.type === "image" ? "🖼️ Ảnh" : "🎥 Video"}
                      </span>
                    </div>
                  </div>
                  {scene.uploaded && (
                    <button style={sty.sceneRemoveBtn} onClick={() => handleRemoveSceneFile(scene.scene_id)} title="Xoá file">✕</button>
                  )}
                </div>

                <p style={sty.sceneDesc}>{scene.description}</p>

                {scene.uploaded && (scene.file_path || scene.file_object || scene.file_name) ? (
                  <div style={sty.sceneFilePill}>
                    <span style={{ fontSize: 14 }}>{scene.type === "image" ? "🖼️" : "🎞️"}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, color: "#d1d5db", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>
                        {scene.file_name
                          || scene.file_path?.split("\\").pop()
                          || scene.file_path?.split("/").pop()
                          || "file đã chọn"}
                      </div>
                      {scene.file_object && (
                        <div style={{ fontSize: 10, color: "#6b7280", marginTop: 2 }}>
                          {(scene.file_object.size / 1024 / 1024).toFixed(1)} MB
                        </div>
                      )}
                    </div>
                    <span style={{ fontSize: 10, color: "#10b981", fontWeight: 700, flexShrink: 0 }}>✓</span>
                  </div>
                ) : (
                  <button style={sty.sceneUploadBtn} onClick={() => handlePickSceneFile(scene.scene_id)}>
                    {scene.type === "image" ? "🖼️ Chọn ảnh" : "🎥 Chọn clip video"}
                  </button>
                )}
              </div>
            ))}
          </div>

          <div style={{ ...sty.step3Actions, marginTop: 28 }}>
            <button style={sty.secondaryBtn} onClick={() => setStep(1)}>← Quay lại</button>
            <button
              style={{ ...sty.warningBtn, opacity: uploadedCount === 0 ? 0.5 : 1, cursor: uploadedCount === 0 ? "not-allowed" : "pointer" }}
              onClick={() => runAssembleVideo(true)}
              disabled={uploadedCount === 0}
            >
              ⚡ Ghép ngay (placeholder cho scene chưa upload)
            </button>
            <button
              style={{ ...sty.primaryBtn, flex: "none", width: "auto", padding: "14px 32px", opacity: !allUploaded ? 0.5 : 1, cursor: !allUploaded ? "not-allowed" : "pointer" }}
              onClick={() => runAssembleVideo(false)}
              disabled={!allUploaded}
            >
              ▶️ Ghép video ({uploadedCount}/{scenes.length} scene)
            </button>
          </div>
        </div>
      )}

      {/* ════ STEP 4 ════ */}
      {step === 4 && (
        <div style={sty.card}>
          <h2 style={sty.cardTitle}>Bước 4 — Đang ghép video với FFmpeg</h2>
          {isCancelled ? (
            <div style={sty.cancelledBox}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🛑</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#ef4444", marginBottom: 8 }}>Đã dừng</div>
              <button style={sty.secondaryBtn} onClick={() => setStep(3)}>← Quay lại Scene Upload</button>
            </div>
          ) : (
            <>
              <div style={sty.spinnerWrap}>
                <div style={sty.spinner} />
                <div style={sty.spinnerText}>
                  {["Khởi động", "Tạo giọng nói", "Tạo phụ đề", "Chuẩn bị scene", "Ghép FFmpeg", "Hoàn tất"][Math.min(assemblyStep, 5)]}…
                </div>
              </div>
              <div style={sty.pipelineSteps}>
                {["Tạo giọng nói AI", "Tạo phụ đề SRT", "Chuẩn bị scene clips", `Ghép ${scenes.length} scene (${transition})`, "Chèn phụ đề"].map((s, i) => (
                  <div key={s} style={sty.pipelineStepRow}>
                    <div style={{
                      ...sty.pipelineStepDot,
                      background: i + 1 < assemblyStep ? "#10b981" : i + 1 === assemblyStep ? "#6366f1" : "#2a2a2a",
                      boxShadow: i + 1 === assemblyStep ? "0 0 8px #6366f1" : "none",
                    }}>
                      {i + 1 < assemblyStep ? "✓" : i + 1}
                    </div>
                    <span style={{ ...sty.pipelineStepLabel, color: i + 1 < assemblyStep ? "#10b981" : i + 1 === assemblyStep ? "#a78bfa" : "#4b5563", fontWeight: i + 1 === assemblyStep ? 600 : 400 }}>
                      {s}
                    </span>
                    {i + 1 === assemblyStep && <div style={sty.pipelineDots}><PulsingDots /></div>}
                  </div>
                ))}
              </div>
              <LogConsole logs={assemblyLogs} />
              <button style={sty.dangerBtn} onClick={() => { cancelRef.current = true; setIsCancelled(true); }}>
                🛑 Dừng ghép video
              </button>
            </>
          )}
        </div>
      )}

      {/* ════ STEP 5 ════ */}
      {step === 5 && result && (
        <div style={sty.card}>
          <div style={sty.step3Header}>
            <h2 style={sty.cardTitle}>Bước 5 — Kết quả</h2>
            <div style={sty.successBadge}>✅ Video hoàn chỉnh</div>
          </div>

          <div style={sty.resultSection}>
            <h3 style={sty.resultSectionTitle}>📝 Kịch bản</h3>
            <div style={sty.scriptGrid}>
              <div style={{ ...sty.scriptBlock, borderColor: "#818cf840", background: "rgba(129,140,248,0.06)" }}>
                <div style={{ ...sty.scriptBlockLabel, color: "#818cf8" }}>🎣 Hook</div>
                <p style={sty.scriptBlockText}>{result.script.hook}</p>
              </div>
              <div style={{ ...sty.scriptBlock, borderColor: "#34d39940", background: "rgba(52,211,153,0.06)" }}>
                <div style={{ ...sty.scriptBlockLabel, color: "#34d399" }}>📖 Body</div>
                <p style={sty.scriptBlockText}>{result.script.body}</p>
              </div>
              <div style={{ ...sty.scriptBlock, borderColor: "#fb923c40", background: "rgba(251,146,60,0.06)" }}>
                <div style={{ ...sty.scriptBlockLabel, color: "#fb923c" }}>📣 CTA</div>
                <p style={sty.scriptBlockText}>{result.script.cta}</p>
              </div>
            </div>
          </div>

          <div style={sty.resultSection}>
            <h3 style={sty.resultSectionTitle}>📢 Captions & Hashtags</h3>
            <div style={sty.captionBlock}>
              <div style={sty.captionLabel}>Caption ngắn</div>
              <div style={sty.captionText}>{result.captions.caption_short}</div>
            </div>
            <div style={{ ...sty.expandable }} onClick={() => setExpandedSection(expandedSection === "hashtags" ? null : "hashtags")}>
              <span># Hashtags ({result.captions.hashtags.length})</span>
              <span>{expandedSection === "hashtags" ? "▲" : "▼"}</span>
            </div>
            {expandedSection === "hashtags" && (
              <div style={sty.hashtagWrap}>
                {result.captions.hashtags.map((h) => <span key={h} style={sty.hashtagChip}>{h}</span>)}
              </div>
            )}
          </div>

          <div style={sty.resultSection}>
            <h3 style={sty.resultSectionTitle}>📁 File xuất</h3>
            <FilePathRow icon="🎥" label="Video" path={result.videoPath} ext=".mp4" />
            <FilePathRow icon="🎙️" label="Audio" path={result.audioPath} ext=".wav" />
          </div>

          <div style={sty.step3Actions}>
            <button style={sty.secondaryBtn} onClick={resetAll}>🔄 Tạo lại</button>
            <button style={sty.primaryBtn} onClick={syncDashboard}>📤 Đồng bộ lên Dashboard</button>
          </div>
        </div>
      )}

      {/* ════ STEP 6 ════ */}
      {step === 6 && (
        <div style={sty.card}>
          <h2 style={sty.cardTitle}>Bước 6 — Đồng bộ lên Dashboard</h2>
          {syncStatus === "loading" && (
            <div style={sty.syncCenter}>
              <div style={sty.syncSpinner} />
              <div style={sty.syncText}>Đang gửi lên Dashboard…</div>
              <div style={sty.syncSub}>http://localhost:3000/api/videos</div>
            </div>
          )}
          {syncStatus === "ok" && (
            <div style={sty.syncCenter}>
              <div style={{ fontSize: 64, marginBottom: 16 }}>✅</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#10b981", marginBottom: 8 }}>Đồng bộ thành công!</div>
              <div style={sty.urlBox}>
                <span style={{ color: "#818cf8" }}>🔗</span>
                <span style={{ fontSize: 13, color: "#e5e7eb" }}>{syncedUrl}</span>
                <button style={sty.copyBtn} onClick={() => navigator.clipboard?.writeText(syncedUrl)}>Copy</button>
              </div>
              <button style={{ ...sty.primaryBtn, marginTop: 24 }} onClick={resetAll}>✨ Tạo bài mới</button>
            </div>
          )}
          {syncStatus === "error" && (
            <div style={sty.syncCenter}>
              <div style={{ fontSize: 64, marginBottom: 16 }}>❌</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#ef4444", marginBottom: 8 }}>Đồng bộ thất bại</div>
              <div style={sty.errorBox}>Error: ECONNREFUSED — Connection refused at http://localhost:3000</div>
              <div style={sty.step3Actions}>
                <button style={sty.secondaryBtn} onClick={() => setStep(5)}>← Quay lại</button>
                <button style={sty.primaryBtn} onClick={syncDashboard}>🔄 Thử lại</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────
const sty: Record<string, any> = {
  container: { padding: "28px 32px", height: "100%", overflowY: "auto", boxSizing: "border-box", background: "#0f0f0f" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 },
  title: { fontSize: 24, fontWeight: 700, color: "#f1f1f1", margin: 0, letterSpacing: -0.5 },
  subtitle: { fontSize: 13, color: "#6b7280", margin: "4px 0 0" },

  stepBar: { display: "flex", alignItems: "center", marginBottom: 28, padding: "16px 20px", background: "#161616", borderRadius: 14, border: "1px solid #252525" },
  stepItem: { display: "flex", flexDirection: "column", alignItems: "center", gap: 6, flexShrink: 0 },
  stepCircle: { width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, transition: "all 0.3s" },
  stepLabel: { fontSize: 10, fontWeight: 500, whiteSpace: "nowrap", transition: "color 0.3s" },
  stepLine: { flex: 1, height: 2, margin: "0 6px", borderRadius: 2, transition: "background 0.3s", marginBottom: 16 },

  card: { background: "#161616", border: "1px solid #252525", borderRadius: 16, padding: "28px 32px" },
  cardTitle: { fontSize: 18, fontWeight: 700, color: "#e5e7eb", margin: "0 0 24px", letterSpacing: -0.3 },

  fieldGroup: { marginBottom: 24 },
  label: { display: "block", fontSize: 13, fontWeight: 600, color: "#d1d5db", marginBottom: 10 },
  required: { color: "#ef4444" },
  hint: { fontSize: 11, color: "#6b7280", marginTop: 6 },

  topicInput: { width: "100%", padding: "14px 16px", fontSize: 16, background: "#1e1e1e", border: "1px solid #333", borderRadius: 12, color: "#f1f1f1", outline: "none", boxSizing: "border-box", transition: "border-color 0.2s" },

  creatorGrid: { display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 },
  creatorCard: { position: "relative", background: "#1e1e1e", border: "2px solid #2a2a2a", borderRadius: 12, padding: "14px 10px", textAlign: "center", cursor: "pointer", transition: "all 0.2s" },
  creatorCardActive: { border: "2px solid #6366f1", background: "rgba(99,102,241,0.08)", boxShadow: "0 0 12px rgba(99,102,241,0.2)" },
  creatorEmoji: { fontSize: 28, marginBottom: 8 },
  creatorName: { fontSize: 12, fontWeight: 600, color: "#e5e7eb", marginBottom: 4 },
  creatorSpec: { fontSize: 10, color: "#6b7280", lineHeight: 1.4 },
  creatorCheck: { position: "absolute", top: 6, right: 8, width: 18, height: 18, borderRadius: "50%", background: "#6366f1", color: "#fff", fontSize: 10, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700 },

  templateRow: { display: "flex", gap: 16 },
  templateCard: { flex: 1, background: "#1e1e1e", border: "2px solid #2a2a2a", borderRadius: 12, padding: "18px", textAlign: "center", cursor: "pointer", transition: "all 0.2s" },
  templateCardActive: { border: "2px solid #818cf8", background: "rgba(129,140,248,0.08)", boxShadow: "0 0 12px rgba(129,140,248,0.2)" },
  templateIcon: { fontSize: 24, display: "block", marginBottom: 8 },
  templateRatio: { fontSize: 18, fontWeight: 800, color: "#f1f1f1", marginBottom: 4 },
  templateLabel: { fontSize: 13, fontWeight: 600, color: "#d1d5db", marginBottom: 4 },
  templateDesc: { fontSize: 11, color: "#6b7280" },

  // Scene Config
  sceneConfigBox: { background: "linear-gradient(135deg, rgba(99,102,241,0.06), rgba(56,189,248,0.04))", border: "1px solid rgba(99,102,241,0.2)", borderRadius: 16, padding: "20px 24px" },
  sceneConfigHeader: { display: "flex", alignItems: "center", gap: 14, marginBottom: 20 },
  sceneConfigIcon: { fontSize: 32 },
  sceneConfigTitle: { fontSize: 15, fontWeight: 700, color: "#e5e7eb" },
  sceneConfigSub: { fontSize: 12, color: "#6b7280", marginTop: 3 },
  sceneModeRow: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 },
  sceneModeCard: { position: "relative", background: "#1e1e1e", border: "2px solid #2a2a2a", borderRadius: 12, padding: "14px 16px", cursor: "pointer", transition: "all 0.2s" },
  sceneModeCardActive: { border: "2px solid #818cf8", background: "rgba(129,140,248,0.1)", boxShadow: "0 0 10px rgba(129,140,248,0.2)" },
  sceneModeBadge: { fontSize: 13, fontWeight: 700, color: "#e5e7eb", marginBottom: 6 },
  sceneModeDesc: { fontSize: 11, color: "#6b7280", lineHeight: 1.5 },
  sceneModeCheck: { position: "absolute", top: 10, right: 12, fontSize: 12, fontWeight: 700, color: "#818cf8" },

  countChip: { background: "#1e1e1e", border: "2px solid #2a2a2a", borderRadius: 20, padding: "6px 18px", fontSize: 13, fontWeight: 600, color: "#9ca3af", cursor: "pointer", transition: "all 0.2s" },
  countChipActive: { border: "2px solid #818cf8", color: "#818cf8", background: "rgba(129,140,248,0.1)" },

  customSceneRow: { display: "flex", gap: 8, marginBottom: 10, alignItems: "center" },
  customSceneNum: { width: 28, height: 28, borderRadius: "50%", background: "linear-gradient(135deg,#6366f1,#818cf8)", color: "#fff", fontSize: 12, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 },

  seedingRow: { display: "flex", gap: 8, marginBottom: 8, alignItems: "center" },
  seedingType: { flexShrink: 0, background: "#1e1e1e", border: "1px solid #333", borderRadius: 8, color: "#d1d5db", padding: "8px 10px", fontSize: 13 },
  seedingInput: { flex: 1, background: "#1e1e1e", border: "1px solid #333", borderRadius: 8, color: "#f1f1f1", padding: "8px 12px", fontSize: 13, outline: "none" },
  seedingRemove: { background: "none", border: "1px solid #333", borderRadius: 8, color: "#6b7280", padding: "8px 12px", cursor: "pointer", fontSize: 12 },
  addSeedingBtn: { background: "none", border: "1px dashed #333", borderRadius: 8, color: "#818cf8", padding: "8px 16px", cursor: "pointer", fontSize: 13, width: "100%", marginTop: 4, transition: "border-color 0.2s" },
  textarea: { width: "100%", background: "#1e1e1e", border: "1px solid #333", borderRadius: 8, color: "#f1f1f1", padding: "10px 14px", fontSize: 13, outline: "none", minHeight: 80, fontFamily: "Inter, sans-serif", resize: "vertical" as const },
  select: { background: "#1e1e1e", border: "1px solid #333", borderRadius: 8, color: "#d1d5db", padding: "8px 12px", fontSize: 13, outline: "none", width: "100%" },

  modeToggle: { display: "flex", background: "#1a1a1a", borderRadius: 10, padding: 4, gap: 4, border: "1px solid #252525", width: "fit-content" },
  modeBtn: { background: "none", border: "none", borderRadius: 8, color: "#6b7280", padding: "10px 20px", cursor: "pointer", fontSize: 13, fontWeight: 500, transition: "all 0.2s" },
  modeBtnActive: { background: "linear-gradient(135deg, #6366f1, #818cf8)", color: "#fff", fontWeight: 600, boxShadow: "0 2px 8px rgba(99,102,241,0.4)" },

  primaryBtn: { width: "100%", background: "linear-gradient(135deg, #6366f1 0%, #818cf8 50%, #38bdf8 100%)", border: "none", borderRadius: 12, color: "#fff", fontSize: 16, fontWeight: 700, padding: "16px 24px", cursor: "pointer", boxShadow: "0 4px 24px rgba(99,102,241,0.4)", letterSpacing: 0.3, transition: "filter 0.2s, transform 0.15s" },
  secondaryBtn: { background: "#1e1e1e", border: "1px solid #333", borderRadius: 12, color: "#d1d5db", fontSize: 14, fontWeight: 600, padding: "12px 24px", cursor: "pointer", transition: "background 0.2s" },
  warningBtn: { background: "rgba(251,146,60,0.1)", border: "1px solid #fb923c40", borderRadius: 12, color: "#fb923c", fontSize: 14, fontWeight: 600, padding: "12px 24px", cursor: "pointer", transition: "all 0.2s" },
  dangerBtn: { marginTop: 16, background: "rgba(239,68,68,0.1)", border: "1px solid #ef444440", borderRadius: 12, color: "#ef4444", fontSize: 14, fontWeight: 600, padding: "12px 24px", cursor: "pointer", transition: "background 0.2s", width: "100%" },

  spinnerWrap: { display: "flex", flexDirection: "column", alignItems: "center", padding: "32px 0 28px" },
  spinner: { width: 64, height: 64, border: "4px solid #252525", borderTop: "4px solid #818cf8", borderRadius: "50%", animation: "spin 0.9s linear infinite", marginBottom: 16 },
  spinnerText: { fontSize: 16, fontWeight: 600, color: "#a78bfa" },
  pipelineSteps: { display: "flex", flexDirection: "column", gap: 14, marginBottom: 24, padding: "20px", background: "#1a1a1a", borderRadius: 12, border: "1px solid #252525" },
  pipelineStepRow: { display: "flex", alignItems: "center", gap: 12 },
  pipelineStepDot: { width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "#fff", flexShrink: 0, transition: "all 0.3s" },
  pipelineStepLabel: { fontSize: 14, transition: "color 0.3s", flex: 1 },
  pipelineDots: { marginLeft: "auto" },
  cancelledBox: { textAlign: "center", padding: "40px 20px" },

  logConsole: { background: "#0d0d0d", border: "1px solid #252525", borderRadius: 12, overflow: "hidden", marginBottom: 16 },
  logHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", background: "#1a1a1a", borderBottom: "1px solid #252525" },
  logTitle: { fontSize: 12, fontWeight: 600, color: "#9ca3af" },
  logCount: { fontSize: 11, color: "#4b5563" },
  logBody: { padding: "12px 14px", maxHeight: 200, overflowY: "auto", fontFamily: "monospace" },
  logLine: { display: "flex", gap: 10, marginBottom: 5, fontSize: 12, lineHeight: 1.5 },
  logTime: { color: "#4b5563", flexShrink: 0, fontSize: 11 },
  logText: { wordBreak: "break-all" },

  // Step 3 — Scene upload
  uploadProgress: { marginBottom: 20, padding: "16px 20px", background: "#1a1a1a", borderRadius: 12, border: "1px solid #252525" },
  progressTrack: { height: 8, background: "#252525", borderRadius: 4, overflow: "hidden" },
  progressFill: { height: "100%", borderRadius: 4, transition: "width 0.4s ease" },

  sceneGrid: { display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16 },
  sceneCard: { background: "#1a1a1a", border: "1px solid #2a2a2a", borderRadius: 14, padding: "18px", transition: "all 0.2s" },
  sceneCardUploaded: { border: "1px solid #10b98140", background: "rgba(16,185,129,0.04)" },
  sceneCardHeader: { display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 12 },
  sceneNum: { width: 32, height: 32, borderRadius: "50%", background: "linear-gradient(135deg,#6366f1,#818cf8)", color: "#fff", fontSize: 13, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 },
  sceneId: { fontSize: 13, fontWeight: 700, color: "#e5e7eb" },
  sceneDurationBadge: { display: "inline-flex", alignItems: "center", gap: 4, background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.3)", color: "#818cf8", borderRadius: 10, padding: "2px 8px", fontSize: 10, fontWeight: 600 },
  sceneDesc: { fontSize: 12, color: "#9ca3af", lineHeight: 1.6, margin: "0 0 14px" },
  sceneUploadBtn: { width: "100%", background: "rgba(99,102,241,0.1)", border: "1px dashed rgba(99,102,241,0.4)", borderRadius: 10, color: "#818cf8", fontSize: 13, fontWeight: 600, padding: "12px", cursor: "pointer", transition: "all 0.2s" },
  sceneFilePill: { display: "flex", alignItems: "center", gap: 8, background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.3)", borderRadius: 10, padding: "8px 12px" },
  sceneRemoveBtn: { background: "none", border: "1px solid #333", borderRadius: 8, color: "#6b7280", padding: "4px 8px", cursor: "pointer", fontSize: 12, flexShrink: 0 },

  // Step 5 result
  step3Header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 },
  successBadge: { background: "rgba(16,185,129,0.1)", border: "1px solid #10b98140", color: "#10b981", borderRadius: 20, padding: "6px 16px", fontSize: 13, fontWeight: 600 },
  resultSection: { marginBottom: 24 },
  resultSectionTitle: { fontSize: 14, fontWeight: 600, color: "#9ca3af", margin: "0 0 14px", textTransform: "uppercase", letterSpacing: 0.5 },
  scriptGrid: { display: "flex", flexDirection: "column", gap: 12 },
  scriptBlock: { borderRadius: 12, padding: "16px 18px", border: "1px solid", transition: "transform 0.15s" },
  scriptBlockLabel: { fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 },
  scriptBlockText: { fontSize: 14, color: "#e5e7eb", lineHeight: 1.6, margin: 0 },
  captionBlock: { background: "#1a1a1a", borderRadius: 10, padding: "12px 16px", marginBottom: 10, border: "1px solid #252525" },
  captionLabel: { fontSize: 11, color: "#6b7280", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 },
  captionText: { fontSize: 13, color: "#e5e7eb", lineHeight: 1.6 },
  expandable: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", background: "#1a1a1a", borderRadius: 10, border: "1px solid #252525", cursor: "pointer", fontSize: 13, fontWeight: 600, color: "#d1d5db", marginBottom: 8, transition: "background 0.2s" },
  hashtagWrap: { display: "flex", flexWrap: "wrap", gap: 8, padding: "12px 0" },
  hashtagChip: { background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.3)", color: "#818cf8", borderRadius: 20, padding: "4px 12px", fontSize: 12, fontWeight: 500 },
  fileRow: { display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", background: "#1a1a1a", borderRadius: 10, border: "1px solid #252525", marginBottom: 10 },
  fileIcon: { fontSize: 22, flexShrink: 0 },
  fileInfo: { flex: 1, minWidth: 0 },
  fileLabel: { fontSize: 13, fontWeight: 600, color: "#e5e7eb", marginBottom: 2 },
  filePath: { fontSize: 11, color: "#6b7280", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  fileExt: { background: "#252525", color: "#9ca3af", borderRadius: 6, padding: "3px 8px", fontSize: 11, fontWeight: 600, flexShrink: 0 },
  openFolderBtn: { background: "none", border: "1px solid #333", borderRadius: 8, padding: "6px 10px", cursor: "pointer", fontSize: 16, color: "#6b7280", flexShrink: 0 },
  step3Actions: { display: "flex", gap: 12, marginTop: 24 },

  // Step 6 sync
  syncCenter: { display: "flex", flexDirection: "column", alignItems: "center", padding: "40px 20px", textAlign: "center" },
  syncSpinner: { width: 56, height: 56, border: "4px solid #252525", borderTop: "4px solid #818cf8", borderRight: "4px solid #38bdf8", borderRadius: "50%", animation: "spin 0.9s linear infinite", marginBottom: 20 },
  syncText: { fontSize: 18, fontWeight: 700, color: "#e5e7eb", marginBottom: 8 },
  syncSub: { fontSize: 12, color: "#6b7280", fontFamily: "monospace" },
  urlBox: { display: "flex", alignItems: "center", gap: 10, background: "#1a1a1a", border: "1px solid #333", borderRadius: 10, padding: "10px 14px", maxWidth: 480, width: "100%" },
  copyBtn: { marginLeft: "auto", background: "none", border: "1px solid #333", borderRadius: 6, color: "#818cf8", fontSize: 12, padding: "4px 10px", cursor: "pointer" },
  errorBox: { background: "rgba(239,68,68,0.08)", border: "1px solid #ef444440", borderRadius: 10, padding: "10px 16px", fontSize: 12, color: "#ef4444", fontFamily: "monospace", maxWidth: 480, width: "100%", textAlign: "left" },
};

// ── Global keyframes ───────────────────────────────────────────────────────
if (typeof document !== "undefined" && !document.getElementById("studio-keyframes")) {
  const style = document.createElement("style");
  style.id = "studio-keyframes";
  style.textContent = `
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes pulse {
      0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
      40% { transform: scale(1); opacity: 1; }
    }
  `;
  document.head.appendChild(style);
}
