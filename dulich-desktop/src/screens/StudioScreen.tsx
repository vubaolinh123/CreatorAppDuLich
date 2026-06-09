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

interface PipelineResult {
  script: { hook: string; body: string; cta: string };
  captions: {
    caption_short: string;
    caption_long: string;
    hashtags: string[];
  };
  imagePrompts: string[];
  videoPath: string;
  audioPath: string;
  dashboardUrl?: string;
}

interface LogLine {
  id: string;
  time: string;
  type: "info" | "success" | "warn" | "error";
  text: string;
}

type Step = 1 | 2 | 3 | 4;
type Mode = "mock" | "full";

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
  { id: "1:1", ratio: "1:1", label: "Vuông", desc: "Instagram feed", icon: "⬜" },
  { id: "16:9", ratio: "16:9", label: "YouTube", desc: "Ngang — màn hình rộng", icon: "🖥️" },
];

const PIPELINE_STEPS = [
  "Phân tích chủ đề",
  "Viết kịch bản",
  "Tạo giọng nói",
  "Dựng video",
  "Hoàn tất",
];

// ── Mock pipeline log lines ────────────────────────────────────────────────
function generateMockLogs(topic: string, creator: string): LogLine[] {
  const now = new Date();
  const fmt = (offset: number) =>
    new Date(now.getTime() + offset * 1000).toLocaleTimeString("vi-VN");
  return [
    { id: "l1",  time: fmt(0),  type: "info",    text: `[Pipeline] Khởi động pipeline cho chủ đề: "${topic}"` },
    { id: "l2",  time: fmt(0),  type: "info",    text: "[Config] Đọc cấu hình từ config.py..." },
    { id: "l3",  time: fmt(1),  type: "info",    text: `[Trend] Phân tích xu hướng: ${topic}` },
    { id: "l4",  time: fmt(1),  type: "success", text: "[Trend] ✓ Đã nhận diện xu hướng tích cực" },
    { id: "l5",  time: fmt(2),  type: "info",    text: "[Script] Gọi Claude AI để viết kịch bản..." },
    { id: "l6",  time: fmt(2),  type: "info",    text: `[Script] Creator: ${creator} — giọng nói phù hợp` },
    { id: "l7",  time: fmt(3),  type: "success", text: "[Script] ✓ Kịch bản Hook/Body/CTA đã hoàn thành (245 từ)" },
    { id: "l8",  time: fmt(3),  type: "info",    text: "[Captions] Tạo captions & hashtags..." },
    { id: "l9",  time: fmt(4),  type: "success", text: "[Captions] ✓ 12 hashtags đã được tạo" },
    { id: "l10", time: fmt(4),  type: "info",    text: "[Images] Tạo image prompts cho Midjourney..." },
    { id: "l11", time: fmt(5),  type: "success", text: "[Images] ✓ 5 image prompts đã tạo" },
    { id: "l12", time: fmt(5),  type: "info",    text: "[Voice] Kết nối ElevenLabs API..." },
    { id: "l13", time: fmt(6),  type: "warn",    text: "[Voice] ELEVENLABS_API_KEY không có — dùng mock audio" },
    { id: "l14", time: fmt(7),  type: "success", text: "[Voice] ✓ Audio mock đã tạo: audio/output_mock.wav" },
    { id: "l15", time: fmt(7),  type: "info",    text: "[Video] Dựng video với FFmpeg..." },
    { id: "l16", time: fmt(9),  type: "success", text: "[Video] ✓ Video đã render: output/videos/output_mock.mp4" },
    { id: "l17", time: fmt(9),  type: "success", text: "[Pipeline] ✅ Pipeline hoàn tất thành công!" },
  ];
}

// ── Mock result ────────────────────────────────────────────────────────────
export function generateMockResult(topic: string): PipelineResult {
  return {
    script: {
      hook: `Bạn đã biết ${topic} có điều này chưa? 😱 Mình shock thật sự khi lần đầu đến đây!`,
      body: `Hôm nay mình sẽ review toàn bộ hành trình khám phá ${topic} — từ chỗ ăn, chỗ ngủ cho đến những góc chụp hình cực đẹp mà ít ai biết. Đây là địa điểm mình đã ở 3 ngày 2 đêm và thật sự không muốn về. Thức ăn ngon, người dân thân thiện, phong cảnh thì miễn chê!`,
      cta: `Follow để không bỏ lỡ series du lịch ${topic} nhé! Link đặt phòng trong bio 👇`,
    },
    captions: {
      caption_short: `${topic} - Trải nghiệm không thể quên! 🌟`,
      caption_long: `✈️ Hành trình ${topic} của mình đây! Nếu bạn đang lên kế hoạch đến đây, đừng bỏ qua video này. Mình đã tổng hợp tất cả kinh nghiệm sau chuyến đi 3 ngày — ăn ở đâu ngon, chơi gì hay, chi phí bao nhiêu. Save lại để dùng nhé! 🗺️`,
      hashtags: [
        `#${topic.replace(/\s+/g, "")}`,
        "#dulichVietnam",
        "#review",
        "#travel",
        "#travelgram",
        "#dulich2026",
        "#kinhghiemdulịch",
        "#vietnam",
        "#travelvlog",
        "#review360",
        "#feedreview",
        "#chiasedulich",
      ],
    },
    imagePrompts: [
      `Aerial drone shot of ${topic} coastline at golden hour, vibrant colors, travel photography`,
      `Local street food market in ${topic}, warm lights, authentic atmosphere, shallow depth of field`,
      `Tourist exploring hidden alley in ${topic}, backpack, adventure mood, editorial style`,
      `Resort swimming pool overlooking ${topic} landscape, luxury travel, blue water, palm trees`,
      `Traditional cultural ceremony in ${topic}, colorful costumes, motion blur, documentary style`,
    ],
    videoPath: `D:\\ProjectWeb\\DuLichAppWeb\\dulich-pipeline\\output\\videos\\${topic.replace(/\s+/g, "_")}_mock.mp4`,
    audioPath: `D:\\ProjectWeb\\DuLichAppWeb\\dulich-pipeline\\output\\audio\\${topic.replace(/\s+/g, "_")}_mock.wav`,
  };
}

// ── Step Indicator ─────────────────────────────────────────────────────────
function StepIndicator({ current }: { current: Step }) {
  const steps = [
    { num: 1, label: "Nhập nội dung" },
    { num: 2, label: "Đang chạy" },
    { num: 3, label: "Kết quả" },
    { num: 4, label: "Đồng bộ" },
  ];
  return (
    <div style={sty.stepBar}>
      {steps.map((s, idx) => (
        <React.Fragment key={s.num}>
          <div style={sty.stepItem}>
            <div
              style={{
                ...sty.stepCircle,
                background:
                  current === s.num
                    ? "linear-gradient(135deg,#6366f1,#38bdf8)"
                    : current > s.num
                    ? "#10b981"
                    : "#2a2a2a",
                color: current >= s.num ? "#fff" : "#6b7280",
                boxShadow: current === s.num ? "0 0 12px rgba(99,102,241,0.5)" : "none",
              }}
            >
              {current > s.num ? "✓" : s.num}
            </div>
            <span
              style={{
                ...sty.stepLabel,
                color: current === s.num ? "#a78bfa" : current > s.num ? "#10b981" : "#4b5563",
              }}
            >
              {s.label}
            </span>
          </div>
          {idx < steps.length - 1 && (
            <div
              style={{
                ...sty.stepLine,
                background: current > s.num ? "#10b981" : "#252525",
              }}
            />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// ── Log Console Component ──────────────────────────────────────────────────
function LogConsole({ logs }: { logs: LogLine[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  const logColor = (t: LogLine["type"]) => {
    if (t === "success") return "#10b981";
    if (t === "warn") return "#f59e0b";
    if (t === "error") return "#ef4444";
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
        {logs.length === 0 && (
          <div style={{ color: "#4b5563", fontSize: 12, padding: "10px 0" }}>
            Chưa có logs...
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ── MAIN COMPONENT ─────────────────────────────────────────────────────────
export default function StudioScreen() {
  const [step, setStep] = useState<Step>(1);

  // Step 1 state
  const [topic, setTopic] = useState("");
  const [selectedCreator, setSelectedCreator] = useState<string>("c1");
  const [selectedTemplate, setSelectedTemplate] = useState<string>("9:16");
  const [mode, setMode] = useState<Mode>("mock");
  const [seedingItems, setSeedingItems] = useState<SeedingItem[]>([
    { id: "s1", value: "", type: "restaurant" },
  ]);

  // Personal Channel Step 1 states
  const [scriptText, setScriptText] = useState("");
  const [clipsInput, setClipsInput] = useState("");
  const [hookStyle, setHookStyle] = useState("zoom_in");
  const [hookText, setHookText] = useState("");

  // Step 2 state
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [pipelineStep, setPipelineStep] = useState(0);
  const [isCancelled, setIsCancelled] = useState(false);

  // Step 3 state
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [expandedSection, setExpandedSection] = useState<string | null>("hashtags");

  // Step 4 state
  const [syncStatus, setSyncStatus] = useState<"loading" | "ok" | "error" | null>(null);
  const [syncedUrl, setSyncedUrl] = useState("");

  // Fetch creator default template on select
  useEffect(() => {
    fetchCreatorSettings(selectedCreator);
  }, [selectedCreator]);

  const fetchCreatorSettings = async (cid: string) => {
    const idMap: Record<string, string> = {
      c1: "lan_anh",
      c2: "minh_tuan",
      c3: "thu_ha",
      c4: "duc_anh",
      c5: "ngoc_mai"
    };
    const mappedId = idMap[cid] || cid;
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    if (!isTauri) return;
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const resStr = await invoke<string>("get_creators");
      const res = JSON.parse(resStr);
      if (res.success && Array.isArray(res.data)) {
        const creator = res.data.find((c: any) => c.id === mappedId);
        if (creator && creator.hook_preference) {
          setHookStyle(creator.hook_preference);
        }
      }
    } catch (e) {
      console.error("Lỗi lấy thông tin creator template:", e);
    }
  };


  const cancelRef = useRef(false);

  // ── Seeding helpers ──
  const addSeeding = () =>
    setSeedingItems((p) => [...p, { id: `s${Date.now()}`, value: "", type: "restaurant" }]);
  const removeSeeding = (id: string) =>
    setSeedingItems((p) => p.filter((i) => i.id !== id));
  const updateSeeding = (id: string, field: keyof SeedingItem, val: string) =>
    setSeedingItems((p) => p.map((i) => (i.id === id ? { ...i, [field]: val } : i)));

  // ── Run pipeline (hybrid Tauri / mock) ──
  const runPipeline = async () => {
    if (!topic.trim()) return;
    cancelRef.current = false;
    setIsCancelled(false);
    setLogs([]);
    setPipelineStep(0);
    setStep(2);

    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;

    if (isTauri) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const { listen } = await import("@tauri-apps/api/event");

        // Listen to logs from Rust backend subprocess
        const unlisten = await listen<any>("pipeline-log", (event) => {
          const logPayload = event.payload; // { time, level, text }
          
          setLogs((prev) => [
            ...prev,
            {
              id: Math.random().toString(),
              time: logPayload.time,
              type: (logPayload.level === "warn" ? "warn" : logPayload.level === "warning" ? "warn" : logPayload.level) as any,
              text: logPayload.text,
            }
          ]);

          // Update pipeline step indicators based on log contents
          const text = logPayload.text;
          if (text.includes("[Trend]")) {
            setPipelineStep(1); // Research / Trend
          } else if (text.includes("[Script]")) {
            setPipelineStep(2); // Script
          } else if (text.includes("[Voice]")) {
            setPipelineStep(3); // Voice
          } else if (text.includes("[Video]")) {
            setPipelineStep(4); // Video
          } else if (text.includes("Pipeline complete!")) {
            setPipelineStep(5); // Complete
          }
        });

        // Run Personal pipeline subprocess in Rust backend
        const idMap: Record<string, string> = {
          c1: "lan_anh",
          c2: "minh_tuan",
          c3: "thu_ha",
          c4: "duc_anh",
          c5: "ngoc_mai"
        };
        const mappedId = idMap[selectedCreator] || selectedCreator;
        
        const rawClips = clipsInput.split(",").map(c => c.trim()).filter(c => c.length > 0);
        const creatorName = CREATORS.find((c) => c.id === selectedCreator)?.name || "Creator";

        const resultJsonStr = await invoke<string>("run_personal_pipeline", {
          creatorId: mappedId,
          scriptText: scriptText || topic,
          clips: rawClips,
          hookStyle: hookStyle,
          hookText: hookText || topic,
          voiceProvider: "", // Will use database voice provider
        });

        unlisten();

        // Parse result JSON
        const runResult = JSON.parse(resultJsonStr);
        const finalResult = {
          script: runResult.script || { hook: "", body: "", cta: "" },
          captions: {
            caption_short: `Video cá nhân từ ${creatorName} 🌟`,
            caption_long: `Xin chào mọi người, đây là video được sản xuất bởi ${creatorName} sử dụng công nghệ AI Voice Clone và Hook Effects.`,
            hashtags: ["#dulich", `#${mappedId}`, `#${runResult.hook_style || "hook"}`]
          },
          imagePrompts: [],
          videoPath: runResult.video_path || "",
          audioPath: runResult.audio_path || "",
        };

        setResult(finalResult);

        // Add to Zustand library store so it shows up in LibraryScreen
        const addToLibrary = useAppStore.getState().addToLibrary;
        addToLibrary({
          id: `lib-${Date.now()}`,
          topic,
          creator: creatorName,
          status: "local",
          createdAt: new Date().toISOString(),
          result: {
            script: finalResult.script,
            captions: {
              hooks: [],
              caption_short: finalResult.captions.caption_short,
              caption_long: finalResult.captions.caption_long,
              hashtags: finalResult.captions.hashtags,
            },
            images: {
              description: topic,
              prompts: finalResult.imagePrompts,
            },
            videoPath: finalResult.videoPath,
            audioPath: finalResult.audioPath,
          }
        });

        setStep(3);

      } catch (err: any) {
        setLogs((prev) => [
          ...prev,
          {
            id: Math.random().toString(),
            time: new Date().toLocaleTimeString("vi-VN"),
            type: "error",
            text: `❌ Lỗi thực thi pipeline: ${err.message || err}`,
          }
        ]);
        setIsCancelled(true);
      }
    } else {
      // ── Mock Fallback (Browser environment) ──
      const creatorName = CREATORS.find((c) => c.id === selectedCreator)?.name || "Creator";
      const allLogs = generateMockLogs(topic, creatorName);
      const stepBreaks = [2, 6, 9, 13, 16]; // log indices that map to pipeline steps

      for (let i = 0; i < allLogs.length; i++) {
        if (cancelRef.current) {
          setIsCancelled(true);
          return;
        }
        await new Promise((r) => setTimeout(r, 350 + Math.random() * 300));
        setLogs((p) => [...p, allLogs[i]]);
        const stepIdx = stepBreaks.findIndex((b) => i === b);
        if (stepIdx !== -1) setPipelineStep(stepIdx + 1);
      }

      // Done mock
      await new Promise((r) => setTimeout(r, 500));
      const idMap: Record<string, string> = {
        c1: "lan_anh",
        c2: "minh_tuan",
        c3: "thu_ha",
        c4: "duc_anh",
        c5: "ngoc_mai"
      };
      const mappedId = idMap[selectedCreator] || selectedCreator;

      const mockResult = {
        script: {
          hook: hookText || `Chào các bạn, mình là ${creatorName}. Bạn đã thấy nơi này chưa?`,
          body: scriptText || `Hôm nay mình đang trải nghiệm du lịch tại chủ đề ${topic}. Một điểm đến vô cùng đẹp đẽ và thú vị mà mọi người không nên bỏ qua khi có dịp ghé thăm.`,
          cta: "Hãy thả tim và follow mình để xem tiếp các hành trình sau nha!"
        },
        captions: {
          caption_short: `Trải nghiệm cùng ${creatorName}! 🌟`,
          caption_long: `Hành trình khám phá chủ đề ${topic} cùng với hiệu ứng hook ${hookStyle}.`,
          hashtags: ["#dulich", `#${creatorName}`, `#${hookStyle}`]
        },
        imagePrompts: [],
        videoPath: `D:\\ProjectWeb\\DuLichAppWeb\\dulich-pipeline\\output\\videos\\video_personal_${mappedId}_mock.mp4`,
        audioPath: `D:\\ProjectWeb\\DuLichAppWeb\\dulich-pipeline\\output\\audio\\personal_${mappedId}_mock.wav`,
      };
      setResult(mockResult);

      // Add mock run to library store
      const addToLibrary = useAppStore.getState().addToLibrary;
      addToLibrary({
        id: `lib-${Date.now()}`,
        topic,
        creator: creatorName,
        status: "local",
        createdAt: new Date().toISOString(),
        result: {
          script: mockResult.script,
          captions: {
            hooks: [],
            caption_short: mockResult.captions.caption_short,
            caption_long: mockResult.captions.caption_long,
            hashtags: mockResult.captions.hashtags,
          },
          images: {
            description: topic,
            prompts: mockResult.imagePrompts,
          },
          videoPath: mockResult.videoPath,
          audioPath: mockResult.audioPath,
        }
      });

      setStep(3);
    }
  };

  const cancelPipeline = () => {
    cancelRef.current = true;
    setIsCancelled(true);
  };

  // ── Sync to dashboard ──
  const syncDashboard = async () => {
    setStep(4);
    setSyncStatus("loading");
    await new Promise((r) => setTimeout(r, 2000));
    const ok = Math.random() > 0.15;
    if (ok) {
      setSyncStatus("ok");
      setSyncedUrl("http://localhost:3000/videos/abc123");
    } else {
      setSyncStatus("error");
    }
  };

  const handleSelectFolder = async () => {
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    if (isTauri) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const folder = await invoke<string | null>("select_folder");
        if (folder) {
          setClipsInput(folder);
        }
      } catch (err) {
        console.error("Lỗi chọn thư mục:", err);
      }
    } else {
      const mockPath = "D:\\MockProject\\clips";
      setClipsInput(mockPath);
    }
  };

  const handleSelectFiles = async () => {
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    if (isTauri) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const files = await invoke<string[] | null>("select_files");
        if (files && files.length > 0) {
          setClipsInput(files.join(", "));
        }
      } catch (err) {
        console.error("Lỗi chọn files:", err);
      }
    } else {
      const mockFiles = [
        "D:\\MockProject\\clips\\video1.mp4",
        "D:\\MockProject\\clips\\video2.mp4"
      ];
      setClipsInput(mockFiles.join(", "));
    }
  };

  const resetAll = () => {
    setStep(1);
    setTopic("");
    setLogs([]);
    setPipelineStep(0);
    setResult(null);
    setSyncStatus(null);
    setSyncedUrl("");
    setIsCancelled(false);
  };

  // ══════════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════════
  return (
    <div style={sty.container}>
      {/* Header */}
      <div style={sty.header}>
        <div>
          <h1 style={sty.title}>🎬 Studio</h1>
          <p style={sty.subtitle}>Sản xuất video du lịch bằng AI</p>
        </div>
      </div>

      <StepIndicator current={step} />

      {/* ════ STEP 1 ════ */}
      {step === 1 && (
        <div style={sty.card}>
          <h2 style={sty.cardTitle}>Bước 1 — Nhập nội dung</h2>

          {/* Topic */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>
              🗺️ Chủ đề video <span style={sty.required}>*</span>
            </label>
            <input
              style={sty.topicInput}
              placeholder="VD: Đà Nẵng travel, Phú Quốc resort, Hội An đêm…"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
            />
            <div style={sty.hint}>Nhập tên điểm đến hoặc chủ đề du lịch bạn muốn làm video</div>
          </div>

          {/* Creator */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>👤 Chọn Creator</label>
            <div style={sty.creatorGrid}>
              {CREATORS.map((c) => (
                <div
                  key={c.id}
                  onClick={() => setSelectedCreator(c.id)}
                  style={{
                    ...sty.creatorCard,
                    ...(selectedCreator === c.id ? sty.creatorCardActive : {}),
                  }}
                >
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
            <label style={sty.label}>📐 Chọn Template</label>
            <div style={sty.templateRow}>
              {TEMPLATES.map((t) => (
                <div
                  key={t.id}
                  onClick={() => setSelectedTemplate(t.id)}
                  style={{
                    ...sty.templateCard,
                    ...(selectedTemplate === t.id ? sty.templateCardActive : {}),
                  }}
                >
                  <span style={sty.templateIcon}>{t.icon}</span>
                  <div style={sty.templateRatio}>{t.ratio}</div>
                  <div style={sty.templateLabel}>{t.label}</div>
                  <div style={sty.templateDesc}>{t.desc}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Seeding */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>📍 Địa điểm Seeding (tuỳ chọn)</label>
            <div style={sty.hint}>Thêm quán ăn, khách sạn để AI đề cập trong video</div>
            {seedingItems.map((item) => (
              <div key={item.id} style={sty.seedingRow}>
                <select
                  style={sty.seedingType}
                  value={item.type}
                  onChange={(e) => updateSeeding(item.id, "type", e.target.value)}
                >
                  <option value="restaurant">🍜 Quán</option>
                  <option value="hotel">🏨 Khách sạn</option>
                </select>
                <input
                  style={sty.seedingInput}
                  placeholder="Nhập tên địa điểm…"
                  value={item.value}
                  onChange={(e) => updateSeeding(item.id, "value", e.target.value)}
                />
                <button
                  style={sty.seedingRemove}
                  onClick={() => removeSeeding(item.id)}
                  disabled={seedingItems.length === 1}
                >
                  ✕
                </button>
              </div>
            ))}
            <button style={sty.addSeedingBtn} onClick={addSeeding}>
              + Thêm địa điểm
            </button>
          </div>

          {/* Script Text */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>📝 Kịch bản / Nội dung chi tiết (Tự chọn)</label>
            <textarea
              style={sty.textarea}
              placeholder="Nhập kịch bản gồm 3 phần (Hook, Body, CTA) phân cách bằng xuống dòng. Nếu bỏ trống, AI sẽ tự viết dựa trên Chủ đề ở trên..."
              value={scriptText}
              onChange={(e) => setScriptText(e.target.value)}
            />
          </div>

          {/* Raw Clips */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>🎥 Thư mục hoặc danh sách Video thô (Raw Clips)</label>
            <div style={{ display: "flex", gap: 10 }}>
              <input
                style={{ ...sty.topicInput, flex: 1, padding: "10px 14px", fontSize: 13 }}
                placeholder="VD: D:\ProjectWeb\clips\bien1.mp4, D:\ProjectWeb\clips\bien2.mp4"
                value={clipsInput}
                onChange={(e) => setClipsInput(e.target.value)}
              />
              <button
                type="button"
                onClick={handleSelectFolder}
                style={sty.dialogSelectBtn}
              >
                📁 Chọn thư mục
              </button>
              <button
                type="button"
                onClick={handleSelectFiles}
                style={sty.dialogSelectBtn}
              >
                🎥 Chọn files
              </button>
            </div>
            <div style={sty.hint}>Chọn một thư mục chứa video thô hoặc danh sách các file video. Nếu bỏ trống, hệ thống tự động sinh video placeholder.</div>
          </div>

          {/* Hook Style & Preview */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>🎣 Hiệu ứng Hook (Mở đầu video)</label>
            <div style={{ display: "flex", gap: 12 }}>
              <select
                style={sty.select}
                value={hookStyle}
                onChange={(e) => setHookStyle(e.target.value)}
              >
                <option value="zoom_in">Zoom In (Phóng to chậm)</option>
                <option value="zoom_out">Zoom Out (Thu nhỏ chậm)</option>
                <option value="glitch">RGB Glitch (Nhiễu sóng màu)</option>
                <option value="cinematic_vignette">Cinematic Vignette (Tối góc điện ảnh)</option>
                <option value="text_slide">Animated Hook Text (Chữ chạy thu hút)</option>
              </select>
              <button
                onClick={() => {
                  const desc: Record<string, string> = {
                    zoom_in: "🔍 Phóng to chậm: Clip mở đầu sẽ zoom từ từ vào tâm để tạo cảm giác cuốn hút tò mò.",
                    zoom_out: "🔭 Thu nhỏ chậm: Lùi xa từ từ để tạo cảm giác bao quát đại cảnh điện ảnh.",
                    glitch: "📺 RGB Glitch: Nhấp nháy màu RGB và nhiễu hạt bụi cực kỳ hiện đại, trẻ trung, nhịp nhanh.",
                    cinematic_vignette: "🎬 Vignette: Tối nhẹ 4 góc hình và đẩy tương phản lên cao như phim điện ảnh.",
                    text_slide: "🔤 Animated Text: Tiêu đề chạy từ dưới lên trên và dừng lại ở trung tâm màn hình."
                  };
                  alert(desc[hookStyle] || "Không có mô tả cho hiệu ứng này.");
                }}
                style={sty.previewBtn}
              >
                👁️ Xem trước
              </button>
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

          {/* Mode toggle */}
          <div style={sty.fieldGroup}>
            <label style={sty.label}>🔧 Chế độ chạy</label>
            <div style={sty.modeToggle}>
              <button
                style={{
                  ...sty.modeBtn,
                  ...(mode === "mock" ? sty.modeBtnActive : {}),
                }}
                onClick={() => setMode("mock")}
              >
                ⚡ Tạo nhanh (Mock)
              </button>
              <button
                style={{
                  ...sty.modeBtn,
                  ...(mode === "full" ? sty.modeBtnActive : {}),
                }}
                onClick={() => setMode("full")}
              >
                ⚙️ Pipeline đầy đủ
              </button>
            </div>
            <div style={sty.hint}>
              {mode === "mock"
                ? "Mock mode: tạo data giả lập ngay, không cần API keys"
                : "Full mode: gọi Claude AI + ElevenLabs thật (cần API keys trong Cài đặt)"}
            </div>
          </div>

          <button
            style={{
              ...sty.primaryBtn,
              opacity: !topic.trim() ? 0.5 : 1,
              cursor: !topic.trim() ? "not-allowed" : "pointer",
            }}
            onClick={runPipeline}
            disabled={!topic.trim()}
          >
            ✨ Bắt đầu tạo video
          </button>
        </div>
      )}

      {/* ════ STEP 2 ════ */}
      {step === 2 && (
        <div style={sty.card}>
          <h2 style={sty.cardTitle}>Bước 2 — Đang chạy Pipeline</h2>

          {isCancelled ? (
            <div style={sty.cancelledBox}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🛑</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#ef4444", marginBottom: 8 }}>
                Đã dừng pipeline
              </div>
              <p style={{ color: "#9ca3af", marginBottom: 20 }}>
                Bạn đã huỷ quá trình tạo video.
              </p>
              <button style={sty.secondaryBtn} onClick={resetAll}>
                ← Quay lại bước 1
              </button>
            </div>
          ) : (
            <>
              {/* Spinner */}
              <div style={sty.spinnerWrap}>
                <div style={sty.spinner} />
                <div style={sty.spinnerText}>
                  {pipelineStep < PIPELINE_STEPS.length
                    ? PIPELINE_STEPS[pipelineStep]
                    : "Hoàn tất"}
                  …
                </div>
              </div>

              {/* Pipeline steps */}
              <div style={sty.pipelineSteps}>
                {PIPELINE_STEPS.map((s, i) => (
                  <div key={s} style={sty.pipelineStepRow}>
                    <div
                      style={{
                        ...sty.pipelineStepDot,
                        background:
                          i < pipelineStep
                            ? "#10b981"
                            : i === pipelineStep
                            ? "#6366f1"
                            : "#2a2a2a",
                        boxShadow: i === pipelineStep ? "0 0 8px #6366f1" : "none",
                      }}
                    >
                      {i < pipelineStep ? "✓" : i + 1}
                    </div>
                    <span
                      style={{
                        ...sty.pipelineStepLabel,
                        color:
                          i < pipelineStep
                            ? "#10b981"
                            : i === pipelineStep
                            ? "#a78bfa"
                            : "#4b5563",
                        fontWeight: i === pipelineStep ? 600 : 400,
                      }}
                    >
                      {s}
                    </span>
                    {i === pipelineStep && (
                      <div style={sty.pipelineDots}>
                        <PulsingDots />
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <LogConsole logs={logs} />

              <button style={sty.dangerBtn} onClick={cancelPipeline}>
                🛑 Dừng pipeline
              </button>
            </>
          )}
        </div>
      )}

      {/* ════ STEP 3 ════ */}
      {step === 3 && result && (
        <div style={sty.card}>
          <div style={sty.step3Header}>
            <h2 style={sty.cardTitle}>Bước 3 — Kết quả</h2>
            <div style={sty.successBadge}>✅ Pipeline thành công</div>
          </div>

          {/* Script */}
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

          {/* Captions */}
          <div style={sty.resultSection}>
            <h3 style={sty.resultSectionTitle}>📢 Captions</h3>
            <div style={sty.captionBlock}>
              <div style={sty.captionLabel}>Caption ngắn</div>
              <div style={sty.captionText}>{result.captions.caption_short}</div>
            </div>
            <div style={sty.captionBlock}>
              <div style={sty.captionLabel}>Caption dài</div>
              <div style={sty.captionText}>{result.captions.caption_long}</div>
            </div>

            {/* Hashtags expandable */}
            <div
              style={sty.expandable}
              onClick={() => setExpandedSection(expandedSection === "hashtags" ? null : "hashtags")}
            >
              <span>#{" "}Hashtags ({result.captions.hashtags.length})</span>
              <span>{expandedSection === "hashtags" ? "▲" : "▼"}</span>
            </div>
            {expandedSection === "hashtags" && (
              <div style={sty.hashtagWrap}>
                {result.captions.hashtags.map((h) => (
                  <span key={h} style={sty.hashtagChip}>{h}</span>
                ))}
              </div>
            )}
          </div>

          {/* Image Prompts */}
          <div style={sty.resultSection}>
            <h3 style={sty.resultSectionTitle}>🎨 Image Prompts</h3>
            <div style={sty.imagePromptList}>
              {result.imagePrompts.map((p, i) => (
                <div key={i} style={sty.imagePromptItem}>
                  <div style={sty.imagePromptNum}>{i + 1}</div>
                  <div style={sty.imagePromptText}>{p}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Files */}
          <div style={sty.resultSection}>
            <h3 style={sty.resultSectionTitle}>📁 File xuất</h3>
            <FilePathRow icon="🎥" label="Video" path={result.videoPath} ext=".mp4" />
            <FilePathRow icon="🎙️" label="Audio" path={result.audioPath} ext=".wav" />
          </div>

          {/* Actions */}
          <div style={sty.step3Actions}>
            <button style={sty.secondaryBtn} onClick={resetAll}>
              🔄 Tạo lại
            </button>
            <button style={sty.primaryBtn} onClick={syncDashboard}>
              📤 Đồng bộ lên Dashboard
            </button>
          </div>
        </div>
      )}

      {/* ════ STEP 4 ════ */}
      {step === 4 && (
        <div style={sty.card}>
          <h2 style={sty.cardTitle}>Bước 4 — Đồng bộ lên Dashboard</h2>

          {syncStatus === "loading" && (
            <div style={sty.syncCenter}>
              <div style={sty.syncSpinner} />
              <div style={sty.syncText}>Đang gửi lên Dashboard…</div>
              <div style={sty.syncSub}>Đang kết nối {`http://localhost:3000/api/videos`}</div>
            </div>
          )}

          {syncStatus === "ok" && (
            <div style={sty.syncCenter}>
              <div style={{ fontSize: 64, marginBottom: 16 }}>✅</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#10b981", marginBottom: 8 }}>
                Đồng bộ thành công!
              </div>
              <p style={{ color: "#9ca3af", marginBottom: 12 }}>
                Bài viết đã được tải lên Dashboard.
              </p>
              <div style={sty.urlBox}>
                <span style={{ color: "#818cf8" }}>🔗</span>
                <span style={{ fontSize: 13, color: "#e5e7eb" }}>{syncedUrl}</span>
                <button
                  style={sty.copyBtn}
                  onClick={() => navigator.clipboard?.writeText(syncedUrl)}
                >
                  Copy
                </button>
              </div>
              <button style={{ ...sty.primaryBtn, marginTop: 24 }} onClick={resetAll}>
                ✨ Tạo bài mới
              </button>
            </div>
          )}

          {syncStatus === "error" && (
            <div style={sty.syncCenter}>
              <div style={{ fontSize: 64, marginBottom: 16 }}>❌</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#ef4444", marginBottom: 8 }}>
                Đồng bộ thất bại
              </div>
              <p style={{ color: "#9ca3af", marginBottom: 12 }}>
                Không thể kết nối đến Dashboard. Kiểm tra URL trong Cài đặt.
              </p>
              <div style={sty.errorBox}>
                Error: ECONNREFUSED — Connection refused at http://localhost:3000
              </div>
              <div style={sty.step3Actions}>
                <button style={sty.secondaryBtn} onClick={() => setStep(3)}>
                  ← Quay lại
                </button>
                <button style={sty.primaryBtn} onClick={syncDashboard}>
                  🔄 Thử lại
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── File Path Row ──────────────────────────────────────────────────────────
function FilePathRow({ icon, label, path, ext }: { icon: string; label: string; path: string; ext: string }) {
  const handleOpenFolder = async () => {
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    if (isTauri && path) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("show_in_folder", { path });
      } catch (err) {
        console.error("Lỗi mở thư mục chứa file:", err);
      }
    } else {
      alert(`Chế độ Web: Đường dẫn file là ${path}`);
    }
  };

  return (
    <div style={sty.fileRow}>
      <span style={sty.fileIcon}>{icon}</span>
      <div style={sty.fileInfo}>
        <div style={sty.fileLabel}>{label}</div>
        <div style={sty.filePath}>{path}</div>
      </div>
      <span style={sty.fileExt}>{ext}</span>
      <button 
        style={sty.openFolderBtn} 
        title="Mở thư mục chứa file và bôi đen"
        onClick={handleOpenFolder}
      >
        📂
      </button>
    </div>
  );
}

// ── Pulsing Dots ───────────────────────────────────────────────────────────
function PulsingDots() {
  return (
    <span style={{ display: "inline-flex", gap: 3, marginLeft: 6 }}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: "#6366f1",
            display: "inline-block",
            animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
    </span>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────
const sty: Record<string, any> = {
  container: {
    padding: "28px 32px",
    height: "100%",
    overflowY: "auto",
    boxSizing: "border-box",
    background: "#0f0f0f",
  },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 },
  title: { fontSize: 24, fontWeight: 700, color: "#f1f1f1", margin: 0, letterSpacing: -0.5 },
  subtitle: { fontSize: 13, color: "#6b7280", margin: "4px 0 0" },

  // Step bar
  stepBar: {
    display: "flex",
    alignItems: "center",
    marginBottom: 28,
    padding: "16px 20px",
    background: "#161616",
    borderRadius: 14,
    border: "1px solid #252525",
  },
  stepItem: { display: "flex", flexDirection: "column", alignItems: "center", gap: 6, flexShrink: 0 },
  stepCircle: {
    width: 32,
    height: 32,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 13,
    fontWeight: 700,
    transition: "all 0.3s",
  },
  stepLabel: { fontSize: 11, fontWeight: 500, whiteSpace: "nowrap", transition: "color 0.3s" },
  stepLine: { flex: 1, height: 2, margin: "0 8px", borderRadius: 2, transition: "background 0.3s", marginBottom: 18 },

  // Card
  card: {
    background: "#161616",
    border: "1px solid #252525",
    borderRadius: 16,
    padding: "28px 32px",
  },
  cardTitle: { fontSize: 18, fontWeight: 700, color: "#e5e7eb", margin: "0 0 24px", letterSpacing: -0.3 },

  // Fields
  fieldGroup: { marginBottom: 24 },
  label: { display: "block", fontSize: 13, fontWeight: 600, color: "#d1d5db", marginBottom: 10 },
  required: { color: "#ef4444" },
  hint: { fontSize: 11, color: "#6b7280", marginTop: 6 },

  topicInput: {
    width: "100%",
    padding: "14px 16px",
    fontSize: 16,
    background: "#1e1e1e",
    border: "1px solid #333",
    borderRadius: 12,
    color: "#f1f1f1",
    outline: "none",
    boxSizing: "border-box",
    transition: "border-color 0.2s",
  },

  // Creator grid
  creatorGrid: { display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 },
  creatorCard: {
    position: "relative",
    background: "#1e1e1e",
    border: "2px solid #2a2a2a",
    borderRadius: 12,
    padding: "14px 10px",
    textAlign: "center",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  creatorCardActive: {
    border: "2px solid #6366f1",
    background: "rgba(99,102,241,0.08)",
    boxShadow: "0 0 12px rgba(99,102,241,0.2)",
  },
  creatorEmoji: { fontSize: 28, marginBottom: 8 },
  creatorName: { fontSize: 12, fontWeight: 600, color: "#e5e7eb", marginBottom: 4 },
  creatorSpec: { fontSize: 10, color: "#6b7280", lineHeight: 1.4 },
  creatorCheck: {
    position: "absolute",
    top: 6,
    right: 8,
    width: 18,
    height: 18,
    borderRadius: "50%",
    background: "#6366f1",
    color: "#fff",
    fontSize: 10,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: 700,
  },

  // Template
  templateRow: { display: "flex", gap: 16 },
  templateCard: {
    flex: 1,
    background: "#1e1e1e",
    border: "2px solid #2a2a2a",
    borderRadius: 12,
    padding: "18px",
    textAlign: "center",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  templateCardActive: {
    border: "2px solid #818cf8",
    background: "rgba(129,140,248,0.08)",
    boxShadow: "0 0 12px rgba(129,140,248,0.2)",
  },
  templateIcon: { fontSize: 24, display: "block", marginBottom: 8 },
  templateRatio: { fontSize: 18, fontWeight: 800, color: "#f1f1f1", marginBottom: 4 },
  templateLabel: { fontSize: 13, fontWeight: 600, color: "#d1d5db", marginBottom: 4 },
  templateDesc: { fontSize: 11, color: "#6b7280" },

  // Seeding
  seedingRow: { display: "flex", gap: 8, marginBottom: 8, alignItems: "center" },
  seedingType: {
    flexShrink: 0,
    background: "#1e1e1e",
    border: "1px solid #333",
    borderRadius: 8,
    color: "#d1d5db",
    padding: "8px 10px",
    fontSize: 13,
  },
  seedingInput: {
    flex: 1,
    background: "#1e1e1e",
    border: "1px solid #333",
    borderRadius: 8,
    color: "#f1f1f1",
    padding: "8px 12px",
    fontSize: 13,
    outline: "none",
  },
  seedingRemove: {
    background: "none",
    border: "1px solid #333",
    borderRadius: 8,
    color: "#6b7280",
    padding: "8px 12px",
    cursor: "pointer",
    fontSize: 12,
  },
  addSeedingBtn: {
    background: "none",
    border: "1px dashed #333",
    borderRadius: 8,
    color: "#818cf8",
    padding: "8px 16px",
    cursor: "pointer",
    fontSize: 13,
    width: "100%",
    marginTop: 4,
    transition: "border-color 0.2s",
  },
  textarea: {
    width: "100%",
    background: "#1e1e1e",
    border: "1px solid #333",
    borderRadius: 8,
    color: "#f1f1f1",
    padding: "10px 14px",
    fontSize: 13,
    outline: "none",
    minHeight: 80,
    fontFamily: "Inter, sans-serif",
    resize: "vertical" as const,
  },
  select: {
    background: "#1e1e1e",
    border: "1px solid #333",
    borderRadius: 8,
    color: "#d1d5db",
    padding: "8px 12px",
    fontSize: 13,
    outline: "none",
    width: "100%",
  },
  previewBtn: {
    background: "none",
    border: "1px solid #333",
    borderRadius: 8,
    color: "#a78bfa",
    padding: "8px 14px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
    whiteSpace: "nowrap" as const,
    transition: "all 0.2s",
  },
  dialogSelectBtn: {
    background: "rgba(255,255,255,0.03)",
    border: "1px solid #333",
    borderRadius: 8,
    color: "#a5b4fc",
    padding: "8px 14px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
    whiteSpace: "nowrap" as const,
    transition: "all 0.2s",
  },

  // Mode toggle
  modeToggle: { display: "flex", background: "#1a1a1a", borderRadius: 10, padding: 4, gap: 4, border: "1px solid #252525", width: "fit-content" },
  modeBtn: {
    background: "none",
    border: "none",
    borderRadius: 8,
    color: "#6b7280",
    padding: "10px 20px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
    transition: "all 0.2s",
  },
  modeBtnActive: {
    background: "linear-gradient(135deg, #6366f1, #818cf8)",
    color: "#fff",
    fontWeight: 600,
    boxShadow: "0 2px 8px rgba(99,102,241,0.4)",
  },

  // Buttons
  primaryBtn: {
    width: "100%",
    background: "linear-gradient(135deg, #6366f1 0%, #818cf8 50%, #38bdf8 100%)",
    border: "none",
    borderRadius: 12,
    color: "#fff",
    fontSize: 16,
    fontWeight: 700,
    padding: "16px 24px",
    cursor: "pointer",
    boxShadow: "0 4px 24px rgba(99,102,241,0.4)",
    letterSpacing: 0.3,
    transition: "filter 0.2s, transform 0.15s",
  },
  secondaryBtn: {
    background: "#1e1e1e",
    border: "1px solid #333",
    borderRadius: 12,
    color: "#d1d5db",
    fontSize: 14,
    fontWeight: 600,
    padding: "12px 24px",
    cursor: "pointer",
    transition: "background 0.2s",
  },
  dangerBtn: {
    marginTop: 16,
    background: "rgba(239,68,68,0.1)",
    border: "1px solid #ef444440",
    borderRadius: 12,
    color: "#ef4444",
    fontSize: 14,
    fontWeight: 600,
    padding: "12px 24px",
    cursor: "pointer",
    transition: "background 0.2s",
    width: "100%",
  },

  // Step 2 — Spinner
  spinnerWrap: { display: "flex", flexDirection: "column", alignItems: "center", padding: "32px 0 28px" },
  spinner: {
    width: 64,
    height: 64,
    border: "4px solid #252525",
    borderTop: "4px solid #818cf8",
    borderRadius: "50%",
    animation: "spin 0.9s linear infinite",
    marginBottom: 16,
  },
  spinnerText: { fontSize: 16, fontWeight: 600, color: "#a78bfa" },

  pipelineSteps: {
    display: "flex",
    flexDirection: "column",
    gap: 14,
    marginBottom: 24,
    padding: "20px",
    background: "#1a1a1a",
    borderRadius: 12,
    border: "1px solid #252525",
  },
  pipelineStepRow: { display: "flex", alignItems: "center", gap: 12 },
  pipelineStepDot: {
    width: 28,
    height: 28,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 11,
    fontWeight: 700,
    color: "#fff",
    flexShrink: 0,
    transition: "all 0.3s",
  },
  pipelineStepLabel: { fontSize: 14, transition: "color 0.3s", flex: 1 },
  pipelineDots: { marginLeft: "auto" },

  cancelledBox: { textAlign: "center", padding: "40px 20px" },

  // Log console
  logConsole: {
    background: "#0d0d0d",
    border: "1px solid #252525",
    borderRadius: 12,
    overflow: "hidden",
    marginBottom: 16,
  },
  logHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "10px 14px",
    background: "#1a1a1a",
    borderBottom: "1px solid #252525",
  },
  logTitle: { fontSize: 12, fontWeight: 600, color: "#9ca3af" },
  logCount: { fontSize: 11, color: "#4b5563" },
  logBody: { padding: "12px 14px", maxHeight: 200, overflowY: "auto", fontFamily: "monospace" },
  logLine: { display: "flex", gap: 10, marginBottom: 5, fontSize: 12, lineHeight: 1.5 },
  logTime: { color: "#4b5563", flexShrink: 0, fontSize: 11 },
  logText: { wordBreak: "break-all" },

  // Step 3
  step3Header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 },
  successBadge: {
    background: "rgba(16,185,129,0.1)",
    border: "1px solid #10b98140",
    color: "#10b981",
    borderRadius: 20,
    padding: "6px 16px",
    fontSize: 13,
    fontWeight: 600,
  },

  resultSection: { marginBottom: 24 },
  resultSectionTitle: { fontSize: 14, fontWeight: 600, color: "#9ca3af", margin: "0 0 14px", textTransform: "uppercase", letterSpacing: 0.5 },

  scriptGrid: { display: "flex", flexDirection: "column", gap: 12 },
  scriptBlock: {
    borderRadius: 12,
    padding: "16px 18px",
    border: "1px solid",
    transition: "transform 0.15s",
  },
  scriptBlockLabel: { fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 },
  scriptBlockText: { fontSize: 14, color: "#e5e7eb", lineHeight: 1.6, margin: 0 },

  captionBlock: {
    background: "#1a1a1a",
    borderRadius: 10,
    padding: "12px 16px",
    marginBottom: 10,
    border: "1px solid #252525",
  },
  captionLabel: { fontSize: 11, color: "#6b7280", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 },
  captionText: { fontSize: 13, color: "#e5e7eb", lineHeight: 1.6 },

  expandable: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "12px 16px",
    background: "#1a1a1a",
    borderRadius: 10,
    border: "1px solid #252525",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
    color: "#d1d5db",
    marginBottom: 8,
    transition: "background 0.2s",
  },
  hashtagWrap: { display: "flex", flexWrap: "wrap", gap: 8, padding: "12px 0" },
  hashtagChip: {
    background: "rgba(99,102,241,0.12)",
    border: "1px solid rgba(99,102,241,0.3)",
    color: "#818cf8",
    borderRadius: 20,
    padding: "4px 12px",
    fontSize: 12,
    fontWeight: 500,
  },

  imagePromptList: { display: "flex", flexDirection: "column", gap: 10 },
  imagePromptItem: {
    display: "flex",
    gap: 12,
    padding: "12px 14px",
    background: "#1a1a1a",
    borderRadius: 10,
    border: "1px solid #252525",
    alignItems: "flex-start",
  },
  imagePromptNum: {
    width: 24,
    height: 24,
    borderRadius: "50%",
    background: "linear-gradient(135deg,#6366f1,#818cf8)",
    color: "#fff",
    fontSize: 11,
    fontWeight: 700,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  imagePromptText: { fontSize: 13, color: "#d1d5db", lineHeight: 1.5, fontStyle: "italic" },

  fileRow: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "12px 16px",
    background: "#1a1a1a",
    borderRadius: 10,
    border: "1px solid #252525",
    marginBottom: 10,
  },
  fileIcon: { fontSize: 22, flexShrink: 0 },
  fileInfo: { flex: 1, minWidth: 0 },
  fileLabel: { fontSize: 13, fontWeight: 600, color: "#e5e7eb", marginBottom: 2 },
  filePath: { fontSize: 11, color: "#6b7280", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  fileExt: {
    background: "#252525",
    color: "#9ca3af",
    borderRadius: 6,
    padding: "3px 8px",
    fontSize: 11,
    fontWeight: 600,
    flexShrink: 0,
  },
  openFolderBtn: {
    background: "none",
    border: "1px solid #333",
    borderRadius: 8,
    padding: "6px 10px",
    cursor: "pointer",
    fontSize: 16,
    color: "#6b7280",
    flexShrink: 0,
  },

  step3Actions: { display: "flex", gap: 12, marginTop: 24 },

  // Step 4
  syncCenter: { display: "flex", flexDirection: "column", alignItems: "center", padding: "40px 20px", textAlign: "center" },
  syncSpinner: {
    width: 56,
    height: 56,
    border: "4px solid #252525",
    borderTop: "4px solid #818cf8",
    borderRight: "4px solid #38bdf8",
    borderRadius: "50%",
    animation: "spin 0.9s linear infinite",
    marginBottom: 20,
  },
  syncText: { fontSize: 18, fontWeight: 700, color: "#e5e7eb", marginBottom: 8 },
  syncSub: { fontSize: 12, color: "#6b7280", fontFamily: "monospace" },
  urlBox: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    background: "#1a1a1a",
    border: "1px solid #333",
    borderRadius: 10,
    padding: "10px 14px",
    maxWidth: 480,
    width: "100%",
  },
  copyBtn: {
    marginLeft: "auto",
    background: "none",
    border: "1px solid #333",
    borderRadius: 6,
    color: "#818cf8",
    fontSize: 12,
    padding: "4px 10px",
    cursor: "pointer",
  },
  errorBox: {
    background: "rgba(239,68,68,0.08)",
    border: "1px solid #ef444440",
    borderRadius: 10,
    padding: "10px 16px",
    fontSize: 12,
    color: "#ef4444",
    fontFamily: "monospace",
    maxWidth: 480,
    width: "100%",
    textAlign: "left",
  },
};

// ── Global keyframes (injected once) ──────────────────────────────────────
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
