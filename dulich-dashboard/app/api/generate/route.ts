import { NextResponse } from "next/server";

export const runtime = "nodejs";

// ─── Fake data generator (no API key needed for testing) ───────────────────
function generateFakeData(
  topic: string,
  templateId: string,
  seeds: string[],
) {
  const seedMentions =
    seeds.length > 0
      ? `Ghé qua ${seeds[0]} thưởng thức đặc sản địa phương ngay nhé!`
      : "Đừng quên thử ẩm thực đường phố cực kỳ đặc sắc tại đây!";

  const script = {
    hook: `Bạn có biết ${topic} đang là điểm đến hot nhất năm 2025 không?`,
    body: `Hôm nay mình đưa các bạn khám phá toàn bộ ${topic} trong vòng 60 giây!\n\nĐầu tiên là cảnh đẹp không thể bỏ qua — bầu trời xanh ngắt, biển cả mênh mông, con người thân thiện.\n\n${seedMentions}\n\nMình đã ở đây 3 ngày 2 đêm với chi phí chỉ 2 triệu một người — cực kỳ hợp lý cho một chuyến đi đáng nhớ!`,
    cta: `Nhấn thích nếu bạn muốn mình làm bộ guide ${topic} chi tiết hơn! Follow để không bỏ lỡ video tiếp theo nhé!`,
  };

  const hooks = [
    `${topic} đẹp đến mức này?!`,
    `2 triệu cho 3 ngày 2 đêm tại ${topic} — có thật không?`,
    `Ai chưa đến ${topic} thì đang bỏ lỡ điều này...`,
  ];

  const captions = {
    hooks,
    caption_short: `${topic} — điểm đến hot năm 2025! Chi phí chỉ từ 2 triệu một người. #dulich #${topic.replace(/\s+/g, "").toLowerCase()}`,
    caption_long: `${topic} — thiên đường du lịch đang đỉnh nhất năm 2025!\n\nCảnh đẹp không cần bộ lọc\nẨm thực đậm đà bản sắc\nChi phí cực hợp lý cho mọi ngân sách\nNhiều lựa chọn lưu trú từ bình dân đến cao cấp\n\n${seeds.length > 0 ? `Mình đã ghé: ${seeds.join(", ")} — tất cả đều cực đỉnh!\n\n` : ""}Lưu ngay để lên lịch chuyến đi nhé!\n\n#dulichvietnam #${topic.replace(/\s+/g, "").toLowerCase()} #travel #vietnam #review`,
    hashtags: [
      "#dulichvietnam",
      "#travel",
      "#vietnam",
      "#reviewdulich",
      "#khampha",
      `#${topic.replace(/\s+/g, "").toLowerCase()}`,
      "#travelgram",
      "#wanderlust",
      "#backpacker",
      "#dulichnoidia",
      "#reviewtravel",
      "#gocdulich",
      "#xuhuong",
      "#tiktokdulich",
      "#365ngaydulichtravelvietnam",
    ],
  };

  const templateLabel =
    templateId === "wide" ? "16:9" : templateId === "square" ? "1:1" : "9:16";

  const images = {
    description: `Bộ ảnh ${topic} — ${templateLabel} format, tông màu warm golden hour, phong cách cinematic travel photography phù hợp TikTok/Reels.`,
    prompts: [
      `Golden hour panoramic view of ${topic} coastline, warm orange tones, wide angle shot, cinematic travel photography, ${templateLabel} ratio, ultra sharp`,
      `Vibrant local street food market in ${topic}, close-up bokeh, colorful dishes, warm lighting, appetizing food photography, documentary style`,
      `Sunset silhouette over ${topic} horizon, dramatic purple-orange sky, long exposure, moody travel photography, cinematic color grade`,
      `Smiling local people in ${topic} village, candid portrait, natural light, authentic cultural photography, Sony A7 quality`,
      `Aerial drone view of ${topic} beach resort, turquoise water, white sand, luxury travel aesthetic, Google Earth perspective, vibrant saturation`,
    ],
  };

  return { script, captions, images };
}
// ───────────────────────────────────────────────────────────────────────────

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { topic, templateId, seeds, creator } = body;

    if (!topic || typeof topic !== "string" || topic.trim().length === 0) {
      return NextResponse.json(
        { error: "Topic là bắt buộc" },
        { status: 400 },
      );
    }

    // Simulate network delay for realistic UX (1.5 – 2.5s)
    await new Promise((resolve) =>
      setTimeout(resolve, 1500 + Math.random() * 1000),
    );

    const result = generateFakeData(
      topic.trim(),
      templateId || "default",
      Array.isArray(seeds) ? seeds.filter((s: string) => s.trim()) : [],
    );

    return NextResponse.json({
      success: true,
      data: result,
      meta: {
        creator: creator || null,
        templateId: templateId || "default",
        generatedAt: new Date().toISOString(),
        mode: "mock", // flag to indicate fake data
      },
    });
  } catch (error) {
    console.error("Generate error:", error);
    return NextResponse.json(
      {
        error: "Không thể tạo nội dung. Vui lòng thử lại.",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
