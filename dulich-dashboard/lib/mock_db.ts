import fs from "fs";
import path from "path";

const dbPath = path.join(process.cwd(), "lib", "mock_db.json");

export interface VideoItem {
  id: string;
  name: string;
  creator: string;
  status: "Đang render" | "Chờ duyệt" | "Đã duyệt" | "Đã đăng";
  date: string;
  topic: string;
  templateId: string;
  seeds: string[];
  script: {
    hook: string;
    body: string;
    cta: string;
  };
  captions: {
    hooks: string[];
    caption_short: string;
    caption_long: string;
    hashtags: string[];
  };
  images: {
    description: string;
    prompts: string[];
  };
}

const defaultVideos: VideoItem[] = [
  {
    id: "1",
    name: "Top 5 địa điểm Đà Nẵng",
    creator: "Creator 1",
    status: "Đã duyệt",
    date: "2026-06-09",
    topic: "Đà Nẵng",
    templateId: "default",
    seeds: ["Nhà hàng Bé Mặn"],
    script: {
      hook: "Bạn có biết Đà Nẵng đang là điểm đến hot nhất năm 2025 không?",
      body: "Hôm nay mình đưa các bạn khám phá toàn bộ Đà Nẵng trong vòng 60 giây!\n\nĐầu tiên là cảnh đẹp không thể bỏ qua — bầu trời xanh ngắt, biển cả mênh mông, con người thân thiện.\n\nGhé qua Nhà hàng Bé Mặn thưởng thức đặc sản địa phương ngay nhé!\n\nMình đã ở đây 3 ngày 2 đêm với chi phí chỉ 2 triệu một người — cực kỳ hợp lý cho một chuyến đi đáng nhớ!",
      cta: "Nhấn thích nếu bạn muốn mình làm bộ guide Đà Nẵng chi tiết hơn! Follow để không bỏ lỡ video tiếp theo nhé!"
    },
    captions: {
      hooks: [
        "Đà Nẵng đẹp đến mức này?!",
        "2 triệu cho 3 ngày 2 đêm tại Đà Nẵng — có thật không?",
        "Ai chưa đến Đà Nẵng thì đang bỏ lỡ điều này..."
      ],
      caption_short: "Đà Nẵng — điểm đến hot năm 2025! Chi phí chỉ từ 2 triệu một người. #dulich #danang",
      caption_long: "Đà Nẵng — thiên đường du lịch đang đỉnh nhất năm 2025!\n\nCảnh đẹp không cần bộ lọc\nẨm thực đậm đà bản sắc\nChi phí cực hợp lý cho mọi ngân sách\nNhiều lựa chọn lưu trú từ bình dân đến cao cấp\n\nMình đã ghé: Nhà hàng Bé Mặn — tất cả đều cực đỉnh!\n\nLưu ngay để lên lịch chuyến đi nhé!\n\n#dulichvietnam #danang #travel #vietnam #review",
      hashtags: ["#dulichvietnam", "#travel", "#vietnam", "#reviewdulich", "#danang"]
    },
    images: {
      description: "Bộ ảnh Đà Nẵng — 9:16 format, tông màu warm golden hour, phong cách cinematic travel photography.",
      prompts: [
        "Golden hour panoramic view of Đà Nẵng coastline, warm orange tones, wide angle shot, cinematic travel photography, 9:16 ratio",
        "Vibrant local street food market in Đà Nẵng, close-up bokeh, colorful dishes, warm lighting, appetizing food photography",
        "Sunset silhouette over Đà Nẵng horizon, dramatic purple-orange sky, long exposure",
        "Smiling local people in Đà Nẵng village, candid portrait, Sony A7 quality",
        "Aerial drone view of Đà Nẵng beach resort, turquoise water, white sand"
      ]
    }
  },
  {
    id: "2",
    name: "Food tour Hà Nội",
    creator: "Creator 2",
    status: "Chờ duyệt",
    date: "2026-06-08",
    topic: "Hà Nội",
    templateId: "default",
    seeds: [],
    script: {
      hook: "Bạn đã nghe ẩm thực phố cổ Hà Nội chưa?",
      body: "Hôm nay mình sẽ dắt bạn đi ăn sập 5 món ngon nhất Hà Nội chỉ với 100k.\n\nĐầu tiên là phở gia truyền thơm nức mũi, sau đó là bún chả nướng than hoa thơm phức.\n\nKhông thể thiếu cốc cafe trứng béo ngậy để kết thúc hành trình ẩm thực thú vị này!",
      cta: "Bình luận món ăn Hà Nội bạn thích nhất bên dưới nhé! Đăng ký kênh ngay!"
    },
    captions: {
      hooks: ["Ăn sập Hà Nội chỉ với 100k!", "Món ngon phố cổ bạn phải thử", "Hà Nội foodtour 1 ngày"],
      caption_short: "Cầm 100k ăn sập phố cổ Hà Nội! Bạn tin được không? #hanoifood #foodtour",
      caption_long: "Ăn sập Hà Nội chỉ trong 1 ngày với danh sách các món ngon bổ rẻ nhất!\n\nXem video và lưu lại địa chỉ nhé các bạn.\n\n#hanoi #foodtour #streetfood #vietnam",
      hashtags: ["#hanoi", "#foodtour", "#streetfood", "#vietnam", "#amthuc"]
    },
    images: {
      description: "Bộ ảnh Food tour Hà Nội — 9:16 format.",
      prompts: [
        "Hot steaming bowl of traditional Hanoi Pho, beef slices, green onions, close-up",
        "Bún chả Hanoi on charcoal grill, smoke rising, appetizing food photography",
        "Egg coffee cup with beautiful latte art in a cozy rustic Hanoi cafe"
      ]
    }
  },
  {
    id: "3",
    name: "Khách sạn view biển Phú Quốc",
    creator: "Creator 3",
    status: "Đang render",
    date: "2026-06-07",
    topic: "Phú Quốc",
    templateId: "default",
    seeds: [],
    script: {
      hook: "Review khách sạn sát biển cực chill tại Phú Quốc!",
      body: "Mở cửa phòng ra là thấy ngay bãi cát trắng mịn và biển xanh ngọc bích.\n\nPhòng ốc rộng rãi, dịch vụ 5 sao, đặc biệt bể bơi vô cực ngắm hoàng hôn siêu đẹp.",
      cta: "Tag ngay cạ cứng vào đây để lên kèo đi Phú Quốc thôi!"
    },
    captions: {
      hooks: ["Khách sạn sát biển đỉnh nhất Phú Quốc", "Ngủ dậy thấy ngay biển xanh Phú Quốc", "Resort vô cực siêu chill"],
      caption_short: "Sáng thức dậy ở một nơi xa view biển Phú Quốc cực xịn! #phuquoc #resort",
      caption_long: "Một trải nghiệm nghỉ dưỡng tuyệt vời tại Phú Quốc.\n\nGiá cực tốt mùa này, dịch vụ chuẩn chỉnh.\n\n#phuquoc #resort #travel #vietnam",
      hashtags: ["#phuquoc", "#resort", "#travel", "#vietnam", "#holiday"]
    },
    images: {
      description: "Bộ ảnh Resort Phú Quốc.",
      prompts: [
        "Luxury hotel room balcony overlooking white sand beach and turquoise ocean in Phu Quoc",
        "Infinite pool in Phu Quoc resort at sunset, beautiful reflections, palm trees"
      ]
    }
  }
];

export function getVideos(): VideoItem[] {
  try {
    const dir = path.dirname(dbPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    if (!fs.existsSync(dbPath)) {
      fs.writeFileSync(dbPath, JSON.stringify(defaultVideos, null, 2), "utf-8");
      return defaultVideos;
    }
    const data = fs.readFileSync(dbPath, "utf-8");
    return JSON.parse(data);
  } catch (e) {
    return defaultVideos;
  }
}

export function saveVideos(videos: VideoItem[]) {
  try {
    const dir = path.dirname(dbPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(dbPath, JSON.stringify(videos, null, 2), "utf-8");
  } catch (e) {
    console.error("Save db error", e);
  }
}

export function addVideo(video: Omit<VideoItem, "id" | "date" | "status">): VideoItem {
  const videos = getVideos();
  const newVideo: VideoItem = {
    ...video,
    id: Date.now().toString(),
    date: new Date().toISOString().split("T")[0],
    status: "Chờ duyệt",
  };
  videos.unshift(newVideo);
  saveVideos(videos);
  return newVideo;
}

export function updateVideoStatus(id: string, status: VideoItem["status"]): boolean {
  const videos = getVideos();
  const index = videos.findIndex((v) => v.id === id);
  if (index !== -1) {
    videos[index].status = status;
    saveVideos(videos);
    return true;
  }
  return false;
}
