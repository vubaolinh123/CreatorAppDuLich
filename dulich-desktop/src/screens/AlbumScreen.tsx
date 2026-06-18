import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";

/* ── Types ───────────────────────────────────────────────────────── */
interface PhotoItem {
  id: string;
  title: string;
  path: string;
  format?: string;
  source?: string;
}

interface AlbumData {
  id: string;
  albumName: string;
  creator: string;
  topic: string;
  description: string;
  photos: PhotoItem[];
  createdAt: string;
}

interface SeedingRestaurant {
  id: string;
  name: string;
  category: string;
  location: string;
  description: string;
}

/* ── Constants ───────────────────────────────────────────────────── */
const CREATORS = [
  { id: "lan_anh", name: "Lan Anh" },
  { id: "minh_tuan", name: "Minh Tuấn" },
  { id: "thu_ha", name: "Thu Hà" },
  { id: "duc_anh", name: "Đức Anh" },
  { id: "ngoc_mai", name: "Ngọc Mai" },
];

const TOPICS = [
  "Phú Quốc", "Đà Nẵng", "Hội An", "Nha Trang", "Đà Lạt",
  "Hà Nội", "Sapa", "Ninh Bình", "Phú Yên", "Bình Định",
];

const SEEDING_STYLES = [
  { id: "modern", name: "Hiện đại", emoji: "✨" },
  { id: "cute", name: "Dễ thương", emoji: "🌸" },
  { id: "bold", name: "Mạnh mẽ", emoji: "🔥" },
  { id: "minimal", name: "Tối giản", emoji: "🤍" },
  { id: "vintage", name: "Cổ điển", emoji: "📽️" },
  { id: "neon", name: "Neon", emoji: "💜" },
];



const FORMATS: Record<string, string> = {
  story: "Story (1080×1920)",
  feed_square: "Feed Vuông (1080×1080)",
  feed_portrait: "Feed Portrait (1080×1350)",
  reels_cover: "Reels Cover (1080×1920)",
};

const TEXT_COLORS = ["#ffffff", "#ffcc00", "#ff6b35", "#e040fb", "#00e5ff", "#76ff03"];
const CARD_TITLE_COLORS = ["#8B0000", "#B22222", "#CC3333", "#800020", "#660000", "#990000"];

const STORAGE_KEY = "dulich_albums";

/* ── Local Storage Helpers ───────────────────────────────────────── */
function loadAlbums(): AlbumData[] {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); } catch { return []; }
}
function saveAlbums(albums: AlbumData[]) { localStorage.setItem(STORAGE_KEY, JSON.stringify(albums)); }
function loadSeedingItems(): SeedingRestaurant[] {
  try { return JSON.parse(localStorage.getItem("dulich_seeding_items") || "[]"); } catch { return []; }
}

/* ── roundRect Polyfill ──────────────────────────────────────────── */
function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number | number[]) {
  const radii = Array.isArray(r) ? r : [r, r, r, r];
  const [tl, tr, br, bl] = radii;
  ctx.beginPath();
  ctx.moveTo(x + tl, y);
  ctx.lineTo(x + w - tr, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + tr);
  ctx.lineTo(x + w, y + h - br);
  ctx.quadraticCurveTo(x + w, y + h, x + w - br, y + h);
  ctx.lineTo(x + bl, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - bl);
  ctx.lineTo(x, y + tl);
  ctx.quadraticCurveTo(x, y, x + tl, y);
  ctx.closePath();
}

/* ── Image loader (supports local files, data URLs, and remote URLs) ── */
async function loadImage(src: string): Promise<HTMLImageElement> {
  // data URLs always work
  if (src.startsWith("data:")) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("Không load được ảnh data URL"));
      img.src = src;
    });
  }

  // Local file paths — use Tauri convertFileSrc to get safe asset URL
  if (src.startsWith("C:\\\\") || src.startsWith("D:\\\\") || src.startsWith("/home/") || src.startsWith("/Users/") || src.includes("\\\\.dulichapp\\\\")) {
    try {
      const { convertFileSrc } = await import("@tauri-apps/api/core");
      const assetUrl = convertFileSrc(src);
      return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error(`Không load được file: ${src.slice(0, 60)}`));
        img.src = assetUrl;
      });
    } catch (e: any) {
      // Fallback: try reading as data URL or direct
    }
  }

  // Remote URLs — try Tauri Rust backend first (bypasses CORS)
  try {
    const dataUrl: string = await invoke<string>("fetch_image_as_base64", { url: src });
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("Không load được ảnh từ base64"));
      img.src = dataUrl;
    });
  } catch (_e) {
    // invoke failed — fallback to direct fetch
  }

  // Last resort: direct fetch (may fail with CORS)
  const res = await fetch(src);
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Không load được ảnh: ${src.slice(0, 60)}`));
    img.src = blobUrl;
  });
}

/* ── Convert local path to displayable URL (for img src) ──────────── */
let _convertFileSrc: ((path: string, protocol?: string) => string) | null = null;
async function initConvertFileSrc() {
  if (_convertFileSrc) return;
  try {
    const mod = await import("@tauri-apps/api/core");
    _convertFileSrc = mod.convertFileSrc;
  } catch {}
}
function toDisplayUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("data:") || path.startsWith("http") || path.startsWith("blob:")) return path;
  if (_convertFileSrc) return _convertFileSrc(path);
  return path;
}

/* ── Shuffle array ───────────────────────────────────────────────── */
function shuffleArray<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/* ── Draw background (cover mode) ────────────────────────────────── */
function drawBackgroundCover(ctx: CanvasRenderingContext2D, w: number, h: number, img: HTMLImageElement) {
  const imgRatio = img.width / img.height;
  const canvasRatio = w / h;
  let sx = 0, sy = 0, sw = img.width, sh = img.height;
  if (imgRatio > canvasRatio) {
    sw = img.height * canvasRatio;
    sx = (img.width - sw) / 2;
  } else {
    sh = img.width / canvasRatio;
    sy = (img.height - sh) / 2;
  }
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, w, h);
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   HOOK IMAGE RENDERER — Ảnh đầu: Photo + Hook text lớn nổi bật
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
async function renderHookImage(config: {
  hook: string;          // "99% khách du lịch"
  subtitle: string;      // "chưa biết những điều này hoặc chưa từng trải nghiệm"
  locationTag: string;   // "Dalat"
  dateTag: string;       // "Tháng 5"
  handleTag: string;     // "@thamhiemdalat"
  style: string;
  fontStyle: string;
  textColor: string;
  format: string;
  bgImageSrc: string;
}): Promise<string> {
  const dims: Record<string, [number, number]> = {
    story: [540, 960], feed_square: [540, 540], feed_portrait: [540, 675], reels_cover: [540, 960],
  };
  const [w, h] = dims[config.format] || [540, 540];
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d")!;

  // 1) Photo background — KHÔNG overlay, photo rõ ràng
  const bgImg = await loadImage(config.bgImageSrc);
  drawBackgroundCover(ctx, w, h, bgImg);

  // 2) Style decorations trên ảnh
  if (config.style === "neon") {
    ctx.shadowColor = "#e040fb";
    ctx.shadowBlur = 30;
    ctx.strokeStyle = "#e040fb";
    ctx.lineWidth = 2;
    ctx.strokeRect(20, 20, w - 40, h - 40);
    ctx.shadowBlur = 0;
  } else if (config.style === "cute") {
    ctx.globalAlpha = 0.15;
    for (let i = 0; i < 15; i++) {
      ctx.fillStyle = ["#f48fb1", "#ce93d8", "#81d4fa", "#fff176"][i % 4];
      ctx.font = `${14 + Math.random() * 16}px sans-serif`;
      ctx.fillText(["🌸", "⭐", "🎀", "💖"][i % 4], Math.random() * w, Math.random() * h);
    }
    ctx.globalAlpha = 1;
  }

  // 3) Tags ở trên cùng — Location tag, Date tag, Handle tag
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  const tagY = 40;
  let tagX = 30;

  if (config.locationTag) {
    // Location tag — pill-shaped, filled
    const locText = `📍 ${config.locationTag}`;
    ctx.font = "bold 12px sans-serif";
    const locW = ctx.measureText(locText).width + 20;
    roundRect(ctx, tagX, tagY, locW, 26, 13);
    ctx.fillStyle = "rgba(139, 0, 0, 0.85)";
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.fillText(locText, tagX + 10, tagY + 6);
    tagX += locW + 8;
  }

  if (config.dateTag) {
    const dateText = config.dateTag;
    ctx.font = "11px sans-serif";
    const dateW = ctx.measureText(dateText).width + 16;
    roundRect(ctx, tagX, tagY, dateW, 26, 13);
    ctx.fillStyle = "rgba(139, 0, 0, 0.85)";
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.fillText(dateText, tagX + 8, tagY + 6);
    tagX += dateW + 8;
  }

  if (config.handleTag) {
    const handleText = config.handleTag;
    ctx.font = "11px sans-serif";
    const handleW = ctx.measureText(handleText).width + 16;
    roundRect(ctx, tagX, tagY, handleW, 26, 13);
    ctx.fillStyle = "rgba(139, 0, 0, 0.85)";
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.fillText(handleText, tagX + 8, tagY + 6);
  }

  // 4) Hook text — LỚN, NỔI BẬT, ở giữa ảnh
  // Tách phần đầu (VD: "99%") và phần sau (VD: "khách du lịch")
  const hookParts = config.hook.split("\n");
  const mainHook = hookParts[0] || config.hook;
  const subHook = hookParts[1] || "";

  // Hook chính — rất lớn, vàng/đậm
  const hookFontSize = w * 0.16;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  // Shadow trước
  ctx.shadowColor = "rgba(0,0,0,0.8)";
  ctx.shadowBlur = 20;
  ctx.shadowOffsetX = 3;
  ctx.shadowOffsetY = 3;

  // Vẽ hook text
  const hookColor = config.textColor === "#ffffff" ? "#FFD700" : config.textColor;
  ctx.fillStyle = hookColor;
  ctx.font = `bold ${hookFontSize}px "Arial Black", Impact, sans-serif`;
  ctx.fillText(mainHook, w / 2, h * 0.35);

  // Sub-hook (nếu có)
  if (subHook) {
    ctx.font = `italic bold ${hookFontSize * 0.7}px "Arial Black", Impact, sans-serif`;
    ctx.fillStyle = hookColor;
    ctx.fillText(subHook, w / 2, h * 0.35 + hookFontSize * 0.9);
  }

  // Reset shadow
  ctx.shadowColor = "transparent";
  ctx.shadowBlur = 0;
  ctx.shadowOffsetX = 0;
  ctx.shadowOffsetY = 0;

  // 5) Subtitle — trắng, nhỏ hơn, ở dưới hook
  if (config.subtitle) {
    const subFontSize = w * 0.04;
    ctx.font = `${subFontSize}px sans-serif`;
    ctx.fillStyle = "#ffffff";
    ctx.shadowColor = "rgba(0,0,0,0.7)";
    ctx.shadowBlur = 10;

    // Word wrap
    const maxLineWidth = w * 0.85;
    const words = config.subtitle.split(" ");
    const lines: string[] = [];
    let currentLine = "";
    for (const word of words) {
      const test = currentLine ? `${currentLine} ${word}` : word;
      if (ctx.measureText(test).width > maxLineWidth && currentLine) {
        lines.push(currentLine);
        currentLine = word;
      } else {
        currentLine = test;
      }
    }
    if (currentLine) lines.push(currentLine);

    const lineHeight = subFontSize * 1.5;
    const startY = subHook
      ? h * 0.35 + hookFontSize * 0.9 + hookFontSize * 0.7 * 0.9 + 30
      : h * 0.35 + hookFontSize * 0.9 + 20;

    for (let i = 0; i < lines.length; i++) {
      ctx.fillText(lines[i], w / 2, startY + i * lineHeight);
    }
    ctx.shadowColor = "transparent";
    ctx.shadowBlur = 0;
  }

  return canvas.toDataURL("image/png");
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   CONTENT IMAGE RENDERER — Ảnh sau: Photo + White card with info
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
async function renderContentImage(config: {
  title: string;         // "BẬT GG MAP CHẾ ĐỘ Ô TÔ"
  content: string;       // Paragraph hoặc bullet list
  contentMode: "paragraph" | "list";
  format: string;
  bgImageSrc: string;
  cardTitleColor?: string;
}): Promise<string> {
  const dims: Record<string, [number, number]> = {
    story: [540, 960], feed_square: [540, 540], feed_portrait: [540, 675], reels_cover: [540, 960],
  };
  const [w, h] = dims[config.format] || [540, 540];
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d")!;

  // 1) Photo background — full, rõ ràng
  const bgImg = await loadImage(config.bgImageSrc);
  drawBackgroundCover(ctx, w, h, bgImg);

  // 2) White card ở trên cùng
  const cardPadding = 20;
  const cardMarginX = 24;
  const cardWidth = w - cardMarginX * 2;
  const titleFontSize = Math.max(13, w * 0.04);
  const contentFontSize = Math.max(11, w * 0.033);
  const lineHeight = contentFontSize * 1.6;
  const titleLineHeight = titleFontSize * 1.4;

  // Tính chiều cao card
  ctx.font = `bold ${titleFontSize}px sans-serif`;
  const titleLines = wrapText(ctx, config.title, cardWidth - cardPadding * 2);
  const titleHeight = titleLines.length * titleLineHeight;

  // Tính nội dung
  const contentLines: string[] = [];
  if (config.contentMode === "list") {
    // Bullet list
    const items = config.content.split("\n").filter(l => l.trim());
    for (const item of items) {
      const wrapped = wrapText(ctx, `• ${item.trim()}`, cardWidth - cardPadding * 2);
      contentLines.push(...wrapped);
    }
  } else {
    // Paragraph
    const wrapped = wrapText(ctx, config.content, cardWidth - cardPadding * 2);
    contentLines.push(...wrapped);
  }
  const contentHeight = contentLines.length * lineHeight;
  const cardHeight = titleHeight + contentHeight + cardPadding * 3 + 10;

  // Vẽ white card
  const cardY = 24;
  roundRect(ctx, cardMarginX, cardY, cardWidth, cardHeight, 12);
  ctx.fillStyle = "#ffffff";
  ctx.fill();

  // Vẽ title (đỏ)
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.fillStyle = config.cardTitleColor || "#8B0000";
  ctx.font = `bold ${titleFontSize}px sans-serif`;
  let textY = cardY + cardPadding;
  for (const line of titleLines) {
    ctx.fillText(line, cardMarginX + cardPadding, textY);
    textY += titleLineHeight;
  }

  // Vẽ content (đen)
  textY += 6;
  ctx.fillStyle = "#1a1a1a";
  ctx.font = `${contentFontSize}px sans-serif`;
  for (const line of contentLines) {
    ctx.fillText(line, cardMarginX + cardPadding, textY);
    textY += lineHeight;
  }

  return canvas.toDataURL("image/png");
}

/* ── Helper: wrap text ───────────────────────────────────────────── */
function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const words = text.split(" ");
  const lines: string[] = [];
  let currentLine = "";
  for (const word of words) {
    const test = currentLine ? `${currentLine} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && currentLine) {
      lines.push(currentLine);
      currentLine = word;
    } else {
      currentLine = test;
    }
  }
  if (currentLine) lines.push(currentLine);
  return lines;
}

/* ══════════════════════════════════════════════════════════════════ */
/* MAIN COMPONENT                                                    */
/* ══════════════════════════════════════════════════════════════════ */
export default function AlbumScreen() {
  type Tab = "create_album" | "manage_albums" | "album_detail" | "seeding";
  const [tab, setTab] = useState<Tab>("create_album");

  const [albums, setAlbums] = useState<AlbumData[]>([]);
  const [selectedAlbum, setSelectedAlbum] = useState<AlbumData | null>(null);

  const [newAlbumName, setNewAlbumName] = useState("");
  const [newAlbumCreator, setNewAlbumCreator] = useState("lan_anh");
  const [newAlbumTopic, setNewAlbumTopic] = useState("Phú Quốc");

  const [photoTitle, setPhotoTitle] = useState("");
  const [photoPath, setPhotoPath] = useState("");
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // ── Seeding form ──
  const [seedHookMain, setSeedHookMain] = useState("99%");         // Phần lớn
  const [seedHookSub, setSeedHookSub] = useState("khách du lịch"); // Phần phụ
  const [seedSubtitle, setSeedSubtitle] = useState("chưa biết những điều này hoặc chưa từng trải nghiệm");
  const [seedLocationTag, setSeedLocationTag] = useState("");
  const [seedDateTag, setSeedDateTag] = useState("");
  const [seedHandleTag, setSeedHandleTag] = useState("");
  const [seedStyle, setSeedStyle] = useState("modern");
  const [seedFontStyle, ] = useState("bold");
  const [seedTextColor, setSeedTextColor] = useState("#FFD700");
  const [seedFormat, setSeedFormat] = useState("feed_square");
  const [seedTopic] = useState("Phú Quốc");

  // Content items (nội dung cho các ảnh sau hook)
  const [seedContentItems, setSeedContentItems] = useState<Array<{ title: string; content: string; mode: "paragraph" | "list" }>>([
    { title: "", content: "", mode: "paragraph" },
  ]);

  const [allSeedingItems, setAllSeedingItems] = useState<SeedingRestaurant[]>([]);
  const [seedPreviews, setSeedPreviews] = useState<string[]>([]);
  const [seedGenerating, setSeedGenerating] = useState(false);

  useEffect(() => { setAlbums(loadAlbums()); setAllSeedingItems(loadSeedingItems()); initConvertFileSrc(); }, []);

  // Set default location tag from topic
  useEffect(() => { if (seedTopic && !seedLocationTag) setSeedLocationTag(seedTopic); }, [seedTopic]);

  const persistAlbums = (updated: AlbumData[]) => { setAlbums(updated); saveAlbums(updated); };

  const showMsg = (type: "success" | "error", msg: string) => {
    if (type === "success") { setSuccessMsg(msg); setErrorMsg(""); }
    else { setErrorMsg(msg); setSuccessMsg(""); }
    setTimeout(() => { setSuccessMsg(""); setErrorMsg(""); }, 3000);
  };

  /* ── CREATE ALBUM ────────────────────────────────────────────── */
  const handleCreateAlbum = () => {
    if (!newAlbumName.trim()) { showMsg("error", "Vui lòng nhập tên album"); return; }
    const newAlbum: AlbumData = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 5),
      albumName: newAlbumName.trim(), creator: newAlbumCreator, topic: newAlbumTopic,
      description: "", photos: [], createdAt: new Date().toISOString(),
    };
    const updated = [newAlbum, ...albums]; persistAlbums(updated);
    setNewAlbumName(""); showMsg("success", "Tạo album thành công!");
    setSelectedAlbum(newAlbum); setTab("album_detail");
  };

  /* ── ADD PHOTO (manual URL) ──────────────────────────────────────── */
  const handleAddPhoto = () => {
    if (!selectedAlbum) return;
    if (!photoTitle.trim()) { showMsg("error", "Vui lòng nhập tên ảnh"); return; }
    const newPhoto: PhotoItem = {
      id: Date.now().toString(36), title: photoTitle.trim(),
      path: photoPath || "pending_upload", format: "original", source: "manual",
    };
    const updatedAlbum = { ...selectedAlbum, photos: [...selectedAlbum.photos, newPhoto] };
    const updatedAlbums = albums.map((a) => a.id === selectedAlbum.id ? updatedAlbum : a);
    persistAlbums(updatedAlbums); setSelectedAlbum(updatedAlbum);
    setPhotoTitle(""); setPhotoPath(""); showMsg("success", "Đã thêm ảnh!");
  };

  /* ── UPLOAD PHOTOS FROM DISK ─────────────────────────────────────── */
  const handleUploadPhotos = async () => {
    if (!selectedAlbum) return;
    try {
      const results: Array<{ id: string; title: string; localPath: string }> =
        await invoke("select_album_images", { albumId: selectedAlbum.id });
      if (!results || results.length === 0) return;
      const newPhotos: PhotoItem[] = results.map((r) => ({
        id: r.id, title: r.title, path: r.localPath, format: "original", source: "local",
      }));
      const updatedAlbum = { ...selectedAlbum, photos: [...selectedAlbum.photos, ...newPhotos] };
      const updatedAlbums = albums.map((a) => a.id === selectedAlbum.id ? updatedAlbum : a);
      persistAlbums(updatedAlbums); setSelectedAlbum(updatedAlbum);
      showMsg("success", `Đã thêm ${newPhotos.length} ảnh từ máy!`);
    } catch (err: any) {
      if (err?.toString().includes("No files selected")) return;
      showMsg("error", "Lỗi upload: " + err?.toString());
    }
  };

  const handleRemovePhoto = (photoId: string) => {
    if (!selectedAlbum) return;
    const updatedAlbum = { ...selectedAlbum, photos: selectedAlbum.photos.filter((p) => p.id !== photoId) };
    const updatedAlbums = albums.map((a) => a.id === selectedAlbum.id ? updatedAlbum : a);
    persistAlbums(updatedAlbums); setSelectedAlbum(updatedAlbum);
  };

  const handleDeleteAlbum = (albumId: string) => {
    if (!confirm("Bạn có chắc muốn xóa album này?")) return;
    const updated = albums.filter((a) => a.id !== albumId);
    persistAlbums(updated); setSelectedAlbum(null); setTab("manage_albums"); showMsg("success", "Đã xóa album.");
  };

  /* ── Content items helpers ────────────────────────────────────── */
  const updateContentItem = (index: number, field: string, value: string) => {
    const items = [...seedContentItems];
    (items[index] as any)[field] = value;
    setSeedContentItems(items);
  };
  const addContentItem = () => {
    setSeedContentItems([...seedContentItems, { title: "", content: "", mode: "paragraph" }]);
  };
  const removeContentItem = (index: number) => {
    if (seedContentItems.length <= 1) return;
    setSeedContentItems(seedContentItems.filter((_, i) => i !== index));
  };

  /* ── Lấy ảnh valid từ album ──────────────────────────────────── */
  const getValidPhotos = (): PhotoItem[] => {
    if (!selectedAlbum) return [];
    return selectedAlbum.photos.filter(p => p.path && p.path !== "pending_upload" && !p.path.startsWith("data:"));
  };

  /* ── GENERATE BATCH SEEDING ──────────────────────────────────── */
  const handleGenerateBatch = async () => {
    if (!seedHookMain.trim()) { showMsg("error", "Vui lòng nhập hook text"); return; }
    const validPhotos = getValidPhotos();
    if (validPhotos.length === 0) { showMsg("error", "Album chưa có ảnh URL/data. Hãy thêm ảnh vào album trước!"); return; }

    setSeedGenerating(true);
    setSeedPreviews([]);

    try {
      const previews: string[] = [];
      const shuffledPhotos = shuffleArray(validPhotos);

      // 1) Ảnh đầu — HOOK: dùng ảnh đầu tiên
      const hookPhoto = shuffledPhotos[0];
      const hookImage = await renderHookImage({
        hook: `${seedHookMain}\n${seedHookSub}`,
        subtitle: seedSubtitle,
        locationTag: seedLocationTag || seedTopic,
        dateTag: seedDateTag,
        handleTag: seedHandleTag,
        style: seedStyle,
        fontStyle: seedFontStyle,
        textColor: seedTextColor,
        format: seedFormat,
        bgImageSrc: hookPhoto.path,
      });
      previews.push(hookImage);

      // 2) Các ảnh sau — CONTENT: random ảnh, mỗi ảnh 1 nội dung
      for (let i = 0; i < seedContentItems.length; i++) {
        const item = seedContentItems[i];
        if (!item.title.trim() && !item.content.trim()) continue;

        // Random ảnh (không trùng hook ảnh)
        const photoIndex = (i + 1) % shuffledPhotos.length;
        const photo = shuffledPhotos[photoIndex] || shuffledPhotos[0];

        const contentImage = await renderContentImage({
          title: item.title || `Thông tin ${i + 1}`,
          content: item.content || "Nội dung...",
          contentMode: item.mode,
          format: seedFormat,
          bgImageSrc: photo.path,
          cardTitleColor: CARD_TITLE_COLORS[i % CARD_TITLE_COLORS.length],
        });
        previews.push(contentImage);
      }

      // Nếu không có content items, tạo 1 ảnh content mặc định từ quán seeding
      if (previews.length === 1 && allSeedingItems.length > 0) {
        const photo = shuffledPhotos[1] || shuffledPhotos[0];
        const restaurant = allSeedingItems[0];
        const contentImage = await renderContentImage({
          title: `${restaurant.name.toUpperCase()} — ${restaurant.location}`,
          content: restaurant.description || `${restaurant.name} là ${restaurant.category === "hotel" ? "khách sạn" : "quán ăn"} nằm tại ${restaurant.location}.`,
          contentMode: "paragraph",
          format: seedFormat,
          bgImageSrc: photo.path,
        });
        previews.push(contentImage);
      }

      setSeedPreviews(previews);
      showMsg("success", `Đã tạo ${previews.length} ảnh seeding!`);
    } catch (err: any) {
      showMsg("error", "Lỗi tạo ảnh: " + err.toString());
    } finally {
      setSeedGenerating(false);
    }
  };

  /* ── SAVE ALL SEEDING TO ALBUM ───────────────────────────────── */
  const handleSaveAllToAlbum = () => {
    if (!selectedAlbum || seedPreviews.length === 0) return;
    const newPhotos: PhotoItem[] = seedPreviews.map((preview, i) => ({
      id: `seed_${Date.now().toString(36)}_${i}`,
      title: i === 0 ? `Hook: ${seedHookMain} ${seedHookSub}` : `Content ${i}`,
      path: preview, format: seedFormat, source: "seeding",
    }));
    const updatedAlbum = { ...selectedAlbum, photos: [...selectedAlbum.photos, ...newPhotos] };
    const updatedAlbums = albums.map((a) => a.id === selectedAlbum.id ? updatedAlbum : a);
    persistAlbums(updatedAlbums); setSelectedAlbum(updatedAlbum);
    setSeedPreviews([]); showMsg("success", `Đã lưu ${newPhotos.length} ảnh seeding vào album!`);
  };

  /* ── DOWNLOAD SINGLE ─────────────────────────────────────────── */
  const handleDownload = (dataUrl: string, filename: string) => {
    const a = document.createElement("a"); a.href = dataUrl; a.download = filename; a.click();
  };

  /* ── SYNC TO DASHBOARD ───────────────────────────────────────── */
  const handleSyncToDashboard = async (album: AlbumData) => {
    setSaving(true);
    try {
      const res = await fetch("http://localhost:3000/api/albums", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ albumName: album.albumName, topic: album.topic, creatorId: album.creator, description: album.description, photos: album.photos }),
      });
      const data = await res.json();
      if (data.success) showMsg("success", "Đã sync lên Dashboard!");
      else showMsg("error", data.error || "Sync thất bại");
    } catch (err: any) { showMsg("error", "Không thể kết nối Dashboard: " + err.message); }
    finally { setSaving(false); }
  };

  /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  /* RENDER                                                          */
  /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  return (
    <div style={S.container}>
      <header style={S.header}>
        <h1 style={S.title}>🖼️ Album Ảnh Seeding</h1>
        <p style={S.subtitle}>Tạo album, quản lý ảnh, và sinh batch ảnh seeding tự động với Canvas.</p>
      </header>

      {errorMsg && <div style={S.errorAlert}>⚠ {errorMsg}</div>}
      {successMsg && <div style={S.successAlert}>✓ {successMsg}</div>}

      <style>{`
        .album-photo-card { position: relative; }
        .album-photo-card:hover .album-photo-delete { opacity: 1 !important; }
      `}</style>

      <div style={S.tabBar}>
        {([["create_album", "➕ Tạo Album"], ["manage_albums", `📋 Albums (${albums.length})`]] as [Tab, string][]).map(([key, label]) => (
          <button key={key} onClick={() => { setTab(key); setErrorMsg(""); setSuccessMsg(""); }}
            style={{ ...S.tabButton, borderBottom: tab === key ? "2px solid #7c3aed" : "2px solid transparent", color: tab === key ? "#fff" : "#6b7280" }}>
            {label}
          </button>
        ))}
      </div>

      {/* ═══ TAB: CREATE ALBUM ═══ */}
      {tab === "create_album" && (
        <div style={S.panel}>
          <h2 style={S.panelTitle}>➕ Tạo Album mới</h2>
          <div style={S.formGrid}>
            <div style={S.formGroup}>
              <label style={S.label}>Tên Album <span style={{ color: "#ef4444" }}>*</span></label>
              <input type="text" value={newAlbumName} onChange={(e) => setNewAlbumName(e.target.value)} placeholder="VD: Review Hà Nội, Food Tour Đà Nẵng..." style={S.input} />
            </div>
            <div style={S.formRow}>
              <div style={{ ...S.formGroup, flex: 1 }}>
                <label style={S.label}>Chủ đề / Khu vực</label>
                <select value={newAlbumTopic} onChange={(e) => setNewAlbumTopic(e.target.value)} style={S.select}>
                  {TOPICS.map((t) => <option key={t} value={t} style={S.option}>{t}</option>)}
                </select>
              </div>
              <div style={{ ...S.formGroup, flex: 1 }}>
                <label style={S.label}>Creator</label>
                <select value={newAlbumCreator} onChange={(e) => setNewAlbumCreator(e.target.value)} style={S.select}>
                  {CREATORS.map((c) => <option key={c.id} value={c.id} style={S.option}>{c.name}</option>)}
                </select>
              </div>
            </div>
            <button onClick={handleCreateAlbum} style={S.primaryBtn}>✨ Tạo Album</button>
          </div>
        </div>
      )}

      {/* ═══ TAB: MANAGE ALBUMS ═══ */}
      {tab === "manage_albums" && (
        <div style={S.panel}>
          <h2 style={S.panelTitle}>📋 Danh sách Album ({albums.length})</h2>
          {albums.length === 0 ? (
            <div style={S.emptyState}><p>Chưa có album nào. Hãy tạo album mới!</p></div>
          ) : (
            <div style={S.albumGrid}>
              {albums.map((album) => (
                <div key={album.id} onClick={() => { setSelectedAlbum(album); setTab("album_detail"); }} style={S.albumCard}>
                  <div style={S.albumCardCover}>
                    {album.photos[0]?.path && album.photos[0].path !== "pending_upload" ? (
                      <img src={toDisplayUrl(album.photos[0].path)} alt="" style={S.albumCardImg} />
                    ) : <div style={{ fontSize: 32, opacity: 0.5 }}>🖼️</div>}
                    <div style={S.albumCardBadge}>{album.photos.length} ảnh</div>
                  </div>
                  <div style={S.albumCardBody}>
                    <div style={S.albumCardName}>{album.albumName}</div>
                    <div style={S.albumCardMeta}>{album.topic} • {album.creator}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═══ TAB: ALBUM DETAIL ═══ */}
      {tab === "album_detail" && selectedAlbum && (
        <div style={S.panel}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <div>
              <button onClick={() => setTab("manage_albums")} style={S.backBtn}>← Quay lại</button>
              <h2 style={{ ...S.panelTitle, marginTop: 8 }}>{selectedAlbum.albumName}</h2>
              <p style={{ fontSize: 12, color: "#6b7280", marginTop: 4 }}>{selectedAlbum.topic} • {selectedAlbum.creator}</p>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => { setTab("seeding"); setSeedLocationTag(selectedAlbum.topic); }} style={S.seedBtn}>✨ Tạo Seeding</button>
              <button onClick={() => handleSyncToDashboard(selectedAlbum)} disabled={saving} style={S.syncBtn}>{saving ? "..." : "🔄 Sync Dashboard"}</button>
              <button onClick={() => handleDeleteAlbum(selectedAlbum.id)} style={S.deleteBtn}>🗑️</button>
            </div>
          </div>

          <div style={S.addPhotoBox}>
            <h3 style={{ fontSize: 13, fontWeight: 600, color: "#fff", marginBottom: 12 }}>Thêm ảnh mới</h3>
            <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
              <div style={{ flex: 1 }}>
                <label style={S.label}>Tên ảnh (Title)</label>
                <input value={photoTitle} onChange={(e) => setPhotoTitle(e.target.value)} placeholder="VD: Bãi biển sunset" style={S.input} />
              </div>
              <div style={{ flex: 1 }}>
                <label style={S.label}>URL ảnh (tùy chọn)</label>
                <input value={photoPath} onChange={(e) => setPhotoPath(e.target.value)} placeholder="https://..." style={S.input} />
              </div>
              <button onClick={handleAddPhoto} style={S.primaryBtn}>➕ Thêm URL</button>
              <button onClick={handleUploadPhotos} style={{ ...S.seedBtn, fontSize: 13, padding: "10px 18px" }}>📁 Upload từ máy</button>
            </div>
            <p style={{ fontSize: 11, color: "#6b7280", marginTop: 8 }}>
              💡 Upload ảnh từ máy để tránh lỗi CORS. Ảnh sẽ được lưu vào thư mục ~/.dulichapp/albums/
            </p>
          </div>

          <h3 style={{ fontSize: 13, fontWeight: 600, color: "#fff", margin: "20px 0 12px" }}>
            Ảnh trong album ({selectedAlbum.photos.length})
          </h3>
          {selectedAlbum.photos.length === 0 ? (
            <div style={S.emptyState}>Chưa có ảnh nào.</div>
          ) : (
            <div style={S.photoGrid}>
              {selectedAlbum.photos.map((photo) => (
                <div key={photo.id} style={S.photoCard} className="album-photo-card">
                  <div style={S.photoCardImg}>
                    {photo.path && photo.path !== "pending_upload" ? (
                      <img src={toDisplayUrl(photo.path)} alt={photo.title} style={S.photoCardImgTag} />
                    ) : <span style={{ color: "#6b7280", fontSize: 20 }}>🖼️</span>}
                  </div>
                  <div style={S.photoCardBody}>
                    <span style={S.photoCardTitle}>{photo.title}</span>
                    {photo.source && (
                      <span style={{ ...S.photoCardSource, color: photo.source === "seeding" ? "#f472b6" : photo.source === "local" ? "#34d399" : "#60a5fa", backgroundColor: photo.source === "seeding" ? "rgba(244,114,182,0.15)" : photo.source === "local" ? "rgba(52,211,153,0.15)" : "rgba(96,165,250,0.15)" }}>
                        {photo.source}
                      </span>
                    )}
                  </div>
                  <button onClick={() => handleRemovePhoto(photo.id)} style={S.photoCardDelete} className="album-photo-delete">✕</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═══ TAB: SEEDING ═══ */}
      {tab === "seeding" && selectedAlbum && (
        <div style={S.panel}>
          <button onClick={() => { setTab("album_detail"); setSeedPreviews([]); }} style={S.backBtn}>← Quay lại album</button>
          <h2 style={{ ...S.panelTitle, marginTop: 8 }}>✨ Tạo Batch Seeding — {getValidPhotos().length} ảnh khả dụng</h2>

          {getValidPhotos().length === 0 && (
            <div style={{ ...S.errorAlert, marginTop: 16 }}>
              ⚠ Album chưa có ảnh URL/data. Hãy thêm ảnh vào album trước khi tạo seeding!
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: 20, marginTop: 16 }}>
            {/* LEFT: Options */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

              {/* ── HOOK IMAGE OPTIONS ── */}
              <div style={{ ...S.optionBox, border: "1px solid rgba(236,72,153,0.3)" }}>
                <label style={{ ...S.label, color: "#f472b6", fontSize: 13, fontWeight: 700 }}>📸 Ảnh 1 — Hook (Ảnh bìa)</label>

                <div style={{ marginTop: 12 }}>
                  <label style={S.label}>Hook chính (chữ lớn)</label>
                  <input value={seedHookMain} onChange={(e) => setSeedHookMain(e.target.value)} placeholder="VD: 99%, 10 điều, Checklist..."
                    style={{ ...S.input, fontSize: 16, fontWeight: 700 }} />
                </div>
                <div style={{ marginTop: 8 }}>
                  <label style={S.label}>Hook phụ (dưới hook chính)</label>
                  <input value={seedHookSub} onChange={(e) => setSeedHookSub(e.target.value)} placeholder="VD: khách du lịch, bạn chưa biết..."
                    style={S.input} />
                </div>
                <div style={{ marginTop: 8 }}>
                  <label style={S.label}>Subtitle (mô tả nhỏ)</label>
                  <input value={seedSubtitle} onChange={(e) => setSeedSubtitle(e.target.value)} placeholder="VD: chưa biết những điều này..."
                    style={S.input} />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 12 }}>
                  <div>
                    <label style={S.label}>📍 Location</label>
                    <input value={seedLocationTag} onChange={(e) => setSeedLocationTag(e.target.value)} placeholder="Dalat"
                      style={S.input} />
                  </div>
                  <div>
                    <label style={S.label}>📅 Date</label>
                    <input value={seedDateTag} onChange={(e) => setSeedDateTag(e.target.value)} placeholder="Tháng 6"
                      style={S.input} />
                  </div>
                  <div>
                    <label style={S.label}>👤 Handle</label>
                    <input value={seedHandleTag} onChange={(e) => setSeedHandleTag(e.target.value)} placeholder="@username"
                      style={S.input} />
                  </div>
                </div>
              </div>

              {/* ── CONTENT IMAGE OPTIONS ── */}
              <div style={{ ...S.optionBox, border: "1px solid rgba(251,191,36,0.3)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <label style={{ ...S.label, color: "#fbbf24", fontSize: 13, fontWeight: 700 }}>📝 Ảnh 2+ — Nội dung (White card)</label>
                  <button onClick={addContentItem} style={{ fontSize: 11, color: "#7c3aed", background: "rgba(124,58,237,0.1)", border: "1px solid rgba(124,58,237,0.3)", borderRadius: 6, padding: "4px 10px", cursor: "pointer" }}>
                    + Thêm ảnh
                  </button>
                </div>

                {seedContentItems.map((item, idx) => (
                  <div key={idx} style={{ marginTop: 12, padding: 12, backgroundColor: "rgba(255,255,255,0.02)", borderRadius: 8, border: "1px solid rgba(255,255,255,0.06)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                      <span style={{ fontSize: 11, color: "#9ca3af" }}>Ảnh {idx + 2}</span>
                      <div style={{ display: "flex", gap: 6 }}>
                        <button onClick={() => updateContentItem(idx, "mode", item.mode === "paragraph" ? "list" : "paragraph")}
                          style={{ fontSize: 10, color: "#60a5fa", background: "rgba(96,165,250,0.1)", border: "1px solid rgba(96,165,250,0.3)", borderRadius: 4, padding: "2px 8px", cursor: "pointer" }}>
                          {item.mode === "paragraph" ? "📝 Paragraph" : "📋 List"}
                        </button>
                        {seedContentItems.length > 1 && (
                          <button onClick={() => removeContentItem(idx)} style={{ fontSize: 10, color: "#ef4444", background: "none", border: "none", cursor: "pointer" }}>✕</button>
                        )}
                      </div>
                    </div>
                    <input value={item.title} onChange={(e) => updateContentItem(idx, "title", e.target.value)}
                      placeholder="Tiêu đề (VD: BẬT GG MAP CHẾ ĐỘ Ô TÔ)" style={{ ...S.input, fontSize: 12, marginBottom: 6 }} />
                    <textarea value={item.content} onChange={(e) => updateContentItem(idx, "content", e.target.value)}
                      placeholder={item.mode === "list" ? "Mỗi dòng 1 mục:\nNguyễn Văn Trỗi\nTrường Công Định\n..." : "Nội dung paragraph..."}
                      rows={4} style={{ ...S.input, resize: "vertical", fontSize: 12 }} />
                  </div>
                ))}
              </div>

              {/* ── STYLE OPTIONS ── */}
              <div style={S.optionBox}>
                <label style={S.label}>Style Ảnh Hook</label>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginTop: 8 }}>
                  {SEEDING_STYLES.map((s) => (
                    <button key={s.id} onClick={() => setSeedStyle(s.id)}
                      style={{ ...S.optionBtn, borderColor: seedStyle === s.id ? "#7c3aed" : "rgba(255,255,255,0.1)", color: seedStyle === s.id ? "#fff" : "#9ca3af" }}>
                      <span style={{ fontSize: 18 }}>{s.emoji}</span><span>{s.name}</span>
                    </button>
                  ))}
                </div>
                <label style={{ ...S.label, marginTop: 12 }}>Màu chữ hook</label>
                <div style={{ display: "flex", gap: 8 }}>
                  {TEXT_COLORS.map((c) => (
                    <button key={c} onClick={() => setSeedTextColor(c)}
                      style={{ width: 28, height: 28, borderRadius: "50%", border: seedTextColor === c ? "2px solid #fff" : "2px solid transparent", backgroundColor: c, cursor: "pointer", transform: seedTextColor === c ? "scale(1.2)" : "scale(1)", transition: "transform 0.15s" }} />
                  ))}
                </div>
                <label style={{ ...S.label, marginTop: 12 }}>Format</label>
                <select value={seedFormat} onChange={(e) => setSeedFormat(e.target.value)} style={S.select}>
                  {Object.entries(FORMATS).map(([k, v]) => <option key={k} value={k} style={S.option}>{v}</option>)}
                </select>
              </div>

              <button onClick={handleGenerateBatch} disabled={!seedHookMain.trim() || seedGenerating || getValidPhotos().length === 0}
                style={{ ...S.seedBtn, opacity: (!seedHookMain.trim() || seedGenerating || getValidPhotos().length === 0) ? 0.5 : 1 }}>
                {seedGenerating ? "⏳ Đang tạo..." : `✨ Tạo ${1 + seedContentItems.filter(i => i.title.trim()).length} ảnh Seeding`}
              </button>
            </div>

            {/* RIGHT: Preview */}
            <div style={S.optionBox}>
              <label style={S.label}>Preview ({seedPreviews.length} ảnh)</label>
              <div style={{ ...S.previewBox, flexDirection: "column", gap: 16, maxHeight: 700, overflowY: "auto", alignItems: "stretch", justifyContent: "flex-start" }}>
                {seedPreviews.length > 0 ? (
                  <>
                    {seedPreviews.map((preview, i) => (
                      <div key={i} style={{ textAlign: "center", position: "relative" }}>
                        <div style={{ fontSize: 11, color: i === 0 ? "#f472b6" : "#fbbf24", fontWeight: 700, marginBottom: 6 }}>
                          {i === 0 ? "📸 Ảnh HOOK (Bìa)" : `📝 Ảnh CONTENT ${i + 1}`}
                        </div>
                        <img src={preview} alt={`Seeding ${i}`} style={{ maxWidth: "100%", maxHeight: 350, borderRadius: 8, boxShadow: "0 8px 32px rgba(0,0,0,0.5)" }} />
                        <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 8 }}>
                          <button onClick={() => handleDownload(preview, `seeding_${i === 0 ? "hook" : `content${i}`}_${seedTopic}_${Date.now()}.png`)}
                            style={{ fontSize: 11, color: "#60a5fa", background: "rgba(96,165,250,0.1)", border: "1px solid rgba(96,165,250,0.3)", borderRadius: 6, padding: "4px 10px", cursor: "pointer" }}>
                            📥 Tải xuống
                          </button>
                        </div>
                      </div>
                    ))}
                    <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 12, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 12 }}>
                      <button onClick={handleSaveAllToAlbum} style={S.primaryBtn}>💾 Lưu tất cả vào Album</button>
                      <button onClick={() => {
                        seedPreviews.forEach((p, i) => handleDownload(p, `seeding_${i === 0 ? "hook" : `content${i}`}_${seedTopic}_${Date.now()}.png`));
                      }} style={S.secondaryBtn}>📥 Tải tất cả</button>
                    </div>
                  </>
                ) : (
                  <div style={{ textAlign: "center", padding: 40, color: "#6b7280" }}>
                    <div style={{ fontSize: 40, marginBottom: 12 }}>✨</div>
                    <p style={{ fontSize: 13 }}>Điền thông tin bên trái và bấm &quot;Tạo ảnh Seeding&quot;</p>
                    <p style={{ fontSize: 11, marginTop: 8, color: "#9ca3af" }}>Ảnh đầu = Hook (text lớn trên photo)<br />Ảnh sau = Content (white card trên photo)</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Styles ──────────────────────────────────────────────────────── */
const S: Record<string, React.CSSProperties> = {
  container: { padding: 24, color: "#f3f4f6", fontFamily: "Inter, sans-serif", height: "100%", overflowY: "auto" },
  header: { marginBottom: 24 },
  title: { fontSize: 26, fontWeight: 700, color: "#ffffff", margin: 0 },
  subtitle: { fontSize: 14, color: "#9ca3af", marginTop: 6, lineHeight: 1.5 },
  tabBar: { display: "flex", gap: 0, marginBottom: 20, borderBottom: "1px solid rgba(255,255,255,0.06)" },
  tabButton: { background: "none", border: "none", padding: "12px 24px", fontSize: 14, fontWeight: 600, cursor: "pointer", transition: "all 0.2s" },
  panel: { backgroundColor: "rgba(17,12,46,0.4)", backdropFilter: "blur(16px)", borderRadius: 16, padding: 24, border: "1px solid rgba(255,255,255,0.06)", boxShadow: "0 8px 32px rgba(0,0,0,0.3)" },
  panelTitle: { fontSize: 17, fontWeight: 600, color: "#fff", margin: 0 },
  formGrid: { display: "flex", flexDirection: "column", gap: 16, marginTop: 18 },
  formRow: { display: "flex", gap: 16 },
  formGroup: { display: "flex", flexDirection: "column", gap: 6 },
  label: { fontSize: 12, fontWeight: 500, color: "#d1d5db" },
  input: { backgroundColor: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, color: "#fff", fontSize: 13, padding: "10px 14px", outline: "none", width: "100%" },
  select: { backgroundColor: "#161233", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 8, color: "#fff", fontSize: 13, padding: "10px 14px", outline: "none" },
  option: { backgroundColor: "#161233", color: "#fff" },
  primaryBtn: { backgroundColor: "#7c3aed", color: "#fff", border: "none", borderRadius: 10, fontSize: 14, fontWeight: 600, padding: "12px 24px", cursor: "pointer", boxShadow: "0 4px 16px rgba(124,58,237,0.3)" },
  secondaryBtn: { backgroundColor: "rgba(255,255,255,0.06)", color: "#fff", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 10, fontSize: 13, fontWeight: 600, padding: "10px 20px", cursor: "pointer" },
  syncBtn: { backgroundColor: "rgba(16,185,129,0.15)", color: "#10b981", border: "1px solid rgba(16,185,129,0.3)", borderRadius: 8, fontSize: 12, fontWeight: 600, padding: "8px 16px", cursor: "pointer" },
  deleteBtn: { background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, fontSize: 14, padding: "8px 12px", cursor: "pointer" },
  seedBtn: { background: "linear-gradient(135deg, #ec4899, #f97316)", color: "#fff", border: "none", borderRadius: 10, fontSize: 14, fontWeight: 600, padding: "12px 24px", cursor: "pointer", boxShadow: "0 4px 16px rgba(236,72,153,0.3)" },
  backBtn: { background: "none", border: "none", color: "#9ca3af", fontSize: 13, cursor: "pointer", padding: 0 },
  addPhotoBox: { backgroundColor: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 12, padding: 16 },
  emptyState: { textAlign: "center", padding: 40, color: "#6b7280", border: "1px dashed rgba(255,255,255,0.08)", borderRadius: 12 },
  errorAlert: { backgroundColor: "rgba(239,68,68,0.15)", border: "1px solid #ef4444", borderRadius: 8, color: "#fca5a5", fontSize: 13, padding: 12, marginBottom: 18 },
  successAlert: { backgroundColor: "rgba(16,185,129,0.15)", border: "1px solid #10b981", borderRadius: 8, color: "#6ee7b7", fontSize: 13, padding: 12, marginBottom: 18 },
  albumGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 16, marginTop: 16 },
  albumCard: { backgroundColor: "rgba(255,255,255,0.02)", borderRadius: 12, border: "1px solid rgba(255,255,255,0.06)", overflow: "hidden", cursor: "pointer", transition: "transform 0.2s, border-color 0.2s" },
  albumCardCover: { width: "100%", height: 160, backgroundColor: "rgba(0,0,0,0.3)", display: "flex", alignItems: "center", justifyContent: "center", position: "relative" as const },
  albumCardImg: { width: "100%", height: "100%", objectFit: "cover" as const },
  albumCardBadge: { position: "absolute" as const, top: 8, right: 8, backgroundColor: "rgba(0,0,0,0.6)", color: "#fff", fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 10 },
  albumCardBody: { padding: 12 },
  albumCardName: { fontSize: 13, fontWeight: 600, color: "#fff", marginBottom: 4 },
  albumCardMeta: { fontSize: 11, color: "#6b7280" },
  photoGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 },
  photoCard: { backgroundColor: "rgba(255,255,255,0.02)", borderRadius: 10, border: "1px solid rgba(255,255,255,0.06)", overflow: "hidden", position: "relative" as const },
  photoCardImg: { width: "100%", height: 140, backgroundColor: "rgba(0,0,0,0.2)", display: "flex", alignItems: "center", justifyContent: "center" },
  photoCardImgTag: { width: "100%", height: "100%", objectFit: "cover" as const },
  photoCardBody: { padding: 8, display: "flex", flexDirection: "column" as const, gap: 4 },
  photoCardTitle: { fontSize: 11, fontWeight: 600, color: "#fff", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const },
  photoCardSource: { fontSize: 9, fontWeight: 700, padding: "1px 6px", borderRadius: 4, alignSelf: "flex-start", textTransform: "uppercase" as const },
  photoCardDelete: { position: "absolute" as const, top: 4, right: 4, background: "rgba(239,68,68,0.8)", border: "none", color: "#fff", width: 20, height: 20, borderRadius: "50%", cursor: "pointer", fontSize: 10, display: "flex", alignItems: "center", justifyContent: "center", opacity: 0 },
  optionBox: { backgroundColor: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 12, padding: 16 },
  optionBtn: { display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 4, padding: "10px 8px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.1)", background: "transparent", cursor: "pointer", fontSize: 11, transition: "all 0.15s" },
  tagBtn: { padding: "6px 14px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.1)", background: "transparent", cursor: "pointer", fontSize: 12, fontWeight: 500, transition: "all 0.15s" },
  seedingItemBtn: { width: "100%", textAlign: "left" as const, padding: "10px 12px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.1)", background: "transparent", cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 8, color: "#d1d5db", transition: "all 0.15s" },
  previewBox: { backgroundColor: "#0a0a0f", borderRadius: 12, border: "1px solid rgba(255,255,255,0.05)", padding: 20, minHeight: 400, display: "flex", alignItems: "center", justifyContent: "center" },
};
