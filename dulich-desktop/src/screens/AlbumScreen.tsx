import { useState, useEffect, useRef } from "react";
import { invoke, convertFileSrc } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

interface LogLine {
  id: string;
  time: string;
  type: "info" | "success" | "warn" | "error";
  text: string;
}

const CREATORS = [
  { id: "lan_anh", name: "Lan Anh" },
  { id: "minh_tuan", name: "Minh Tuấn" },
  { id: "thu_ha", name: "Thu Hà" },
  { id: "duc_anh", name: "Đức Anh" },
  { id: "ngoc_mai", name: "Ngọc Mai" },
];

const FORMAT_LABELS: Record<string, string> = {
  story: "Story (1080x1920)",
  feed_square: "Feed Vuông (1080x1080)",
  feed_portrait: "Feed Portrait (1080x1350)",
  reels_cover: "Reels Cover (1080x1920)",
  youtube_thumb: "YouTube Thumb (1280x720)",
  facebook_cover: "Facebook Cover (820x312)",
  pinterest: "Pinterest Pin (1000x1500)",
  carousel_slide: "Carousel (1080x1080)",
  blog_header: "Blog Header (1200x630)",
  seeding_card: "Seeding Card (800x800)",
};

export default function AlbumScreen() {
  const [activeTab, setActiveTab] = useState<"create" | "manage">("create");
  const [step, setStep] = useState<1 | 2 | 3>(1); // 1: Input, 2: Running, 3: Result
  const [topic, setTopic] = useState("");
  const [title, setTitle] = useState("Review Phú Quốc Cực Chất");
  const [subtitle, setSubtitle] = useState("Trải nghiệm thiên đường đảo ngọc cùng Lan Anh");
  const [selectedCreator, setSelectedCreator] = useState("lan_anh");
  const [canvaFrame, setCanvaFrame] = useState("");
  const [selectedFrameId, setSelectedFrameId] = useState<string>("auto");
  const [learnedFrames, setLearnedFrames] = useState<any[]>([]);
  const [loadingFrames, setLoadingFrames] = useState(false);

  const [logs, setLogs] = useState<LogLine[]>([]);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState("Đang khởi động...");
  const [resultImages, setResultImages] = useState<Record<string, string>>({});
  const [zoomImage, setZoomImage] = useState<string | null>(null);

  const [errorMsg, setErrorMsg] = useState("");
  const logConsoleBottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const STORAGE_KEY = "dulich_learned_frames";

  const isTauri = (): boolean =>
    typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;

  // ── Web-mode: load/save frames to localStorage ──
  const getWebFrames = (): any[] => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); } catch { return []; }
  };
  const saveWebFrames = (frames: any[]) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(frames));
  };

  useEffect(() => {
    if (logConsoleBottomRef.current) {
      logConsoleBottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs.length]);

  // Load learned frames on mount + when tab switches to manage
  useEffect(() => {
    if (activeTab === "manage" || activeTab === "create") {
      loadLearnedFrames();
    }
  }, [activeTab]);

  const loadLearnedFrames = async () => {
    try {
      setLoadingFrames(true);
      if (isTauri()) {
        const resultStr = await invoke<string>("list_learned_frames", {
          creatorId: "",
          formatName: "",
        });
        const parsed = JSON.parse(resultStr);
        if (parsed.success && Array.isArray(parsed.data)) {
          setLearnedFrames(parsed.data);
        }
      } else {
        setLearnedFrames(getWebFrames());
      }
    } catch (e) {
      console.warn("Could not load learned frames:", e);
    } finally {
      setLoadingFrames(false);
    }
  };

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";

    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });

      const newFrame: any = {
        frame_id: "web_" + Date.now(),
        name: file.name.replace(/\.[^/.]+$/, ""),
        thumbnail_path: dataUrl,
        width: 1080,
        height: 1920,
        aspect_ratio: "9:16",
        compatible_formats: Object.keys(FORMAT_LABELS),
        style_tags: ["web-upload"],
        color_palette: [],
        usage_count: 0,
        uploaded_by: selectedCreator,
      };

      const frames = [...getWebFrames(), newFrame];
      saveWebFrames(frames);
      setLearnedFrames(frames);
      alert(`Đã thêm khung ảnh "${file.name}" thành công!`);
    } catch (err: any) {
      alert("Lỗi đọc file: " + err.message);
    }
  };

  const handleUploadFrames = async () => {
    try {
      if (isTauri()) {
        const selected = await invoke<string | null>("select_single_file", {
          allowedExtensions: ["zip", "png"],
        });
        if (!selected) return;

        const resultStr = await invoke<string>("upload_canva_frames", {
          zipPath: selected,
          creatorId: selectedCreator,
        });
        const parsed = JSON.parse(resultStr);
        if (parsed.success) {
          await loadLearnedFrames();
          alert(`Đã học ${parsed.data.total || 1} khung ảnh thành công!`);
        } else {
          alert("Lỗi: " + (parsed.data || "Không rõ"));
        }
      } else {
        // Web mode: use file input
        fileInputRef.current?.click();
      }
    } catch (e: any) {
      alert("Lỗi upload: " + e.message);
    }
  };

  const handleDeleteFrame = async (frameId: string) => {
    try {
      if (isTauri()) {
        await invoke<string>("delete_learned_frame", { frameId });
      } else {
        const frames = getWebFrames().filter((f) => f.frame_id !== frameId);
        saveWebFrames(frames);
      }
      setLearnedFrames((prev) => prev.filter((f) => f.frame_id !== frameId));
    } catch (e: any) {
      alert("Lỗi xóa: " + e.message);
    }
  };

  const runAlbumPipeline = async () => {
    if (!topic.trim()) {
      setErrorMsg("Vui lòng nhập chủ đề để AI tìm kiếm hình ảnh phù hợp.");
      return;
    }

    setStep(2);
    setLogs([]);
    setProgress(0);
    setStatusText("Đang khởi động pipeline...");
    setErrorMsg("");

    if (isTauri()) {
      try {
        const unlisten = await listen<any>("pipeline-log", (event) => {
          const logPayload = event.payload;
          setLogs((prev) => [
            ...prev,
            {
              id: Math.random().toString(),
              time: logPayload.time,
              type: (logPayload.level === "warn" ? "warn" : logPayload.level === "warning" ? "warn" : logPayload.level) as any,
              text: logPayload.text,
            }
          ]);

          const text = logPayload.text;
          if (text.includes("tìm thấy ảnh nền")) {
            setProgress(25);
            setStatusText("Đang thiết lập background du lịch...");
          } else if (text.includes("định dạng ảnh seeding")) {
            setProgress(40);
            setStatusText("Đang vẽ layout Pillow seeding...");
          } else if (text.includes("Đã tạo format")) {
            setProgress((prev) => Math.min(90, prev + 5));
            setStatusText(`Đang xuất ảnh: ${text.split("'")[1] || ""}`);
          } else if (text.includes("Job tạo Album seeding hoàn tất")) {
            setProgress(100);
            setStatusText("Hoàn tất xuất album!");
          }
        });

        const resultJsonStr = await invoke<string>("run_album_pipeline", {
          topic,
          title,
          subtitle,
          frame: canvaFrame,
          creatorId: selectedCreator,
          frameId: selectedFrameId === "auto" ? "" : selectedFrameId,
        });

        unlisten();

        const runResult = JSON.parse(resultJsonStr);
        setResultImages(runResult.images || {});
        setStep(3);

      } catch (err: any) {
        setLogs((prev) => [
          ...prev,
          {
            id: Math.random().toString(),
            time: new Date().toLocaleTimeString(),
            type: "error",
            text: `❌ Lỗi: ${err.message || err}`,
          }
        ]);
        setErrorMsg(err.toString());
      }
    } else {
      // ── Mock mode: generate canvas previews using selected frame ──
      const formatList = Object.keys(FORMAT_LABELS);
      const selectedFrame = selectedFrameId && selectedFrameId !== "auto"
        ? learnedFrames.find(f => f.frame_id === selectedFrameId) || null
        : null;

      const mockLogLines = [
        `[AlbumPipeline] Khởi động Image Pipeline cho chủ đề: ${topic}`,
        `[Pexels] ✓ Tìm thấy ảnh nền du lịch từ stock`,
        `[Composer] Thiết lập kích thước vẽ...`,
        ...formatList.map(fmt => `[Composer] ✓ Đã tạo format '${fmt}'`),
        "[AlbumPipeline] ✓ Job tạo Album seeding hoàn tất thành công!"
      ];

      const generatedImages: Record<string, string> = {};

      for (let i = 0; i < formatList.length; i++) {
        const fmt = formatList[i];
        const nowStr = new Date().toLocaleTimeString();
        setLogs((prev) => [
          ...prev,
          {
            id: Math.random().toString(),
            time: nowStr,
            type: i < 2 ? "info" : "success",
            text: mockLogLines[Math.min(i, mockLogLines.length - 1)],
          }
        ]);
        setProgress(Math.floor(((i + 1) / formatList.length) * 100));
        setStatusText(`Đang tạo ${FORMAT_LABELS[fmt] || fmt}...`);

        // Generate canvas preview
        generatedImages[fmt] = await generateFormatPreview(fmt, selectedFrame, title, subtitle, topic);
        await new Promise((r) => setTimeout(r, 300));
      }

      setResultImages(generatedImages);
      setStep(3);
    }
  };

  // ── Generate a canvas-based preview image for each format ──
  const generateFormatPreview = async (
    format: string,
    frame: any | null,
    title: string,
    subtitle: string,
    topic: string
  ): Promise<string> => {
    const dims: Record<string, [number, number]> = {
      story: [540, 960],
      feed_square: [540, 540],
      feed_portrait: [540, 675],
      reels_cover: [540, 960],
      youtube_thumb: [640, 360],
      facebook_cover: [540, 206],
      pinterest: [500, 750],
      carousel_slide: [540, 540],
      blog_header: [600, 315],
      seeding_card: [400, 400],
    };

    const [w, h] = dims[format] || [540, 540];
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d")!;

    // Background
    if (frame?.thumbnail_path?.startsWith("data:")) {
      const img = await loadImage(frame.thumbnail_path);
      ctx.drawImage(img, 0, 0, w, h);
      ctx.fillStyle = "rgba(0,0,0,0.35)";
      ctx.fillRect(0, 0, w, h);
    } else {
      const grad = ctx.createLinearGradient(0, 0, w, h);
      grad.addColorStop(0, "#1e1b4b");
      grad.addColorStop(0.5, "#312e81");
      grad.addColorStop(1, "#831843");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, w, h);

      // Subtle pattern
      ctx.fillStyle = "rgba(255,255,255,0.03)";
      for (let x = 0; x < w; x += 20) {
        for (let y = 0; y < h; y += 20) {
          if ((x + y) % 40 === 0) ctx.fillRect(x, y, 8, 8);
        }
      }
    }

    // Overlay format label and title
    const isWide = w > h;
    const fontSize = Math.min(w, h) * (isWide ? 0.12 : 0.07);

    // Format badge
    ctx.fillStyle = "rgba(124, 58, 237, 0.85)";
    ctx.beginPath();
    const badgeSize = Math.min(w * 0.35, 140);
    ctx.roundRect(10, 10, badgeSize, 22, 6);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.font = `bold 11px sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText((FORMAT_LABELS[format] || format).toUpperCase(), 10 + badgeSize / 2, 26);

    // Title
    ctx.fillStyle = "#ffffff";
    ctx.font = `bold ${fontSize}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    const lines = wrapText(ctx, title, w * 0.85);
    const lineHeight = fontSize * 1.3;
    const startY = h / 2 - (lines.length - 1) * lineHeight / 2 - 10;

    lines.forEach((line, i) => {
      ctx.fillText(line, w / 2, startY + i * lineHeight);
    });

    // Subtitle
    if (subtitle) {
      const subSize = Math.max(11, fontSize * 0.55);
      ctx.fillStyle = "rgba(255,255,255,0.8)";
      ctx.font = `${subSize}px sans-serif`;
      ctx.fillText(subtitle, w / 2, startY + lines.length * lineHeight + 8);
    }

    // Topic tag
    ctx.fillStyle = "rgba(255,255,255,0.12)";
    ctx.beginPath();
    ctx.roundRect(w / 2 - 50, h - 28, 100, 18, 9);
    ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,0.5)";
    ctx.font = "9px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(`#${topic.split(" ")[0]}`, w / 2, h - 16);

    return canvas.toDataURL("image/png");
  };

  const loadImage = (src: string): Promise<HTMLImageElement> => {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = src;
    });
  };

  const wrapText = (ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] => {
    if (ctx.measureText(text).width <= maxWidth) return [text];
    const words = text.split(" ");
    const lines: string[] = [];
    let current = "";
    for (const word of words) {
      const test = current ? current + " " + word : word;
      if (ctx.measureText(test).width > maxWidth && current) {
        lines.push(current);
        current = word;
      } else {
        current = test;
      }
    }
    if (current) lines.push(current);
    return lines.length ? lines : [text];
  };

  const handleOpenFolder = async () => {
    try {
      // Open output/albums folder
      await invoke("list_directory", { path: "./output/albums" });
      alert("Đã mở thư mục output/albums trên máy local.");
    } catch (e) {
      alert("Hãy kiểm tra thư mục: dulich-pipeline/output/albums/");
    }
  };

  const resetAll = () => {
    setStep(1);
    setTopic("");
    setLogs([]);
    setProgress(0);
    setResultImages({});
  };

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>🖼️ Tạo Album Ảnh Seeding</h1>
        <p style={styles.subtitle}>Tạo 10 kích thước ảnh chuẩn seeding (mô phỏng, không cần AI). Upload khung ảnh của bạn và xem kết quả ngay trên trình duyệt.</p>
      </header>

      {errorMsg && <div style={styles.errorAlert}>⚠ {errorMsg}</div>}

      {/* --- TABS --- */}
      {step === 1 && (
        <div style={styles.tabBar}>
          <button
            onClick={() => setActiveTab("create")}
            style={{
              ...styles.tabButton,
              borderBottom: activeTab === "create" ? "2px solid #7c3aed" : "2px solid transparent",
              color: activeTab === "create" ? "#ffffff" : "#6b7280",
            }}
          >
            📸 Tạo Album
          </button>
          <button
            onClick={() => setActiveTab("manage")}
            style={{
              ...styles.tabButton,
              borderBottom: activeTab === "manage" ? "2px solid #7c3aed" : "2px solid transparent",
              color: activeTab === "manage" ? "#ffffff" : "#6b7280",
            }}
          >
            🎨 Quản lý Khung Ảnh
          </button>
        </div>
      )}

      {/* --- STEP 1: INPUT --- */}
      {step === 1 && activeTab === "create" && (
        <div style={styles.glassPanel}>
          <h2 style={styles.panelTitle}>Thông số thiết kế Album</h2>

          <div style={styles.formGrid}>
            <div style={styles.formGroup}>
              <label style={styles.label}>🗺️ Chủ đề hình ảnh (Từ khoá để tạo ảnh mô phỏng)</label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="VD: Phú Quốc resort, cafe Đà Lạt view đẹp, món ăn Hà Nội..."
                style={styles.input}
              />
              <small style={styles.hint}>Dùng từ khóa để gắn hashtag và mô phỏng ảnh seeding.</small>
            </div>

            <div style={styles.formRow}>
              <div style={{ ...styles.formGroup, flex: 1.2 }}>
                <label style={styles.label}>🔤 Tiêu đề chính (Title)</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Nhập tiêu đề lớn in đậm..."
                  style={styles.input}
                />
              </div>

              <div style={{ ...styles.formGroup, flex: 1 }}>
                <label style={styles.label}>👤 Người tạo (Creator)</label>
                <select
                  value={selectedCreator}
                  onChange={(e) => setSelectedCreator(e.target.value)}
                  style={styles.select}
                >
                  {CREATORS.map(c => (
                    <option key={c.id} value={c.id} style={styles.option}>{c.name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>✍️ Phụ đề / Đoạn giới thiệu ngắn (Subtitle)</label>
              <input
                type="text"
                value={subtitle}
                onChange={(e) => setSubtitle(e.target.value)}
                placeholder="Nhập mô tả phụ..."
                style={styles.input}
              />
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>🎨 Khung ảnh</label>
              <div style={styles.frameSelectorRow}>
                <select
                  value={selectedFrameId}
                  onChange={(e) => setSelectedFrameId(e.target.value)}
                  style={{ ...styles.select, flex: 1 }}
                >
                  <option value="auto">🤖 AI Tự Chọn Khung</option>
                  <option value="">🔲 Khung mặc định (Chuyển màu tím)</option>
                  {learnedFrames.map((f) => (
                    <option key={f.frame_id} value={f.frame_id}>
                      🖼️ {f.name} ({f.width}x{f.height})
                    </option>
                  ))}
                </select>
                {learnedFrames.length > 0 && selectedFrameId !== "auto" && selectedFrameId && (
                  <div style={styles.framePreview}>
                    {(() => {
                      const frame = learnedFrames.find(f => f.frame_id === selectedFrameId);
                      return frame ? (
                        <div>
                          <img src={frame.thumbnail_path?.startsWith("data:") ? frame.thumbnail_path : convertFileSrc(frame.thumbnail_path)} alt={frame.name} style={styles.frameThumb} />
                          <div style={styles.frameTags}>
                            {frame.style_tags?.map((t: string) => <span key={t} style={styles.tag}>#{t}</span>)}
                          </div>
                        </div>
                      ) : null;
                    })()}
                  </div>
                )}
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>🎨 Khung Canva tùy chọn (Đường dẫn ảnh PNG)</label>
              <input
                type="text"
                value={canvaFrame}
                onChange={(e) => setCanvaFrame(e.target.value)}
                placeholder="Đường dẫn frame PNG (Bỏ trống để dùng khung đã chọn ở trên)"
                style={styles.input}
              />
            </div>

            <button onClick={runAlbumPipeline} style={styles.generateBtn}>
              ✨ Bắt đầu xuất 10 ảnh Seeding
            </button>
          </div>
        </div>
      )}

      {/* --- FRAME MANAGEMENT TAB --- */}
      {step === 1 && activeTab === "manage" && (
        <div style={styles.glassPanel}>
          <h2 style={styles.panelTitle}>🎨 Quản lý Khung Ảnh Canva</h2>
          <p style={{ ...styles.hint, marginBottom: 16 }}>
            Upload file PNG để làm khung nền cho ảnh seeding. (Hiện tại đang chạy chế độ mô phỏng, chưa có AI.)
          </p>

          <button onClick={handleUploadFrames} style={styles.generateBtn}>
            📤 Upload Khung Ảnh (ZIP/PNG)
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".zip,.png,.jpg,.jpeg"
            style={{ display: "none" }}
            onChange={handleFileSelected}
          />

          <div style={{ height: 20 }} />

          {loadingFrames ? (
            <div style={{ textAlign: "center", padding: 40, color: "#9ca3af" }}>
              Đang tải danh sách khung ảnh...
            </div>
          ) : learnedFrames.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: "#6b7280" }}>
              <p>Chưa có khung ảnh nào.</p>
              <p style={{ fontSize: 12 }}>Upload file PNG để làm khung nền ảnh seeding.</p>
            </div>
          ) : (
            <div style={styles.frameGrid}>
              {learnedFrames.map((frame) => (
                <div key={frame.frame_id} style={styles.frameCard}>
                  <div style={styles.frameCardPreview}>
                    {frame.thumbnail_path ? (
                      <img
                        src={frame.thumbnail_path?.startsWith("data:") ? frame.thumbnail_path : convertFileSrc(frame.thumbnail_path)}
                        alt={frame.name}
                        style={styles.frameCardThumb}
                      />
                    ) : (
                      <div style={{ color: "#6b7280", fontSize: 12 }}>No preview</div>
                    )}
                  </div>
                  <div style={styles.frameCardInfo}>
                    <span style={styles.frameCardName}>{frame.name}</span>
                    <span style={styles.frameCardDims}>{frame.width}x{frame.height}</span>
                    <div style={styles.frameCardTags}>
                      {frame.style_tags?.slice(0, 3).map((t: string) => (
                        <span key={t} style={styles.tag}>#{t}</span>
                      ))}
                    </div>
                    <span style={styles.frameCardUsage}>Đã dùng: {frame.usage_count} lần</span>
                  </div>
                  <button
                    onClick={() => handleDeleteFrame(frame.frame_id)}
                    style={styles.frameCardDelete}
                    title="Xóa khung"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* --- STEP 2: RUNNING --- */}
      {step === 2 && (
        <div style={styles.glassPanel}>
          <h2 style={styles.panelTitle}>⚙️ Đang xử lý Album ảnh...</h2>
          
          <div style={styles.progressSection}>
            <div style={styles.progressBarBg}>
              <div style={{ ...styles.progressBarFill, width: `${progress}%` }} />
            </div>
            <div style={styles.progressMeta}>
              <span style={styles.progressStatus}>{statusText}</span>
              <span style={styles.progressPercent}>{progress}%</span>
            </div>
          </div>

          {/* Console logs */}
          <div style={styles.consoleBox}>
            <div style={styles.consoleHeader}>📟 Console Outputs</div>
            <div style={styles.consoleBody}>
              {logs.map((l, index) => {
                const color = l.type === "success" ? "#10b981" : l.type === "error" ? "#ef4444" : l.type === "warn" ? "#f59e0b" : "#9ca3af";
                return (
                  <div key={index} style={{ ...styles.consoleLine, color }}>
                    <span style={styles.consoleTime}>{l.time}</span>
                    <span>{l.text}</span>
                  </div>
                );
              })}
              <div ref={logConsoleBottomRef} />
            </div>
          </div>
        </div>
      )}

      {/* --- STEP 3: RESULT GALLERY --- */}
      {step === 3 && (
        <div style={styles.resultContainer}>
          <div style={styles.resultHeaderRow}>
            <h2 style={styles.panelTitle}>🎉 Kết quả: 10 ảnh Seeding</h2>
            <div style={styles.resultActions}>
              <button onClick={handleOpenFolder} style={styles.secondaryBtn}>📁 Thư mục đầu ra</button>
              <button onClick={resetAll} style={styles.primaryBtn}>← Làm album mới</button>
            </div>
          </div>

          <div style={styles.galleryGrid}>
            {Object.entries(resultImages).map(([format, path]) => {
              const isDataUrl = typeof path === "string" && path.startsWith("data:");
              const isMock = !isDataUrl && (path === "mock_placeholder" || path.includes("album_mock_"));
              const imageUrl = isDataUrl ? path : (!isMock ? convertFileSrc(path) : null);
              return (
                <div key={format} style={styles.galleryCard}>
                  <div
                    onClick={() => setZoomImage(format)}
                    style={{
                      ...styles.imagePreviewBox,
                      background: isMock
                        ? "linear-gradient(135deg, #4f46e5, #ec4899)"
                        : "rgba(0,0,0,0.4)"
                    }}
                  >
                    {isMock ? (
                      <div style={styles.mockOverlayText}>
                        <span style={styles.mockLabel}>{FORMAT_LABELS[format] || format}</span>
                        <p style={styles.mockSubTitle}>{title}</p>
                      </div>
                    ) : imageUrl ? (
                      <img src={imageUrl} alt={format} style={styles.imagePreview} />
                    ) : (
                      <span style={{ fontSize: 13, color: "#fff" }}>🖼️ {FORMAT_LABELS[format] || format}</span>
                    )}
                  </div>
                  <div style={styles.cardInfo}>
                    <span style={styles.cardTitle}>{FORMAT_LABELS[format] || format}</span>
                    <span style={styles.cardPath}>{isDataUrl ? "Canvas preview" : isMock ? "Generated mock" : path.split("\\").pop()}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ZOOM MODAL */}
      {zoomImage && (
        <div onClick={() => setZoomImage(null)} style={styles.modal}>
          <div onClick={(e) => e.stopPropagation()} style={styles.modalContent}>
            <button onClick={() => setZoomImage(null)} style={styles.modalClose}>✕</button>
            <h3 style={styles.modalTitle}>{FORMAT_LABELS[zoomImage] || zoomImage}</h3>
            
            <div style={styles.modalImagePlaceholder}>
              {(() => {
                const imgPath = resultImages[zoomImage];
                const isDataUrl = imgPath?.startsWith("data:");
                const isMock = !isDataUrl && (!imgPath || imgPath === "mock_placeholder" || imgPath.includes("album_mock_"));
                return isMock ? (
                  <div style={styles.modalMockCard}>
                    <span style={styles.modalMockIcon}>🌴</span>
                    <h1 style={styles.modalMockTitle}>{title}</h1>
                    <p style={styles.modalMockSub}>{subtitle}</p>
                    <span style={styles.modalMockHash}>#seeding #travel #vietnam</span>
                  </div>
                ) : (
                  <img
                    src={isDataUrl ? imgPath : convertFileSrc(imgPath)}
                    alt={zoomImage}
                    style={styles.modalImage}
                  />
                );
              })()}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    padding: 24,
    color: "#f3f4f6",
    fontFamily: "Inter, sans-serif",
    height: "100%",
    overflowY: "auto" as const,
  },
  imagePreview: {
    width: "100%",
    height: "100%",
    objectFit: "cover" as const,
  },
  modalImage: {
    maxWidth: "100%",
    maxHeight: "100%",
    objectFit: "contain" as const,
    borderRadius: 8,
  },
  header: {
    marginBottom: 24,
  },
  title: {
    fontSize: 26,
    fontWeight: 700,
    color: "#ffffff",
    margin: 0,
  },
  subtitle: {
    fontSize: 14,
    color: "#9ca3af",
    marginTop: 6,
    lineHeight: 1.5,
  },
  glassPanel: {
    backgroundColor: "rgba(17, 12, 46, 0.4)",
    backdropFilter: "blur(16px)",
    borderRadius: 16,
    padding: 24,
    border: "1px solid rgba(255, 255, 255, 0.06)",
    boxShadow: "0 8px 32px 0 rgba(0, 0, 0, 0.3)",
  },
  panelTitle: {
    fontSize: 17,
    fontWeight: 600,
    color: "#ffffff",
    margin: 0,
  },
  formGrid: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 18,
    marginTop: 18,
  },
  formRow: {
    display: "flex",
    gap: 16,
  },
  formGroup: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 6,
  },
  label: {
    fontSize: 13,
    fontWeight: 500,
    color: "#d1d5db",
  },
  input: {
    backgroundColor: "rgba(255, 255, 255, 0.04)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    borderRadius: 8,
    color: "#ffffff",
    fontSize: 13,
    padding: "10px 14px",
    outline: "none",
    width: "100%",
  },
  select: {
    backgroundColor: "#161233",
    border: "1px solid rgba(255, 255, 255, 0.15)",
    borderRadius: 8,
    color: "#ffffff",
    fontSize: 13,
    padding: "10px 14px",
    outline: "none",
  },
  option: {
    backgroundColor: "#161233",
    color: "#ffffff",
  },
  hint: {
    fontSize: 11,
    color: "#6b7280",
  },
  generateBtn: {
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    border: "none",
    borderRadius: 10,
    fontSize: 14,
    fontWeight: 600,
    padding: "14px 28px",
    cursor: "pointer",
    boxShadow: "0 4px 16px rgba(124, 58, 237, 0.3)",
    transition: "background-color 0.2s",
    marginTop: 8,
  },
  progressSection: {
    marginTop: 20,
    marginBottom: 20,
  },
  progressBarBg: {
    width: "100%",
    height: 8,
    backgroundColor: "rgba(255, 255, 255, 0.05)",
    borderRadius: 4,
    overflow: "hidden",
  },
  progressBarFill: {
    height: "100%",
    background: "linear-gradient(90deg, #7c3aed, #a78bfa)",
    transition: "width 0.4s ease",
  },
  progressMeta: {
    display: "flex",
    justifyContent: "space-between",
    marginTop: 8,
    fontSize: 12,
  },
  progressStatus: {
    color: "#a78bfa",
    fontWeight: 500,
  },
  progressPercent: {
    color: "#ffffff",
    fontWeight: 600,
  },
  consoleBox: {
    backgroundColor: "#080710",
    borderRadius: 12,
    border: "1px solid rgba(255, 255, 255, 0.05)",
    overflow: "hidden",
  },
  consoleHeader: {
    padding: "10px 16px",
    backgroundColor: "rgba(255, 255, 255, 0.02)",
    borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
    fontSize: 11.5,
    fontWeight: 600,
    color: "#6b7280",
    textTransform: "uppercase" as const,
  },
  consoleBody: {
    padding: 16,
    maxHeight: 220,
    overflowY: "auto" as const,
    fontFamily: "monospace",
    fontSize: 12,
    display: "flex",
    flexDirection: "column" as const,
    gap: 6,
  },
  consoleLine: {
    display: "flex",
    gap: 12,
  },
  consoleTime: {
    color: "#4b5563",
    flexShrink: 0,
  },
  resultContainer: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 20,
  },
  resultHeaderRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  resultActions: {
    display: "flex",
    gap: 12,
  },
  primaryBtn: {
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    border: "none",
    borderRadius: 8,
    padding: "10px 20px",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  secondaryBtn: {
    backgroundColor: "transparent",
    color: "#ffffff",
    border: "1px solid rgba(255, 255, 255, 0.15)",
    borderRadius: 8,
    padding: "10px 20px",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  galleryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
    gap: 20,
  },
  galleryCard: {
    backgroundColor: "rgba(255, 255, 255, 0.02)",
    borderRadius: 12,
    border: "1px solid rgba(255, 255, 255, 0.05)",
    overflow: "hidden",
    cursor: "pointer",
    transition: "transform 0.2s",
  },
  imagePreviewBox: {
    width: "100%",
    height: 180,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    position: "relative" as const,
    overflow: "hidden",
  },
  mockOverlayText: {
    position: "absolute" as const,
    bottom: 12,
    left: 12,
    right: 12,
  },
  mockLabel: {
    fontSize: 11,
    fontWeight: 700,
    color: "#a78bfa",
    textTransform: "uppercase" as const,
  },
  mockSubTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: "#ffffff",
    margin: "4px 0 0 0",
  },
  cardInfo: {
    padding: 12,
    display: "flex",
    flexDirection: "column" as const,
    gap: 2,
  },
  cardTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: "#ffffff",
  },
  cardPath: {
    fontSize: 10,
    color: "#6b7280",
    fontFamily: "monospace",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  errorAlert: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    border: "1px solid #ef4444",
    borderRadius: 8,
    color: "#fca5a5",
    fontSize: 13,
    padding: 12,
    marginBottom: 18,
  },
  modal: {
    position: "fixed" as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0, 0, 0, 0.8)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
    backdropFilter: "blur(4px)",
  },
  modalContent: {
    backgroundColor: "#111",
    borderRadius: 16,
    padding: 24,
    border: "1px solid rgba(255, 255, 255, 0.1)",
    maxWidth: 500,
    width: "90%",
    position: "relative" as const,
  },
  modalClose: {
    position: "absolute" as const,
    top: 16,
    right: 16,
    background: "none",
    border: "none",
    color: "#9ca3af",
    fontSize: 18,
    cursor: "pointer",
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: 600,
    color: "#ffffff",
    margin: "0 0 16px 0",
  },
  modalImagePlaceholder: {
    width: "100%",
    height: 400,
    background: "linear-gradient(135deg, #1e1b4b, #431407)",
    borderRadius: 12,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    border: "1px solid rgba(255, 255, 255, 0.05)",
  },
  modalMockCard: {
    textAlign: "center" as const,
    padding: 24,
    maxWidth: 320,
  },
  modalMockIcon: {
    fontSize: 48,
    display: "block",
    marginBottom: 16,
  },
  modalMockTitle: {
    fontSize: 20,
    fontWeight: 700,
    color: "#ffffff",
    margin: "0 0 8px 0",
  },
  modalMockSub: {
    fontSize: 13,
    color: "#d1d5db",
    margin: "0 0 16px 0",
    lineHeight: 1.5,
  },
  modalMockHash: {
    fontSize: 11.5,
    color: "#818cf8",
    fontWeight: 500,
  },

  // ── NEW: Tab bar ──
  tabBar: {
    display: "flex",
    gap: 0,
    marginBottom: 0,
  },
  tabButton: {
    background: "none",
    border: "none",
    padding: "12px 24px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    color: "#6b7280",
    transition: "all 0.2s",
  },

  // ── NEW: Frame selector ──
  frameSelectorRow: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 12,
  },
  framePreview: {
    backgroundColor: "rgba(0,0,0,0.2)",
    borderRadius: 8,
    padding: 8,
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  frameThumb: {
    width: 60,
    height: 60,
    objectFit: "contain" as const,
    borderRadius: 4,
  },
  frameTags: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: 4,
  },
  tag: {
    fontSize: 10,
    color: "#818cf8",
    backgroundColor: "rgba(129, 140, 248, 0.1)",
    padding: "2px 6px",
    borderRadius: 4,
  },

  // ── NEW: Frame management gallery ──
  frameGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
    gap: 16,
    marginTop: 16,
  },
  frameCard: {
    backgroundColor: "rgba(255, 255, 255, 0.02)",
    borderRadius: 12,
    border: "1px solid rgba(255, 255, 255, 0.06)",
    overflow: "hidden",
    position: "relative" as const,
  },
  frameCardPreview: {
    width: "100%",
    height: 140,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(0,0,0,0.3)",
  },
  frameCardThumb: {
    maxWidth: "100%",
    maxHeight: "100%",
    objectFit: "contain" as const,
  },
  frameCardInfo: {
    padding: 10,
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
  },
  frameCardName: {
    fontSize: 12,
    fontWeight: 600,
    color: "#ffffff",
  },
  frameCardDims: {
    fontSize: 10,
    color: "#6b7280",
  },
  frameCardTags: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: 3,
  },
  frameCardUsage: {
    fontSize: 10,
    color: "#6b7280",
  },
  frameCardDelete: {
    position: "absolute" as const,
    top: 6,
    right: 6,
    background: "rgba(239, 68, 68, 0.8)",
    border: "none",
    color: "#ffffff",
    width: 24,
    height: 24,
    borderRadius: "50%",
    cursor: "pointer",
    fontSize: 12,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
};
