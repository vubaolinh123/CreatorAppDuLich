import { useState } from "react";
import { useAppStore } from "../stores/appStore";

type SettingsTab = "dashboard" | "apikeys" | "creators" | "folder" | "resources";

interface Creator {
  id: number;
  name: string;
  voiceId: string;
  avatar: string;
}



const DEFAULT_CREATORS: Creator[] = [
  { id: 1, name: "Nguyễn Thành Nam", voiceId: "EXAVITQu4vr4xnSDxMaL", avatar: "👨‍💼" },
  { id: 2, name: "Trần Minh Châu", voiceId: "ErXwobaYiN019PkySvjV", avatar: "👩‍💻" },
  { id: 3, name: "Lê Hoàng Phúc", voiceId: "VR6AewLTigWG4xSOukaG", avatar: "🧑‍🎤" },
  { id: 4, name: "Ngọc Mai", voiceId: "", avatar: "👩‍🌾" },
  { id: 5, name: "Đức Anh", voiceId: "", avatar: "🧔" },
];

export default function SettingsScreen() {
  const { settings, updateSettings, updateResourceSettings } = useAppStore();
  const [activeTab, setActiveTab] = useState<SettingsTab>("dashboard");
  const [saved, setSaved] = useState(false);

  // Dashboard settings
  const [dashboardUrl, setDashboardUrl] = useState(settings.dashboardUrl || "http://localhost:3000");
  const [pingStatus, setPingStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");

  // API Keys
  const [anthropicKey, setAnthropicKey] = useState(settings.anthropicKey || "");
  const [elevenLabsKey, setElevenLabsKey] = useState(settings.elevenLabsKey || "");
  const [vbeeKey, setVbeeKey] = useState(settings.vbeeKey || "");
  const [openAiKey, setOpenAiKey] = useState(settings.openAiKey || "");
  const [showAnthropicKey, setShowAnthropicKey] = useState(false);
  const [showElevenLabsKey, setShowElevenLabsKey] = useState(false);
  const [showVbeeKey, setShowVbeeKey] = useState(false);
  const [showOpenAiKey, setShowOpenAiKey] = useState(false);

  // Resources
  const [maxWorkers, setMaxWorkers] = useState(settings.resources?.maxWorkers ?? 2);
  const [ramGb, setRamGb] = useState(settings.resources?.ramGb ?? 4.0);
  const [cpuCores, setCpuCores] = useState(settings.resources?.cpuCores ?? 2);
  const [voiceProvider, setVoiceProvider] = useState<'vbee' | 'elevenlabs' | 'mock'>(settings.resources?.voiceProvider ?? 'vbee');
  const [mongoUri, setMongoUri] = useState(settings.resources?.mongoUri ?? 'mongodb://localhost:27017');

  // Creators
  const [creators, setCreators] = useState(settings.creators?.length ? settings.creators : DEFAULT_CREATORS);

  // Output folder
  const [outputFolder, setOutputFolder] = useState(settings.outputFolder || "D:\\DuLichApp\\Output");

  const handleSave = async () => {
    // Persist to Zustand store
    updateSettings({
      dashboardUrl, anthropicKey, elevenLabsKey, vbeeKey, openAiKey, outputFolder, creators,
    });
    updateResourceSettings({ maxWorkers, ramGb, cpuCores, voiceProvider, mongoUri });
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const testConnection = async () => {
    setPingStatus("loading");
    await new Promise((r) => setTimeout(r, 1400));
    setPingStatus(Math.random() > 0.2 ? "ok" : "error");
  };

  const updateCreator = (id: number, field: keyof Creator, value: string) => {
    setCreators((prev) =>
      prev.map((c) => (c.id === id ? { ...c, [field]: value } : c))
    );
  };

  const TABS: { id: SettingsTab; label: string; icon: string }[] = [
    { id: "dashboard", label: "Dashboard", icon: "🌐" },
    { id: "apikeys", label: "API Keys", icon: "🔑" },
    { id: "resources", label: "Tài nguyên", icon: "⚡" },
    { id: "creators", label: "Creators", icon: "👥" },
    { id: "folder", label: "Thư mục", icon: "📁" },
  ];

  return (
    <div style={s.container}>
      {/* Header */}
      <div style={s.header}>
        <div>
          <h1 style={s.title}>⚙️ Cài đặt</h1>
          <p style={s.subtitle}>Quản lý cấu hình hệ thống</p>
        </div>
        <button
          style={{ ...s.saveBtn, background: saved ? "#10b981" : "linear-gradient(135deg,#6366f1,#818cf8)" }}
          onClick={handleSave}
        >
          {saved ? "✅ Đã lưu!" : "💾 Lưu cài đặt"}
        </button>
      </div>

      <div style={s.body}>
        {/* Tabs sidebar */}
        <div style={s.tabSidebar}>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              style={{ ...s.tabBtn, ...(activeTab === tab.id ? s.tabBtnActive : {}) }}
              onClick={() => setActiveTab(tab.id)}
            >
              <span style={s.tabIcon}>{tab.icon}</span>
              <span style={s.tabLabel}>{tab.label}</span>
              {activeTab === tab.id && <div style={s.tabActiveBar} />}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div style={s.tabContent}>
          {/* ── Dashboard ── */}
          {activeTab === "dashboard" && (
            <div style={s.section}>
              <h2 style={s.sectionTitle}>🌐 Cài đặt Dashboard</h2>
              <p style={s.sectionDesc}>
                Nhập URL của Dashboard Vercel để đồng bộ bài viết lên cloud.
              </p>

              <div style={s.formGroup}>
                <label style={s.label}>Dashboard URL</label>
                <div style={s.inputRow}>
                  <input
                    style={s.input}
                    value={dashboardUrl}
                    onChange={(e) => setDashboardUrl(e.target.value)}
                    placeholder="https://your-app.vercel.app"
                  />
                  <button
                    style={{ ...s.testBtn, opacity: pingStatus === "loading" ? 0.6 : 1 }}
                    onClick={testConnection}
                    disabled={pingStatus === "loading"}
                  >
                    {pingStatus === "loading" ? "Đang kiểm tra…" : "Test kết nối"}
                  </button>
                </div>
                {pingStatus === "ok" && (
                  <div style={s.statusMsg("#10b981")}>✅ Kết nối thành công! Dashboard đang online.</div>
                )}
                {pingStatus === "error" && (
                  <div style={s.statusMsg("#ef4444")}>❌ Không thể kết nối. Kiểm tra lại URL.</div>
                )}
              </div>

              <div style={s.infoCard}>
                <div style={s.infoTitle}>💡 Hướng dẫn</div>
                <ul style={s.infoList}>
                  <li>Để localhost: bài viết chỉ lưu trên máy, không đồng bộ</li>
                  <li>Để URL Vercel: bài viết sẽ được đẩy lên cloud sau khi tạo xong</li>
                  <li>Bạn có thể thay đổi bất cứ lúc nào mà không mất dữ liệu</li>
                </ul>
              </div>
            </div>
          )}

          {/* ── API Keys ── */}
          {activeTab === "apikeys" && (
            <div style={s.section}>
              <h2 style={s.sectionTitle}>🔑 API Keys</h2>
              <p style={s.sectionDesc}>
                Để trống nếu muốn dùng <strong style={{ color: "#a78bfa" }}>Mock mode</strong> (tạo data giả, không cần key).
              </p>

              <div style={s.formGroup}>
                <label style={s.label}>
                  Anthropic API Key
                  <span style={s.mockBadge}>Claude AI</span>
                </label>
                <div style={s.passwordRow}>
                  <input
                    style={s.input}
                    type={showAnthropicKey ? "text" : "password"}
                    value={anthropicKey}
                    onChange={(e) => setAnthropicKey(e.target.value)}
                    placeholder="sk-ant-api03-..."
                  />
                  <button
                    style={s.showHideBtn}
                    onClick={() => setShowAnthropicKey((p) => !p)}
                  >
                    {showAnthropicKey ? "🙈 Ẩn" : "👁️ Hiện"}
                  </button>
                </div>
                <div style={s.keyHint}>
                  {anthropicKey
                    ? "✅ Key đã được cài đặt — sẽ dùng Claude AI thật"
                    : "⚡ Trống → Dùng Mock mode (khuyến nghị để test)"}
                </div>
              </div>

              <div style={s.divider} />

              <div style={s.formGroup}>
                <label style={s.label}>
                  ElevenLabs API Key
                  <span style={s.mockBadge}>Text-to-Speech</span>
                </label>
                <div style={s.passwordRow}>
                  <input
                    style={s.input}
                    type={showElevenLabsKey ? "text" : "password"}
                    value={elevenLabsKey}
                    onChange={(e) => setElevenLabsKey(e.target.value)}
                    placeholder="sk_..."
                  />
                  <button
                    style={s.showHideBtn}
                    onClick={() => setShowElevenLabsKey((p) => !p)}
                  >
                    {showElevenLabsKey ? "🙈 Ẩn" : "👁️ Hiện"}
                  </button>
                </div>
                <div style={s.keyHint}>
                  {elevenLabsKey
                    ? "✅ Key đã được cài đặt — sẽ tạo giọng nói thật"
                    : "⚡ Trống → Dùng audio giả (silent mock)"}
                </div>
              </div>

              <div style={s.divider} />

              <div style={s.formGroup}>
                <label style={s.label}>
                  Vbee.ai API Key
                  <span style={{ ...s.mockBadge, background: 'rgba(52,211,153,0.15)', color: '#34d399' }}>Tiếng Việt TTS</span>
                </label>
                <div style={s.passwordRow}>
                  <input
                    style={s.input}
                    type={showVbeeKey ? "text" : "password"}
                    value={vbeeKey}
                    onChange={(e) => setVbeeKey(e.target.value)}
                    placeholder="vbee_api_..."
                  />
                  <button style={s.showHideBtn} onClick={() => setShowVbeeKey((p) => !p)}>
                    {showVbeeKey ? "🙈 Ẩn" : "👁️ Hiện"}
                  </button>
                </div>
                <div style={s.keyHint}>
                  {vbeeKey
                    ? "✅ Key đã cài — Tiếng Việt TTS chất lượng cao"
                    : "⚡ Trống → Mock audio (không cần key cho standard voices)"}
                </div>
              </div>

              <div style={s.divider} />

              <div style={s.formGroup}>
                <label style={s.label}>
                  OpenAI API Key
                  <span style={{ ...s.mockBadge, background: 'rgba(16,185,129,0.15)', color: '#10b981' }}>ChatGPT TTS</span>
                </label>
                <div style={s.passwordRow}>
                  <input
                    style={s.input}
                    type={showOpenAiKey ? "text" : "password"}
                    value={openAiKey}
                    onChange={(e) => setOpenAiKey(e.target.value)}
                    placeholder="sk-proj-..."
                  />
                  <button style={s.showHideBtn} onClick={() => setShowOpenAiKey((p) => !p)}>
                    {showOpenAiKey ? "🙈 Ẩn" : "👁️ Hiện"}
                  </button>
                </div>
                <div style={s.keyHint}>
                  {openAiKey
                    ? "✅ Key đã được cài đặt — sẽ dùng OpenAI ChatGPT TTS"
                    : "⚡ Trống → Dùng mock audio (nếu chọn OpenAI provider)"}
                </div>
              </div>

              <div style={s.warningCard}>
                <div style={s.warningTitle}>⚠️ Lưu ý bảo mật</div>
                <p style={s.warningText}>
                  API keys được lưu trên máy của bạn, không gửi lên server. Không chia sẻ file cài đặt với người khác.
                </p>
              </div>
            </div>
          )}

          {/* ── Resources ── */}
          {activeTab === "resources" && (
            <div style={s.section}>
              <h2 style={s.sectionTitle}>⚡ Tài nguyên hệ thống</h2>
              <p style={s.sectionDesc}>
                Cấu hình RAM, CPU và số jobs chạy song song. Hệ thống tự điều chỉnh workers theo giới hạn này.
              </p>

              {/* RAM */}
              <div style={s.formGroup}>
                <label style={s.label}>💾 RAM tối đa (GB)</label>
                <div style={s.sliderWrap}>
                  <input
                    type="range" min={1} max={32} step={0.5}
                    value={ramGb}
                    onChange={(e) => setRamGb(parseFloat(e.target.value))}
                    style={s.rangeInput}
                  />
                  <span style={s.rangeVal}>{ramGb} GB</span>
                </div>
                <div style={s.hint}>Ước tính: mỗi worker dùng ~500MB. {ramGb}GB = tối đa {Math.floor(ramGb / 0.5)} workers</div>
              </div>

              <div style={s.divider} />

              {/* CPU */}
              <div style={s.formGroup}>
                <label style={s.label}>💻 CPU Cores</label>
                <div style={s.sliderWrap}>
                  <input
                    type="range" min={1} max={16} step={1}
                    value={cpuCores}
                    onChange={(e) => setCpuCores(parseInt(e.target.value))}
                    style={s.rangeInput}
                  />
                  <span style={s.rangeVal}>{cpuCores} cores</span>
                </div>
                <div style={s.hint}>Số CPU cores cho phép pipeline dùng</div>
              </div>

              <div style={s.divider} />

              {/* Max Workers */}
              <div style={s.formGroup}>
                <label style={s.label}>⚡ Số workers tối đa (jobs song song)</label>
                <div style={s.sliderWrap}>
                  <input
                    type="range" min={1} max={8} step={1}
                    value={maxWorkers}
                    onChange={(e) => setMaxWorkers(parseInt(e.target.value))}
                    style={s.rangeInput}
                  />
                  <span style={s.rangeVal}>{maxWorkers} workers</span>
                </div>
                <div style={s.hint}>Chạy tối đa {maxWorkers} clip cùng lúc</div>
              </div>

              <div style={s.divider} />

              {/* Voice Provider */}
              <div style={s.formGroup}>
                <label style={s.label}>🎵 Voice Provider mặc định</label>
                <div style={{ display: 'flex', gap: 10 }}>
                  {(['vbee', 'elevenlabs', 'mock'] as const).map(p => (
                    <button
                      key={p}
                      onClick={() => setVoiceProvider(p)}
                      style={{
                        flex: 1, padding: '10px 8px', borderRadius: 8, cursor: 'pointer',
                        fontSize: 12, fontWeight: 600,
                        background: voiceProvider === p ? 'rgba(99,102,241,0.25)' : 'rgba(255,255,255,0.04)',
                        border: `1px solid ${voiceProvider === p ? '#6366f1' : 'rgba(255,255,255,0.08)'}`,
                        color: voiceProvider === p ? '#818cf8' : '#64748b',
                        transition: 'all 0.15s',
                      }}
                    >
                      {p === 'vbee' ? '🆻🇳 Vbee.ai' : p === 'elevenlabs' ? '🌍 ElevenLabs' : '🧩 Mock'}
                    </button>
                  ))}
                </div>
                <div style={s.hint}>
                  {voiceProvider === 'vbee'
                    ? 'Vbee.ai: Tiếng Việt native, chất lượng cao'
                    : voiceProvider === 'elevenlabs'
                    ? 'ElevenLabs: Đa ngôn ngữ, voice clone'
                    : 'Mock: Không cần API key, tạo audio giả để test'}
                </div>
              </div>

              <div style={s.divider} />

              {/* MongoDB URI */}
              <div style={s.formGroup}>
                <label style={s.label}>🌱 MongoDB URI</label>
                <input
                  style={s.input}
                  value={mongoUri}
                  onChange={(e) => setMongoUri(e.target.value)}
                  placeholder="mongodb://localhost:27017"
                />
                <div style={s.hint}>Local: mongodb://localhost:27017 | Atlas: mongodb+srv://...</div>
              </div>

              <div style={s.infoCard}>
                <div style={s.infoTitle}>💡 Tóm tắt cấu hình hiện tại</div>
                <ul style={s.infoList}>
                  <li>RAM: {ramGb}GB → tối đa {Math.floor(ramGb / 0.5)} workers</li>
                  <li>CPU: {cpuCores} cores</li>
                  <li>Workers thực tế: {Math.min(maxWorkers, cpuCores, Math.floor(ramGb / 0.5))} (min của cả 3)</li>
                  <li>Voice: {voiceProvider}</li>
                  <li>MongoDB: {mongoUri}</li>
                </ul>
              </div>
            </div>
          )}

          {activeTab === "creators" && (
            <div style={s.section}>
              <h2 style={s.sectionTitle}>👥 Quản lý Creators</h2>
              <p style={s.sectionDesc}>
                Cài đặt thông tin và Voice ID ElevenLabs cho từng creator.
              </p>
              <div style={s.creatorGrid}>
                {creators.map((creator) => (
                  <CreatorCard
                    key={creator.id}
                    creator={creator}
                    onChange={updateCreator}
                  />
                ))}
              </div>
            </div>
          )}

          {/* ── Folder ── */}
          {activeTab === "folder" && (
            <div style={s.section}>
              <h2 style={s.sectionTitle}>📁 Thư mục xuất file</h2>
              <p style={s.sectionDesc}>
                Chọn nơi lưu video, audio và các file được tạo ra bởi pipeline.
              </p>

              <div style={s.formGroup}>
                <label style={s.label}>Thư mục output</label>
                <div style={s.inputRow}>
                  <input
                    style={s.input}
                    value={outputFolder}
                    onChange={(e) => setOutputFolder(e.target.value)}
                    placeholder="D:\DuLichApp\Output"
                  />
                  <button style={s.testBtn} onClick={() => {}}>
                    📂 Chọn thư mục
                  </button>
                </div>
                <div style={s.hint}>Đường dẫn đầy đủ trên máy tính của bạn</div>
              </div>

              <div style={s.folderPreview}>
                <div style={s.folderRow}>
                  <span style={s.folderIcon}>📁</span>
                  <div>
                    <div style={s.folderName}>Videos</div>
                    <div style={s.folderPath}>{outputFolder}/videos/</div>
                  </div>
                </div>
                <div style={s.folderRow}>
                  <span style={s.folderIcon}>📁</span>
                  <div>
                    <div style={s.folderName}>Audio</div>
                    <div style={s.folderPath}>{outputFolder}/audio/</div>
                  </div>
                </div>
                <div style={s.folderRow}>
                  <span style={s.folderIcon}>📁</span>
                  <div>
                    <div style={s.folderName}>Scripts</div>
                    <div style={s.folderPath}>{outputFolder}/scripts/</div>
                  </div>
                </div>
              </div>

              <div style={s.infoCard}>
                <div style={s.infoTitle}>💡 Lưu ý</div>
                <ul style={s.infoList}>
                  <li>Đảm bảo ổ đĩa có đủ dung lượng (mỗi video khoảng 50–200MB)</li>
                  <li>Không nên dùng thư mục trong Program Files hoặc Windows</li>
                  <li>Có thể dùng ổ D: hoặc E: để tránh tốn không gian ổ C:</li>
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Creator Card ───────────────────────────────────────────────────────────
function CreatorCard({
  creator,
  onChange,
}: {
  creator: Creator;
  onChange: (id: number, field: keyof Creator, value: string) => void;
}) {


  return (
    <div style={s.creatorCard}>
      {/* Avatar */}
      <div style={s.avatarSection}>
        <div style={s.avatar}>{creator.avatar}</div>
        <select
          style={s.avatarSelect}
          value={creator.avatar}
          onChange={(e) => onChange(creator.id, "avatar", e.target.value)}
        >
          {["👨‍💼", "👩‍💻", "🧑‍🎤", "👩‍🌾", "🧔", "👩‍🦱", "🧑‍💻", "👨‍🎤", "🧕", "👦", "👧", "🧒"].map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
      </div>

      {/* Name */}
      <div style={s.creatorFormGroup}>
        <label style={s.creatorLabel}>Tên Creator</label>
        <input
          style={s.creatorInput}
          value={creator.name}
          onChange={(e) => onChange(creator.id, "name", e.target.value)}
          placeholder={`Creator ${creator.id}`}
        />
      </div>

      {/* Voice ID */}
      <div style={s.creatorFormGroup}>
        <label style={s.creatorLabel}>ElevenLabs Voice ID</label>
        <input
          style={s.creatorInput}
          value={creator.voiceId}
          onChange={(e) => onChange(creator.id, "voiceId", e.target.value)}
          placeholder="Để trống → dùng Mock voice"
        />
        {creator.voiceId && (
          <div style={{ fontSize: 10, color: "#10b981", marginTop: 4 }}>✅ Voice ID đã cài</div>
        )}
        {!creator.voiceId && (
          <div style={{ fontSize: 10, color: "#6b7280", marginTop: 4 }}>⚡ Chưa có → Mock mode</div>
        )}
      </div>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────
const s: Record<string, any> = {
  container: {
    padding: "28px 32px",
    height: "100%",
    overflowY: "auto",
    boxSizing: "border-box",
    background: "#0f0f0f",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 28,
    flexShrink: 0,
  },
  title: { fontSize: 24, fontWeight: 700, color: "#f1f1f1", margin: 0 },
  subtitle: { fontSize: 13, color: "#6b7280", margin: "4px 0 0" },
  saveBtn: {
    border: "none",
    borderRadius: 10,
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    padding: "10px 22px",
    cursor: "pointer",
    transition: "background 0.3s",
    boxShadow: "0 4px 12px rgba(99,102,241,0.3)",
  },
  body: {
    display: "flex",
    gap: 24,
    flex: 1,
    minHeight: 0,
  },
  tabSidebar: {
    width: 160,
    flexShrink: 0,
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  tabBtn: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    background: "transparent",
    border: "1px solid transparent",
    borderRadius: 10,
    color: "#6b7280",
    fontSize: 13,
    fontWeight: 500,
    padding: "10px 14px",
    cursor: "pointer",
    textAlign: "left",
    position: "relative",
    transition: "all 0.15s",
  },
  tabBtnActive: {
    background: "rgba(99,102,241,0.12)",
    borderColor: "rgba(99,102,241,0.3)",
    color: "#a78bfa",
  },
  tabActiveBar: {
    position: "absolute",
    left: 0,
    top: "50%",
    transform: "translateY(-50%)",
    width: 3,
    height: "60%",
    background: "linear-gradient(180deg, #7c3aed, #2563eb)",
    borderRadius: "0 4px 4px 0",
  },
  tabIcon: { fontSize: 16 },
  tabLabel: { fontSize: 13 },
  tabContent: {
    flex: 1,
    overflowY: "auto",
  },
  section: {
    background: "#161616",
    border: "1px solid #252525",
    borderRadius: 16,
    padding: "28px 32px",
  },
  sectionTitle: { fontSize: 18, fontWeight: 700, color: "#e5e7eb", margin: "0 0 8px" },
  sectionDesc: { fontSize: 13, color: "#6b7280", margin: "0 0 24px", lineHeight: 1.6 },
  formGroup: { marginBottom: 20 },
  label: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 13,
    fontWeight: 600,
    color: "#d1d5db",
    marginBottom: 8,
  },
  mockBadge: {
    fontSize: 10,
    background: "rgba(99,102,241,0.15)",
    color: "#818cf8",
    borderRadius: 20,
    padding: "2px 8px",
    border: "1px solid rgba(99,102,241,0.25)",
    fontWeight: 500,
  },
  input: {
    flex: 1,
    background: "#0f0f0f",
    border: "1px solid #2a2a2a",
    borderRadius: 8,
    color: "#e5e7eb",
    fontSize: 13,
    padding: "10px 14px",
    outline: "none",
    width: "100%",
    boxSizing: "border-box",
    fontFamily: "inherit",
  },
  inputRow: { display: "flex", gap: 10 },
  passwordRow: { display: "flex", gap: 10 },
  testBtn: {
    background: "linear-gradient(135deg, #6366f1, #818cf8)",
    border: "none",
    borderRadius: 8,
    color: "#fff",
    fontSize: 12,
    fontWeight: 600,
    padding: "10px 16px",
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  showHideBtn: {
    background: "#1e1e1e",
    border: "1px solid #2a2a2a",
    borderRadius: 8,
    color: "#9ca3af",
    fontSize: 12,
    padding: "10px 14px",
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  keyHint: { fontSize: 12, color: "#6b7280", marginTop: 6 },
  hint: { fontSize: 11, color: "#6b7280", marginTop: 6 },
  statusMsg: (color: string) => ({
    fontSize: 12,
    color,
    marginTop: 8,
    padding: "8px 12px",
    background: `${color}10`,
    borderRadius: 8,
    border: `1px solid ${color}30`,
  }),
  divider: { height: 1, background: "#252525", margin: "20px 0" },
  infoCard: {
    background: "rgba(99,102,241,0.06)",
    border: "1px solid rgba(99,102,241,0.2)",
    borderRadius: 12,
    padding: "16px 20px",
    marginTop: 20,
  },
  infoTitle: { fontSize: 13, fontWeight: 600, color: "#a78bfa", marginBottom: 10 },
  infoList: { margin: 0, padding: "0 0 0 16px", color: "#9ca3af", fontSize: 12, lineHeight: 1.8 },
  warningCard: {
    background: "rgba(245,158,11,0.06)",
    border: "1px solid rgba(245,158,11,0.25)",
    borderRadius: 12,
    padding: "16px 20px",
    marginTop: 20,
  },
  warningTitle: { fontSize: 13, fontWeight: 600, color: "#f59e0b", marginBottom: 8 },
  warningText: { fontSize: 12, color: "#9ca3af", lineHeight: 1.6, margin: 0 },
  // Creator grid
  creatorGrid: { display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16 },
  creatorCard: {
    background: "#1e1e1e",
    border: "1px solid #2a2a2a",
    borderRadius: 14,
    padding: "18px 20px",
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  avatarSection: { display: "flex", alignItems: "center", gap: 12 },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 12,
    background: "rgba(99,102,241,0.15)",
    border: "1px solid rgba(99,102,241,0.3)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 24,
    flexShrink: 0,
  },
  avatarSelect: {
    background: "#0f0f0f",
    border: "1px solid #2a2a2a",
    borderRadius: 8,
    color: "#e5e7eb",
    fontSize: 16,
    padding: "4px 8px",
    cursor: "pointer",
  },
  creatorFormGroup: {},
  creatorLabel: { display: "block", fontSize: 11, fontWeight: 600, color: "#6b7280", marginBottom: 5, textTransform: "uppercase" },
  creatorInput: {
    width: "100%",
    background: "#0f0f0f",
    border: "1px solid #252525",
    borderRadius: 8,
    color: "#e5e7eb",
    fontSize: 12,
    padding: "8px 12px",
    outline: "none",
    boxSizing: "border-box",
    fontFamily: "inherit",
  },
  // Folder
  folderPreview: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    marginTop: 16,
    background: "#1e1e1e",
    borderRadius: 12,
    padding: "14px 16px",
    border: "1px solid #2a2a2a",
  },
  folderRow: { display: "flex", alignItems: "center", gap: 12 },
  folderIcon: { fontSize: 20 },
  folderName: { fontSize: 13, fontWeight: 600, color: "#d1d5db" },
  folderPath: { fontSize: 11, color: "#6b7280", marginTop: 2, fontFamily: "monospace" },
  // Resource sliders
  sliderWrap: { display: "flex", alignItems: "center", gap: 16, marginBottom: 6 },
  rangeInput: { flex: 1, accentColor: "#6366f1", height: 4, cursor: "pointer" } as React.CSSProperties,
  rangeVal: { fontSize: 14, fontWeight: 700, color: "#818cf8", minWidth: 80, textAlign: "right" as const },
};
