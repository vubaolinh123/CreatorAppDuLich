import React, { useState } from "react";
import { useAppStore } from "../stores/appStore";


// ── Types ──────────────────────────────────────────────────────────────────
type LibraryStatus = "local" | "synced" | "published";

interface LibraryItem {
  id: string;
  topic: string;
  creator: string;
  status: LibraryStatus;
  createdAt: string;
  views?: number;
  likes?: number;
  script: { hook: string; body: string; cta: string };
  captions: { caption_short: string; caption_long: string; hashtags: string[] };
  imagePrompts: string[];
  videoPath: string;
}

interface LibraryScreenProps {
  onNavigate?: (screen: string) => void;
}

// ── Helpers ────────────────────────────────────────────────────────────────
type FilterTab = "all" | "local" | "synced" | "published";

const FILTER_TABS: { id: FilterTab; label: string; icon: string }[] = [
  { id: "all", label: "Tất cả", icon: "📦" },
  { id: "local", label: "Chờ đồng bộ", icon: "⏳" },
  { id: "synced", label: "Đã đồng bộ", icon: "☁️" },
  { id: "published", label: "Đã đăng", icon: "✅" },
];

const GRADIENT_THUMBS = [
  "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
  "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
  "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
  "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
  "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",
];

function statusConfig(s: LibraryStatus) {
  const map: Record<LibraryStatus, { text: string; color: string; bg: string }> = {
    local: { text: "Chờ đồng bộ", color: "#f59e0b", bg: "rgba(245,158,11,0.12)" },
    synced: { text: "Đã đồng bộ", color: "#818cf8", bg: "rgba(129,140,248,0.12)" },
    published: { text: "Đã đăng", color: "#10b981", bg: "rgba(16,185,129,0.12)" },
  };
  return map[s];
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function formatNumber(n?: number) {
  if (!n) return null;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

// ── Main Component ─────────────────────────────────────────────────────────
export default function LibraryScreen({ onNavigate }: LibraryScreenProps) {
  const [filter, setFilter] = useState<FilterTab>("all");
  const [search, setSearch] = useState("");
  const [selectedItem, setSelectedItem] = useState<LibraryItem | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);

  const storeLibrary = useAppStore((s) => s.library);
  const syncItem = useAppStore((s) => s.syncItem);

  // Map Zustand library items to the local LibraryItem interface structure
  const library: LibraryItem[] = storeLibrary.map((item) => ({
    id: item.id,
    topic: item.topic,
    creator: item.creator,
    status: item.status,
    createdAt: item.createdAt,
    views: item.views,
    likes: item.likes,
    script: item.result.script,
    captions: {
      caption_short: item.result.captions.caption_short,
      caption_long: item.result.captions.caption_long,
      hashtags: item.result.captions.hashtags || [],
    },
    imagePrompts: item.result.images?.prompts || [],
    videoPath: item.result.videoPath || "",
  }));

  const filtered = library.filter((item) => {
    const matchFilter = filter === "all" || item.status === filter;
    const matchSearch =
      !search.trim() ||
      item.topic.toLowerCase().includes(search.toLowerCase()) ||
      item.creator.toLowerCase().includes(search.toLowerCase());
    return matchFilter && matchSearch;
  });

  const handleSync = async (item: LibraryItem, e: React.MouseEvent) => {
    e.stopPropagation();
    setSyncingId(item.id);
    try {
      await syncItem(item.id);
    } catch (err) {
      console.error(err);
    }
    setSyncingId(null);
  };

  const counts: Record<FilterTab, number> = {
    all: library.length,
    local: library.filter((i) => i.status === "local").length,
    synced: library.filter((i) => i.status === "synced").length,
    published: library.filter((i) => i.status === "published").length,
  };

  return (
    <div style={s.container}>
      {/* Header */}
      <div style={s.header}>
        <div>
          <h1 style={s.title}>📋 Thư viện bài</h1>
          <p style={s.subtitle}>{library.length} bài đã tạo</p>
        </div>
        <button style={s.createBtn} onClick={() => onNavigate?.("studio")}>
          ✨ Tạo bài mới
        </button>
      </div>

      {/* Search + Filter */}
      <div style={s.controls}>
        <div style={s.searchWrap}>
          <span style={s.searchIcon}>🔍</span>
          <input
            style={s.searchInput}
            placeholder="Tìm kiếm bài viết..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div style={s.filterTabs}>
          {FILTER_TABS.map((tab) => (
            <button
              key={tab.id}
              style={{
                ...s.filterTab,
                ...(filter === tab.id ? s.filterTabActive : {}),
              }}
              onClick={() => setFilter(tab.id)}
            >
              {tab.icon} {tab.label}
              <span style={{ ...s.countBadge, opacity: filter === tab.id ? 1 : 0.6 }}>
                {counts[tab.id]}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Content Area */}
      <div style={s.contentArea}>
        {/* Grid */}
        <div style={{ ...s.gridArea, width: selectedItem ? "calc(100% - 380px)" : "100%" }}>
          {filtered.length === 0 ? (
            <EmptyState onNavigate={onNavigate} />
          ) : (
            <div style={{ ...s.grid, gridTemplateColumns: selectedItem ? "repeat(2, 1fr)" : "repeat(3, 1fr)" }}>
              {filtered.map((item, idx) => (
                <LibraryCard
                  key={item.id}
                  item={item}
                  gradientBg={GRADIENT_THUMBS[idx % GRADIENT_THUMBS.length]}
                  isSelected={selectedItem?.id === item.id}
                  isSyncing={syncingId === item.id}
                  onClick={() => setSelectedItem(selectedItem?.id === item.id ? null : item)}
                  onSync={handleSync}
                />
              ))}
            </div>
          )}
        </div>

        {/* Detail Panel */}
        {selectedItem && (
          <DetailPanel item={selectedItem} onClose={() => setSelectedItem(null)} />
        )}
      </div>
    </div>
  );
}

// ── Library Card ──────────────────────────────────────────────────────────
function LibraryCard({
  item,
  gradientBg,
  isSelected,
  isSyncing,
  onClick,
  onSync,
}: {
  item: LibraryItem;
  gradientBg: string;
  isSelected: boolean;
  isSyncing: boolean;
  onClick: () => void;
  onSync: (item: LibraryItem, e: React.MouseEvent) => void;
}) {
  const sc = statusConfig(item.status);
  const views = formatNumber(item.views);
  const likes = formatNumber(item.likes);

  return (
    <div
      style={{
        ...s.card,
        ...(isSelected ? s.cardSelected : {}),
      }}
      onClick={onClick}
    >
      {/* Thumbnail */}
      <div style={{ ...s.thumbnail, background: gradientBg }}>
        <div style={s.thumbnailOverlay}>
          {item.videoPath ? "🎬" : "📝"}
        </div>
        <span style={{ ...s.statusBadge, color: sc.color, background: sc.bg }}>
          {sc.text}
        </span>
      </div>

      {/* Content */}
      <div style={s.cardContent}>
        <div style={s.cardTopic}>{item.topic}</div>
        <div style={s.cardMeta}>
          <span style={s.creatorChip}>{item.creator}</span>
          <span style={s.dateText}>{formatDate(item.createdAt)}</span>
        </div>

        {views && (
          <div style={s.statsRow}>
            <span style={s.stat}>👁️ {views}</span>
            <span style={s.stat}>❤️ {likes}</span>
          </div>
        )}

        {/* Actions */}
        <div style={s.cardActions} onClick={(e) => e.stopPropagation()}>
          <button style={s.detailBtn} onClick={onClick}>
            Chi tiết
          </button>
          {item.status === "local" && (
            <button
              style={{ ...s.syncBtn, opacity: isSyncing ? 0.6 : 1 }}
              onClick={(e) => onSync(item, e)}
              disabled={isSyncing}
            >
              {isSyncing ? "⏳ Đang sync..." : "☁️ Đồng bộ"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Detail Panel ──────────────────────────────────────────────────────────
function DetailPanel({ item, onClose }: { item: LibraryItem; onClose: () => void }) {
  const [tab, setTab] = useState<"script" | "captions" | "prompts">("script");
  const sc = statusConfig(item.status);

  return (
    <div style={s.detailPanel}>
      {/* Panel Header */}
      <div style={s.panelHeader}>
        <div style={s.panelTitle}>Chi tiết bài viết</div>
        <button style={s.closeBtn} onClick={onClose}>✕</button>
      </div>

      {/* Status */}
      <span style={{ ...s.statusBadge, color: sc.color, background: sc.bg, display: "inline-block", marginBottom: 12 }}>
        {sc.text}
      </span>

      <div style={s.panelTopic}>{item.topic}</div>
      <div style={s.panelCreator}>👤 {item.creator} · {formatDate(item.createdAt)}</div>

      {/* Tabs */}
      <div style={s.panelTabs}>
        {[
          { id: "script", label: "📝 Kịch bản" },
          { id: "captions", label: "📢 Captions" },
          { id: "prompts", label: "🎨 Prompts" },
        ].map((t) => (
          <button
            key={t.id}
            style={{ ...s.panelTab, ...(tab === t.id ? s.panelTabActive : {}) }}
            onClick={() => setTab(t.id as typeof tab)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={s.panelContent}>
        {tab === "script" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <ScriptBlock color="#818cf8" label="🎣 Hook" text={item.script.hook} />
            <ScriptBlock color="#34d399" label="📖 Body" text={item.script.body} />
            <ScriptBlock color="#fb923c" label="📣 CTA" text={item.script.cta} />
          </div>
        )}
        {tab === "captions" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={s.captionBlock}>
              <div style={s.captionLabel}>Caption ngắn</div>
              <div style={s.captionText}>{item.captions.caption_short}</div>
            </div>
            <div style={s.captionBlock}>
              <div style={s.captionLabel}>Caption dài</div>
              <div style={s.captionText}>{item.captions.caption_long}</div>
            </div>
            <div style={s.hashtagWrap}>
              {item.captions.hashtags.map((h) => (
                <span key={h} style={s.hashtagChip}>{h}</span>
              ))}
            </div>
          </div>
        )}
        {tab === "prompts" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {item.imagePrompts.map((p, i) => (
              <div key={i} style={s.promptItem}>
                <div style={s.promptNum}>{i + 1}</div>
                <div style={s.promptText}>{p}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* File paths */}
      {item.videoPath && (
        <div style={s.fileRow}>
          <span>🎬</span>
          <div style={s.filePath}>{item.videoPath}</div>
        </div>
      )}
    </div>
  );
}

// ── Script Block ──────────────────────────────────────────────────────────
function ScriptBlock({ color, label, text }: { color: string; label: string; text: string }) {
  return (
    <div style={{ border: `1px solid ${color}30`, background: `${color}08`, borderRadius: 10, padding: "12px 14px" }}>
      <div style={{ fontSize: 11, fontWeight: 700, color, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 13, color: "#d1d5db", lineHeight: 1.6 }}>{text}</div>
    </div>
  );
}

// ── Empty State ───────────────────────────────────────────────────────────
function EmptyState({ onNavigate }: { onNavigate?: (s: string) => void }) {
  return (
    <div style={s.emptyState}>
      <div style={s.emptyIcon}>📭</div>
      <div style={s.emptyTitle}>Chưa có bài viết nào</div>
      <div style={s.emptySub}>Hãy tạo bài đầu tiên của bạn ngay!</div>
      <button style={s.emptyBtn} onClick={() => onNavigate?.("studio")}>
        ✨ Tạo bài ngay
      </button>
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
    marginBottom: 24,
    flexShrink: 0,
  },
  title: { fontSize: 24, fontWeight: 700, color: "#f1f1f1", margin: 0 },
  subtitle: { fontSize: 13, color: "#6b7280", margin: "4px 0 0" },
  createBtn: {
    background: "linear-gradient(135deg, #6366f1, #818cf8)",
    border: "none",
    borderRadius: 10,
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    padding: "10px 20px",
    cursor: "pointer",
    boxShadow: "0 4px 12px rgba(99,102,241,0.3)",
  },
  controls: { display: "flex", flexDirection: "column", gap: 12, marginBottom: 20, flexShrink: 0 },
  searchWrap: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    background: "#161616",
    border: "1px solid #252525",
    borderRadius: 10,
    padding: "0 14px",
  },
  searchIcon: { fontSize: 14, color: "#6b7280" },
  searchInput: {
    background: "none",
    border: "none",
    outline: "none",
    color: "#e5e7eb",
    fontSize: 13,
    padding: "10px 0",
    flex: 1,
  },
  filterTabs: { display: "flex", gap: 6 },
  filterTab: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    background: "#161616",
    border: "1px solid #252525",
    borderRadius: 8,
    color: "#9ca3af",
    fontSize: 12,
    fontWeight: 500,
    padding: "7px 12px",
    cursor: "pointer",
    transition: "all 0.15s",
  },
  filterTabActive: {
    background: "rgba(99,102,241,0.15)",
    borderColor: "rgba(99,102,241,0.4)",
    color: "#a78bfa",
  },
  countBadge: {
    background: "#2a2a2a",
    borderRadius: 20,
    padding: "1px 7px",
    fontSize: 11,
    color: "#6b7280",
  },
  contentArea: {
    display: "flex",
    gap: 20,
    flex: 1,
    minHeight: 0,
    overflow: "hidden",
  },
  gridArea: { overflowY: "auto", transition: "width 0.3s ease" },
  grid: {
    display: "grid",
    gap: 16,
  },
  card: {
    background: "#161616",
    border: "1px solid #252525",
    borderRadius: 14,
    overflow: "hidden",
    cursor: "pointer",
    transition: "border-color 0.2s, transform 0.15s",
  },
  cardSelected: {
    borderColor: "rgba(99,102,241,0.5)",
    boxShadow: "0 0 0 1px rgba(99,102,241,0.2)",
  },
  thumbnail: {
    height: 140,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
  },
  thumbnailOverlay: {
    fontSize: 40,
    opacity: 0.6,
  },
  statusBadge: {
    position: "absolute",
    top: 10,
    right: 10,
    fontSize: 11,
    fontWeight: 600,
    padding: "3px 10px",
    borderRadius: 20,
  },
  cardContent: { padding: "14px 16px" },
  cardTopic: {
    fontSize: 13,
    fontWeight: 600,
    color: "#e5e7eb",
    lineHeight: 1.5,
    marginBottom: 8,
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
  },
  cardMeta: { display: "flex", alignItems: "center", gap: 8, marginBottom: 8 },
  creatorChip: {
    fontSize: 11,
    background: "rgba(99,102,241,0.1)",
    color: "#818cf8",
    borderRadius: 6,
    padding: "2px 8px",
    border: "1px solid rgba(99,102,241,0.2)",
  },
  dateText: { fontSize: 11, color: "#6b7280" },
  statsRow: { display: "flex", gap: 12, marginBottom: 10 },
  stat: { fontSize: 12, color: "#9ca3af" },
  cardActions: { display: "flex", gap: 8 },
  detailBtn: {
    flex: 1,
    background: "#1e1e1e",
    border: "1px solid #2a2a2a",
    borderRadius: 8,
    color: "#d1d5db",
    fontSize: 12,
    fontWeight: 500,
    padding: "7px 0",
    cursor: "pointer",
  },
  syncBtn: {
    flex: 1,
    background: "linear-gradient(135deg, #6366f1, #818cf8)",
    border: "none",
    borderRadius: 8,
    color: "#fff",
    fontSize: 12,
    fontWeight: 600,
    padding: "7px 0",
    cursor: "pointer",
  },
  // Detail Panel
  detailPanel: {
    width: 360,
    flexShrink: 0,
    background: "#161616",
    border: "1px solid #252525",
    borderRadius: 16,
    padding: "20px",
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: 0,
  },
  panelHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
  },
  panelTitle: { fontSize: 14, fontWeight: 700, color: "#e5e7eb" },
  closeBtn: {
    background: "#1e1e1e",
    border: "1px solid #2a2a2a",
    borderRadius: 6,
    color: "#9ca3af",
    width: 28,
    height: 28,
    cursor: "pointer",
    fontSize: 12,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  panelTopic: {
    fontSize: 13,
    fontWeight: 600,
    color: "#e5e7eb",
    lineHeight: 1.5,
    marginBottom: 6,
  },
  panelCreator: { fontSize: 12, color: "#6b7280", marginBottom: 14 },
  panelTabs: { display: "flex", gap: 4, marginBottom: 14 },
  panelTab: {
    flex: 1,
    background: "#1e1e1e",
    border: "1px solid #252525",
    borderRadius: 8,
    color: "#6b7280",
    fontSize: 11,
    fontWeight: 500,
    padding: "6px 4px",
    cursor: "pointer",
    textAlign: "center",
  },
  panelTabActive: {
    background: "rgba(99,102,241,0.15)",
    borderColor: "rgba(99,102,241,0.35)",
    color: "#a78bfa",
  },
  panelContent: { flex: 1, overflowY: "auto" },
  captionBlock: {
    background: "#1e1e1e",
    borderRadius: 10,
    padding: "12px 14px",
    border: "1px solid #2a2a2a",
  },
  captionLabel: { fontSize: 10, fontWeight: 600, color: "#6b7280", textTransform: "uppercase", marginBottom: 6 },
  captionText: { fontSize: 12, color: "#d1d5db", lineHeight: 1.6 },
  hashtagWrap: { display: "flex", flexWrap: "wrap", gap: 6 },
  hashtagChip: {
    fontSize: 11,
    background: "rgba(99,102,241,0.1)",
    color: "#818cf8",
    borderRadius: 20,
    padding: "3px 10px",
    border: "1px solid rgba(99,102,241,0.2)",
  },
  promptItem: { display: "flex", gap: 10, alignItems: "flex-start" },
  promptNum: {
    width: 22,
    height: 22,
    borderRadius: "50%",
    background: "rgba(99,102,241,0.15)",
    border: "1px solid rgba(99,102,241,0.3)",
    color: "#818cf8",
    fontSize: 11,
    fontWeight: 700,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  promptText: { fontSize: 12, color: "#9ca3af", lineHeight: 1.6, flex: 1 },
  fileRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    background: "#1e1e1e",
    borderRadius: 8,
    padding: "10px 12px",
    marginTop: 12,
    border: "1px solid #2a2a2a",
  },
  filePath: { fontSize: 11, color: "#6b7280", wordBreak: "break-all", flex: 1 },
  // Empty
  emptyState: {
    gridColumn: "1 / -1",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "60px 0",
    gap: 12,
  },
  emptyIcon: { fontSize: 56, marginBottom: 8 },
  emptyTitle: { fontSize: 18, fontWeight: 700, color: "#d1d5db" },
  emptySub: { fontSize: 13, color: "#6b7280" },
  emptyBtn: {
    marginTop: 8,
    background: "linear-gradient(135deg, #6366f1, #818cf8)",
    border: "none",
    borderRadius: 10,
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    padding: "10px 24px",
    cursor: "pointer",
  },
};
