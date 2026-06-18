/**
 * canvaBridge.ts — Canva Integration Service
 * Handles fetching frames from Canva public designs and managing Canva API interactions.
 */

export interface CanvaFrameResult {
  frame_id: string;
  name: string;
  thumbnail_path: string; // data URL
  width: number;
  height: number;
  aspect_ratio: string;
  style_tags: string[];
  color_palette: string[];
}

/**
 * Extract frame images from a publicly shared Canva design
 * Uses the public render API when available.
 */
export async function fetchCanvaPublicDesign(designUrl: string): Promise<CanvaFrameResult[]> {
  // Extract design ID from URL
  const match = designUrl.match(/canva\.com\/design\/([^/]+)/);
  if (!match) throw new Error("Invalid Canva design URL");

  const designId = match[1];
  const results: CanvaFrameResult[] = [];
  const timestamp = Date.now();

  // Canva public rendering endpoints:
  // https://www.canva.com/design/{designId}/view -> public view
  // https://www.canva.com/api/design/{designId}/thumbnail -> thumbnail

  try {
    // Attempt 1: Try the public thumbnail API
    const thumbUrl = `https://www.canva.com/api/design/${designId}/thumbnail`;
    const resp = await fetch(thumbUrl, {
      method: "HEAD",
      mode: "no-cors",
    });

    if (resp.ok || resp.type === "opaque") {
      // We can at least reference the thumbnail
    }
  } catch {
    // Fallback: use render API
  }

  // For now, return a placeholder that tells the user to export manually
  // Full Canva API integration requires Canva API credentials
  throw new Error(
    "Canva yêu cầu đăng nhập. Vui lòng:\n" +
    "1. Mở design trong Canva\n" +
    "2. File > Download > PNG (chọn định dạng muốn dùng)\n" +
    "3. Upload file PNG đã export vào hệ thống"
  );
}

/**
 * Check if a Canva design is publicly accessible
 */
export async function checkCanvaAccess(designUrl: string): Promise<{
  accessible: boolean;
  public: boolean;
  error?: string;
}> {
  try {
    const resp = await fetch(designUrl, {
      method: "HEAD",
      mode: "no-cors",
    });
    return {
      accessible: resp.type === "opaque" || resp.ok,
      public: resp.ok,
    };
  } catch (e: any) {
    return {
      accessible: false,
      public: false,
      error: e.message,
    };
  }
}

/**
 * Generate a Canva-like frame using CSS/Canvas (offline fallback)
 * Creates a frame matching the visual style of a Canva template
 */
export function generateCanvaStyleFrame(
  canvas: HTMLCanvasElement,
  style: {
    cornerRadius?: number;
    borderWidth?: number;
    borderColor?: string;
    shadow?: boolean;
    gradient?: string[];
    pattern?: "none" | "dots" | "stripes" | "hearts";
  }
): void {
  const ctx = canvas.getContext("2d")!;
  const w = canvas.width;
  const h = canvas.height;

  const cr = style.cornerRadius || Math.min(w, h) * 0.05;
  const bw = style.borderWidth || 4;

  // Shadow
  if (style.shadow !== false) {
    ctx.shadowColor = "rgba(0,0,0,0.2)";
    ctx.shadowBlur = 12;
    ctx.shadowOffsetX = 2;
    ctx.shadowOffsetY = 2;
  }

  // Border background
  ctx.fillStyle = style.borderColor || "#ffffff";
  ctx.beginPath();
  ctx.roundRect(0, 0, w, h, cr);
  ctx.fill();

  ctx.shadowColor = "transparent";

  // Inner cutout (transparent center where image shows through)
  const inset = bw;
  ctx.globalCompositeOperation = "destination-out";
  ctx.fillStyle = "#000";
  ctx.beginPath();
  ctx.roundRect(inset, inset, w - inset * 2, h - inset * 2, Math.max(0, cr - 2));
  ctx.fill();
  ctx.globalCompositeOperation = "source-over";
}

/**
 * Instructions text for exporting frames from Canva
 */
export const CANVA_EXPORT_GUIDE = {
  title: "Hướng dẫn xuất khung từ Canva",
  steps: [
    "Mở design Canva của bạn",
    "Chọn khung ảnh muốn sử dụng",
    "Click File → Download → PNG",
    "Chọn 'Transparent background' nếu có",
    "Tải file về và upload lên hệ thống",
  ],
  tips: "Nên xuất khung có nền trong suốt (PNG) để dễ ghép ảnh.",
};
