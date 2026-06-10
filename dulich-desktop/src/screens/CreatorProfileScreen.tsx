import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useAppStore } from "../stores/appStore";

interface Creator {
  id: string;
  name: string;
  voice_provider: string;
  voice_id: string;
  hook_preference: string;
  created_at?: string;
  updated_at?: string;
}

interface AnalysisResult {
  success: boolean;
  filename: string;
  duration: number;
  recommended_hook: string;
  hook_name: string;
  confidence: number;
  analysis_details: string;
}

const PROVIDER_VOICES: Record<string, { id: string; name: string }[]> = {
  vbee: [
    { id: "hn_female_lananh", name: "Lan Anh (Hà Nội Nữ)" },
    { id: "hn_male_minhtuan", name: "Minh Tuấn (Hà Nội Nam)" },
    { id: "hn_female_ngocmai", name: "Ngọc Mai (Hà Nội Nữ)" },
    { id: "hcm_male_ducanh", name: "Đức Anh (HCM Nam)" },
  ],
  edge: [
    { id: "vi-VN-HoaiMyNeural", name: "Hoài My (Nữ)" },
    { id: "vi-VN-NamMinhNeural", name: "Nam Minh (Nam)" },
  ],
  elevenlabs: [
    { id: "1rqNHUqUbBGpY3OyzPMI", name: "Vietnamese Male (ElevenLabs preset)" },
    { id: "custom", name: "Custom Voice ID (Nhập mã tự chọn...)" },
  ],
  openai: [
    { id: "custom", name: "Nhập mã giọng đọc OpenAI..." },
  ],
  mock: [
    { id: "mock", name: "Mock Voice (Im lặng)" }
  ]
};

export default function CreatorProfileScreen() {
  const [creators, setCreators] = useState<Creator[]>([]);
  const [selectedCreator, setSelectedCreator] = useState<Creator | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  
  // Video Analysis state
  const [videoPath, setVideoPath] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);

  const handlePlayPreview = async () => {
    if (!selectedCreator || previewLoading) return;
    setPreviewLoading(true);
    setErrorMsg("");
    
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    const provider = selectedCreator.voice_provider;
    const voiceId = selectedCreator.voice_id;
    const text = "Xin chào, đây là giọng nói thử nghiệm của bạn.";
    
    try {
      if (isTauri) {
        const settings = useAppStore.getState().settings;
        await invoke("set_api_keys", {
          elevenlabsKey: settings.elevenLabsKey || "",
          vbeeKey: settings.vbeeKey || "",
          openaiKey: settings.openAiKey || "",
          anthropicKey: settings.anthropicKey || "",
        });
        
        const resStr = await invoke<string>("preview_voice", {
          voiceProvider: provider,
          voiceId: voiceId,
          text: text,
        });
        
        const res = JSON.parse(resStr);
        if (res.success && res.data.audio_path) {
          const { convertFileSrc } = await import("@tauri-apps/api/core");
          const audioUrl = convertFileSrc(res.data.audio_path);
          const audio = new Audio(audioUrl);
          await audio.play();
        } else {
          setErrorMsg("Lỗi nghe thử: " + (res.data || "Không rõ nguyên nhân"));
        }
      } else {
        // Browser Mode
        const settings = useAppStore.getState().settings;
        const res = await fetch("http://localhost:7788/preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider,
            voice_id: voiceId,
            text,
            elevenlabs_api_key: settings.elevenLabsKey || "",
            vbee_api_key: settings.vbeeKey || "",
            openai_api_key: settings.openAiKey || "",
            anthropic_api_key: settings.anthropicKey || "",
          }),
        });
        
        if (!res.ok) {
          const t = await res.text();
          throw new Error(t);
        }
        
        const json = await res.json();
        if (json.success && json.url_path) {
          const audio = new Audio("http://localhost:7788" + json.url_path);
          await audio.play();
        } else {
          setErrorMsg("Lỗi nghe thử: " + (json.error || "Không rõ nguyên nhân"));
        }
      }
    } catch (err: any) {
      setErrorMsg("Lỗi kết nối hoặc tạo giọng nói: " + err.message);
    } finally {
      setPreviewLoading(false);
    }
  };

  useEffect(() => {
    fetchCreators();
  }, []);

  const fetchCreators = async () => {
    setLoading(true);
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    try {
      let resStr = "";
      if (isTauri) {
        resStr = await invoke<string>("get_creators");
      } else {
        const localData = localStorage.getItem("dulichapp_creators");
        if (localData) {
          resStr = JSON.stringify({ success: true, data: JSON.parse(localData) });
        } else {
          const defaultList = [
            { id: "lan_anh", name: "Lan Anh", voice_provider: "vbee", voice_id: "hn_female_lananh", hook_preference: "zoom_in" },
            { id: "minh_tuan", name: "Minh Tuấn", voice_provider: "vbee", voice_id: "hn_male_minhtuan", hook_preference: "glitch" },
            { id: "thu_ha", name: "Thu Hà", voice_provider: "vbee", voice_id: "hn_female_thutrang", hook_preference: "cinematic_vignette" },
            { id: "duc_anh", name: "Đức Anh", voice_provider: "vbee", voice_id: "hcm_male_ducanh", hook_preference: "zoom_out" },
            { id: "ngoc_mai", name: "Ngọc Mai", voice_provider: "vbee", voice_id: "hn_female_ngocmai", hook_preference: "zoom_in" },
          ];
          localStorage.setItem("dulichapp_creators", JSON.stringify(defaultList));
          resStr = JSON.stringify({ success: true, data: defaultList });
        }
      }
      const res = JSON.parse(resStr);
      if (res.success && Array.isArray(res.data)) {
        setCreators(res.data);
        if (res.data.length > 0 && !selectedCreator) {
          setSelectedCreator(res.data[0]);
        } else if (selectedCreator) {
          // Keep current selection updated
          const updated = res.data.find((c: Creator) => c.id === selectedCreator.id);
          if (updated) setSelectedCreator(updated);
        }
      }
    } catch (err) {
      console.error("Lỗi fetch creators:", err);
      setErrorMsg("Không thể kết nối đến MongoDB pipeline.");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveCreator = async () => {
    if (!selectedCreator) return;
    setSaving(true);
    setErrorMsg("");
    setSuccessMsg("");
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    try {
      let resStr = "";
      if (isTauri) {
        const payload = JSON.stringify(selectedCreator);
        resStr = await invoke<string>("save_creator", { creatorJson: payload });
      } else {
        const localData = localStorage.getItem("dulichapp_creators");
        let list = localData ? JSON.parse(localData) : [];
        const idx = list.findIndex((c: any) => c.id === selectedCreator.id);
        if (idx !== -1) {
          list[idx] = selectedCreator;
        } else {
          list.push(selectedCreator);
        }
        localStorage.setItem("dulichapp_creators", JSON.stringify(list));
        resStr = JSON.stringify({ success: true, data: "saved" });
      }
      const res = JSON.parse(resStr);
      if (res.success) {
        setSuccessMsg(`Đã lưu cấu hình cho ${selectedCreator.name}!`);
        fetchCreators();
        setTimeout(() => setSuccessMsg(""), 3000);
      } else {
        setErrorMsg(res.data || "Lưu thất bại.");
      }
    } catch (err: any) {
      setErrorMsg(err.toString());
    } finally {
      setSaving(false);
    }
  };

  const handleAnalyzeVideo = async () => {
    if (!videoPath) {
      setErrorMsg("Vui lòng nhập đường dẫn video mẫu.");
      return;
    }
    setAnalyzing(true);
    setErrorMsg("");
    setAnalysisResult(null);
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    try {
      let resStr = "";
      if (isTauri) {
        resStr = await invoke<string>("analyze_hook_video", { videoPath });
      } else {
        resStr = JSON.stringify({
          success: true,
          data: {
            filename: "video_mau.mp4",
            duration: 12.5,
            confidence: 0.92,
            recommended_hook: "zoom_in",
            hook_name: "Zoom In (Phóng to)",
            analysis_details: "Phát hiện chuyển động tịnh tiến về phía trước với vận tốc chậm đều, phù hợp để tạo cảm giác tò mò và tập trung vào chủ thể ở trung tâm."
          }
        });
      }
      const res = JSON.parse(resStr);
      if (res.success) {
        setAnalysisResult(res.data);
        // Automatically set recommended hook
        if (selectedCreator) {
          setSelectedCreator({
            ...selectedCreator,
            hook_preference: res.data.recommended_hook
          });
        }
      } else {
        setErrorMsg(res.data || "Không thể phân tích video này.");
      }
    } catch (err: any) {
      setErrorMsg(err.toString());
    } finally {
      setAnalyzing(false);
    }
  };

  const updateSelectedCreatorField = (field: keyof Creator, value: string) => {
    if (!selectedCreator) return;
    setSelectedCreator({
      ...selectedCreator,
      [field]: value
    });
  };

  const hookStyles = [
    { id: "zoom_in", name: "Zoom In (Phóng to)" },
    { id: "zoom_out", name: "Zoom Out (Thu nhỏ)" },
    { id: "glitch", name: "RGB Glitch (Nhiễu sóng)" },
    { id: "cinematic_vignette", name: "Cinematic Vignette (Tối góc)" },
    { id: "text_slide", name: "Animated Text (Chữ chạy)" },
    { id: "tiktok_tag_banner_purple", name: "TikTok Tag Banner (Nền Tím)" },
    { id: "tiktok_tag_banner_pink", name: "TikTok Tag Banner (Nền Hồng)" },
    { id: "tiktok_tag_banner_green", name: "TikTok Tag Banner (Nền Xanh Lá)" },
    { id: "tiktok_quote_card", name: "TikTok Quote Card" },
    { id: "tiktok_floating_box", name: "TikTok Floating Box (Chữ + Nền trôi nổi)" }
  ];

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>👤 Quản lý Người Tạo (Creators)</h1>
        <p style={styles.subtitle}>Quản lý giọng nói clone AI và tối ưu hiệu ứng Hook cho 5 creator cốt lõi.</p>
      </header>

      {errorMsg && <div style={styles.errorAlert}>⚠ {errorMsg}</div>}
      {successMsg && <div style={styles.successAlert}>✓ {successMsg}</div>}

      <div style={styles.layout}>
        {/* Sidebar: Creators List */}
        <aside style={styles.sidebar}>
          <h3 style={styles.sectionTitle}>Danh sách Creator</h3>
          {loading && <div style={styles.loadingText}>Đang tải danh sách...</div>}
          <div style={styles.creatorList}>
            {creators.map((c) => {
              const isSelected = selectedCreator?.id === c.id;
              return (
                <button
                  key={c.id}
                  onClick={() => {
                    setSelectedCreator(c);
                    setAnalysisResult(null);
                    setVideoPath("");
                  }}
                  style={{
                    ...styles.creatorCard,
                    backgroundColor: isSelected ? "rgba(124, 58, 237, 0.2)" : "rgba(255, 255, 255, 0.03)",
                    borderColor: isSelected ? "#a78bfa" : "rgba(255, 255, 255, 0.08)",
                  }}
                >
                  <div style={styles.avatar}>
                    {c.name.charAt(0)}
                  </div>
                  <div style={styles.creatorInfo}>
                    <span style={styles.creatorName}>{c.name}</span>
                    <span style={styles.creatorVoiceCode}>
                      {c.voice_provider === "vbee" ? "🎙 Vbee" : c.voice_provider === "edge" ? "🌐 Microsoft Edge" : c.voice_provider === "openai" ? "🤖 OpenAI TTS" : c.voice_provider === "mock" ? "🤖 Mock" : "✨ ElevenLabs"} - {c.voice_id}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        {/* Main: Profile Config & Hook Analyzer */}
        {selectedCreator ? (
          <main style={styles.mainContent}>
            <div style={styles.glassPanel}>
              <h2 style={styles.panelTitle}>Cấu hình Profile: {selectedCreator.name}</h2>
              
              <div style={styles.formGrid}>
                {/* Voice Settings */}
                <div style={styles.formGroup}>
                  <label style={styles.label}>Nền tảng Voice Clone</label>
                  <select
                    value={selectedCreator.voice_provider}
                    onChange={(e) => {
                      const prov = e.target.value;
                      const defaultVoice = PROVIDER_VOICES[prov]?.[0]?.id || "";
                      setSelectedCreator({
                        ...selectedCreator,
                        voice_provider: prov,
                        voice_id: defaultVoice
                      });
                    }}
                    style={styles.select}
                  >
                    <option style={styles.option} value="vbee">Vbee.ai (Tiếng Việt chất lượng cao)</option>
                    <option style={styles.option} value="edge">Microsoft Edge TTS (Miễn phí & Đồng bộ tốt)</option>
                    <option style={styles.option} value="elevenlabs">ElevenLabs (Bilingual / Clone giọng nói)</option>
                    <option style={styles.option} value="openai">OpenAI TTS (Giọng đọc mượt mà từ ChatGPT)</option>
                    <option style={styles.option} value="mock">Mock Voice (Test offline)</option>
                  </select>
                </div>

                <div style={styles.formGroup}>
                  <label style={styles.label}>Chọn Giọng Đọc</label>
                  <div style={{ display: "flex", gap: 10 }}>
                    <select
                      value={
                        selectedCreator.voice_provider === "elevenlabs" &&
                        !PROVIDER_VOICES.elevenlabs.some(v => v.id === selectedCreator.voice_id)
                          ? "custom"
                          : selectedCreator.voice_id
                      }
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === "custom") {
                          updateSelectedCreatorField("voice_id", "");
                        } else {
                          updateSelectedCreatorField("voice_id", val);
                        }
                      }}
                      style={{ ...styles.select, flex: 1 }}
                    >
                      {(PROVIDER_VOICES[selectedCreator.voice_provider] || []).map((v) => (
                        <option key={v.id} value={v.id} style={styles.option}>
                          {v.name}
                        </option>
                      ))}
                      {selectedCreator.voice_provider === "elevenlabs" && (
                        <option value="custom" style={styles.option}>
                          Custom Voice ID (Nhập mã tự chọn...)
                        </option>
                      )}
                    </select>

                    {selectedCreator.voice_provider !== "mock" && (
                      <button
                        onClick={handlePlayPreview}
                        disabled={previewLoading || !selectedCreator.voice_id}
                        style={{
                          backgroundColor: "rgba(99, 102, 241, 0.15)",
                          border: "1px solid rgba(99, 102, 241, 0.4)",
                          color: "#a5b4fc",
                          borderRadius: 8,
                          padding: "0 16px",
                          fontSize: 13,
                          fontWeight: 600,
                          cursor: (previewLoading || !selectedCreator.voice_id) ? "not-allowed" : "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          whiteSpace: "nowrap",
                          transition: "all 0.2s"
                        }}
                      >
                        {previewLoading ? "⏳ Đang tạo..." : "🔊 Nghe thử"}
                      </button>
                    )}
                  </div>
                </div>

                {/* Additional custom input for ElevenLabs custom voices */}
                {selectedCreator.voice_provider === "elevenlabs" && 
                  (!PROVIDER_VOICES.elevenlabs.some(v => v.id === selectedCreator.voice_id) || 
                   selectedCreator.voice_id === "custom") && (
                    <div style={styles.formGroup}>
                      <label style={styles.label}>Nhập Custom ElevenLabs Voice ID</label>
                      <input
                        type="text"
                        value={selectedCreator.voice_id === "custom" ? "" : selectedCreator.voice_id}
                        onChange={(e) => updateSelectedCreatorField("voice_id", e.target.value)}
                        placeholder="Nhập ElevenLabs Voice ID (VD: pNInz6obpgDQGcFmaJgB)"
                        style={styles.input}
                      />
                      <small style={styles.hint}>
                        Nhập Voice ID từ ElevenLabs Voice Library hoặc dashboard của bạn.
                      </small>
                    </div>
                )}

                {/* Hook Preference */}
                <div style={styles.formGroup}>
                  <label style={styles.label}>Hiệu ứng Hook mặc định</label>
                  <select
                    value={selectedCreator.hook_preference}
                    onChange={(e) => updateSelectedCreatorField("hook_preference", e.target.value)}
                    style={styles.select}
                  >
                    {hookStyles.map((s) => (
                      <option key={s.id} value={s.id} style={styles.option}>{s.name}</option>
                    ))}
                  </select>
                </div>

                <div style={styles.formActions}>
                  <button
                    onClick={handleSaveCreator}
                    disabled={saving}
                    style={styles.saveBtn}
                  >
                    {saving ? "Đang lưu..." : "💾 Lưu thay đổi"}
                  </button>
                </div>
              </div>
            </div>

            {/* AI Hook Analyzer */}
            <div style={styles.glassPanel}>
              <h2 style={styles.panelTitle}>🎬 AI Hook Analyzer (Học mẫu video)</h2>
              <p style={styles.desc}>
                Upload hoặc nhập đường dẫn video mẫu (reference video) của Creator này.
                AI sẽ phân tích chuyển động, nhịp điệu và đề xuất Hook template phù hợp.
              </p>

              <div style={styles.analyzerBox}>
                <div style={styles.inputRow}>
                  <input
                    type="text"
                    value={videoPath}
                    onChange={(e) => setVideoPath(e.target.value)}
                    placeholder="Đường dẫn tuyệt đối tới file video (VD: D:\Videos\ref_lananh.mp4)"
                    style={styles.input}
                  />
                  <button
                    onClick={handleAnalyzeVideo}
                    disabled={analyzing}
                    style={styles.analyzeBtn}
                  >
                    {analyzing ? "Đang phân tích..." : "⚡ Phân tích Hook"}
                  </button>
                </div>

                {analysisResult && (
                  <div style={styles.resultBox}>
                    <h4 style={styles.resultTitle}>📊 Kết quả phân tích AI:</h4>
                    
                    <div style={styles.resultGrid}>
                      <div style={styles.resultCard}>
                        <span style={styles.resultLabel}>Video gốc:</span>
                        <span style={styles.resultValue}>{analysisResult.filename}</span>
                      </div>
                      <div style={styles.resultCard}>
                        <span style={styles.resultLabel}>Thời lượng phát hiện:</span>
                        <span style={styles.resultValue}>{analysisResult.duration} giây</span>
                      </div>
                      <div style={styles.resultCard}>
                        <span style={styles.resultLabel}>Độ tin cậy:</span>
                        <span style={{ ...styles.resultValue, color: "#10b981" }}>{(analysisResult.confidence * 100).toFixed(0)}%</span>
                      </div>
                      <div style={styles.resultCard}>
                        <span style={styles.resultLabel}>Đề xuất hiệu ứng:</span>
                        <span style={{ ...styles.resultValue, color: "#a78bfa" }}>{analysisResult.hook_name}</span>
                      </div>
                    </div>

                    <div style={styles.detailsBox}>
                      <strong>Chi tiết đặc trưng:</strong>
                      <p style={styles.detailsText}>{analysisResult.analysis_details}</p>
                    </div>

                    <div style={styles.applyNote}>
                      ℹ️ Hiệu ứng <strong>{analysisResult.hook_name}</strong> đã tự động được gán vào trường "Hiệu ứng Hook mặc định" của {selectedCreator.name}. Hãy nhấn <strong>Lưu thay đổi</strong> ở trên để áp dụng vĩnh viễn.
                    </div>
                  </div>
                )}
              </div>
            </div>
          </main>
        ) : (
          <div style={styles.emptyState}>Vui lòng chọn hoặc thêm Creator để cấu hình.</div>
        )}
      </div>
    </div>
  );
}

const styles = {
  container: {
    padding: 24,
    color: "#f3f4f6",
    fontFamily: "Inter, sans-serif",
  },
  header: {
    marginBottom: 28,
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
  },
  layout: {
    display: "grid",
    gridTemplateColumns: "280px 1fr",
    gap: 24,
  },
  sidebar: {
    backgroundColor: "rgba(30, 27, 75, 0.3)",
    backdropFilter: "blur(12px)",
    borderRadius: 16,
    padding: 20,
    border: "1px solid rgba(255, 255, 255, 0.05)",
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: 600,
    color: "#e5e7eb",
    margin: "0 0 16px 0",
  },
  loadingText: {
    fontSize: 13,
    color: "#9ca3af",
  },
  creatorList: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 12,
  },
  creatorCard: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderStyle: "solid",
    cursor: "pointer",
    textAlign: "left" as const,
    transition: "all 0.2s ease",
    width: "100%",
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 15,
    fontWeight: 700,
  },
  creatorInfo: {
    display: "flex",
    flexDirection: "column" as const,
  },
  creatorName: {
    fontSize: 14,
    fontWeight: 600,
    color: "#ffffff",
  },
  creatorVoiceCode: {
    fontSize: 11,
    color: "#9ca3af",
    marginTop: 2,
  },
  mainContent: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 24,
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
    fontSize: 18,
    fontWeight: 600,
    color: "#ffffff",
    margin: "0 0 18px 0",
  },
  desc: {
    fontSize: 13,
    color: "#9ca3af",
    margin: "0 0 16px 0",
    lineHeight: 1.5,
  },
  formGrid: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 18,
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
  hint: {
    fontSize: 11,
    color: "#6b7280",
    marginTop: 2,
  },
  formActions: {
    display: "flex",
    justifyContent: "flex-end",
    marginTop: 10,
  },
  saveBtn: {
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    border: "none",
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 600,
    padding: "12px 24px",
    cursor: "pointer",
    transition: "background-color 0.2s",
  },
  analyzerBox: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 16,
  },
  inputRow: {
    display: "flex",
    gap: 12,
  },
  analyzeBtn: {
    backgroundColor: "rgba(255, 255, 255, 0.08)",
    border: "1px solid rgba(255, 255, 255, 0.15)",
    borderRadius: 8,
    color: "#ffffff",
    fontSize: 13,
    fontWeight: 600,
    padding: "0 20px",
    cursor: "pointer",
    whiteSpace: "nowrap" as const,
    transition: "all 0.2s",
  },
  resultBox: {
    backgroundColor: "rgba(255, 255, 255, 0.02)",
    borderRadius: 12,
    border: "1px solid rgba(255, 255, 255, 0.05)",
    padding: 20,
    marginTop: 10,
  },
  resultTitle: {
    fontSize: 14,
    fontWeight: 600,
    margin: "0 0 14px 0",
    color: "#ffffff",
  },
  resultGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: 12,
    marginBottom: 16,
  },
  resultCard: {
    backgroundColor: "rgba(0, 0, 0, 0.2)",
    borderRadius: 8,
    padding: 12,
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
  },
  resultLabel: {
    fontSize: 11,
    color: "#6b7280",
  },
  resultValue: {
    fontSize: 13,
    fontWeight: 600,
    color: "#ffffff",
  },
  detailsBox: {
    backgroundColor: "rgba(0, 0, 0, 0.15)",
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  detailsText: {
    fontSize: 12,
    color: "#d1d5db",
    margin: "6px 0 0 0",
    lineHeight: 1.5,
  },
  applyNote: {
    fontSize: 11.5,
    color: "#a78bfa",
    lineHeight: 1.4,
  },
  emptyState: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    height: 300,
    color: "#9ca3af",
    fontSize: 14,
    border: "2px dashed rgba(255, 255, 255, 0.08)",
    borderRadius: 16,
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
  successAlert: {
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    border: "1px solid #10b981",
    borderRadius: 8,
    color: "#6ee7b7",
    fontSize: 13,
    padding: 12,
    marginBottom: 18,
  }
};
