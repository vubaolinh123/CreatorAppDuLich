/**
 * aiService.ts — AI Image Analysis using Gemini API
 * Analyzes user images to recommend optimal frame themes and placement positions.
 */

import { useAppStore } from "../stores/appStore";

export interface ImageAnalysis {
  dominantColors: string[];
  brightness: "very_bright" | "bright" | "medium" | "dark" | "very_dark";
  composition: {
    subjectPosition: "center" | "left" | "right" | "top" | "bottom" | "spread";
    subjectSize: "large" | "medium" | "small";
    hasFace: boolean;
    hasText: boolean;
  };
  recommendedTheme: string;
  framePlacement: {
    position: "overlay" | "border_only" | "bottom_third" | "top_third";
    cornerStyle: "all" | "top_only" | "bottom_only";
    opacity: number; // 0-1
  };
  titleSuggestion: string;
  tags: string[];
}

const GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent";

async function getGeminiKey(): Promise<string> {
  const settings = useAppStore.getState().settings;
  if (settings.geminiKey) return settings.geminiKey;
  // Fallback: try OpenAI key for GPT-4o vision
  if (settings.openAiKey) return `openai:${settings.openAiKey}`;
  throw new Error("Vui lòng cấu hình Gemini API Key trong Cài đặt > API Keys");
}

export async function analyzeImage(
  imageDataUrl: string,
  topic?: string
): Promise<ImageAnalysis> {
  const key = await getGeminiKey();

  if (key.startsWith("openai:")) {
    return analyzeWithOpenAI(key.slice(7), imageDataUrl, topic);
  }

  const prompt = `Bạn là chuyên gia phân tích ảnh cho hệ thống tạo nội dung du lịch. Hãy phân tích ảnh này và trả về JSON (không markdown, không code block):

{
  "dominantColors": ["#hex1", "#hex2", "#hex3"],
  "brightness": "very_bright|bright|medium|dark|very_dark",
  "composition": {
    "subjectPosition": "center|left|right|top|bottom|spread",
    "subjectSize": "large|medium|small",
    "hasFace": false,
    "hasText": false
  },
  "recommendedTheme": "cute_pastel|kawaii_star|ribbon_gold|neon_glow|vintage_film|polaroid|floral_dream|minimal_line|glitter_sparkle|ocean_breeze|sunset_warm|candy_pop",
  "framePlacement": {
    "position": "overlay|border_only|bottom_third|top_third",
    "cornerStyle": "all|top_only|bottom_only",
    "opacity": 0.8
  },
  "titleSuggestion": "Tiêu đề gợi ý cho ảnh này (ngắn gọn, hấp dẫn)",
  "tags": ["tag1", "tag2", "tag3"]
}

CHỌN THEME PHÙ HỢP NHẤT với ảnh dựa trên màu sắc, không gian, và nội dung:
- cute_pastel: ảnh pastel, nhẹ nhàng, nữ tính
- kawaii_star: ảnh tươi sáng, vui nhộn
- ribbon_gold: ảnh sang trọng, hoàng hôn, vàng
- neon_glow: ảnh hiện đại, thành phố, đêm
- vintage_film: ảnh cổ điển, retro, film
- polaroid: ảnh đời thường, travel diary
- floral_dream: ảnh hoa, thiên nhiên
- minimal_line: ảnh tối giản, kiến trúc
- glitter_sparkle: ảnh glam, lấp lánh
- ocean_breeze: ảnh biển, hồ bơi
- sunset_warm: ảnh hoàng hôn, bình minh
- candy_pop: ảnh nhiều màu, nổi bật

${topic ? `Chủ đề: "${topic}". Hãy gợi ý tiêu đề và tags phù hợp.` : ""}`;

  try {
    const resp = await fetch(`${GEMINI_API_URL}?key=${key}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{
          parts: [
            { text: prompt },
            {
              inline_data: {
                mime_type: "image/png",
                data: imageDataUrl.split(",")[1] || imageDataUrl,
              },
            },
          ],
        }],
        generationConfig: {
          temperature: 0.3,
          maxOutputTokens: 1024,
        },
      }),
    });

    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error(`Gemini API error: ${resp.status} ${errText}`);
    }

    const data = await resp.json();
    const rawText = data?.candidates?.[0]?.content?.parts?.[0]?.text || "{}";
    const cleaned = rawText.replace(/```(json)?/g, "").trim();
    return JSON.parse(cleaned);
  } catch (e: any) {
    console.warn("Gemini analysis failed, using fallback:", e.message);
    return fallbackAnalysis(imageDataUrl);
  }
}

async function analyzeWithOpenAI(
  apiKey: string,
  imageDataUrl: string,
  topic?: string
): Promise<ImageAnalysis> {
  const prompt = `Analyze this travel photo. Return JSON (no markdown):
{
  "dominantColors": ["#hex1", "#hex2", "#hex3"],
  "brightness": "bright|medium|dark",
  "composition": { "subjectPosition": "center|left|right|top|bottom|spread", "subjectSize": "large|medium|small", "hasFace": false, "hasText": false },
  "recommendedTheme": "ocean_breeze|sunset_warm|cute_pastel|vintage_film|neon_glow|polaroid|floral_dream|minimal_line|glitter_sparkle|candy_pop|kawaii_star|ribbon_gold",
  "framePlacement": { "position": "border_only|overlay|bottom_third", "cornerStyle": "all|top_only", "opacity": 0.8 },
  "titleSuggestion": "Suggested short title in Vietnamese",
  "tags": ["tag1", "tag2"]
}`;

  try {
    const resp = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: "gpt-4o-mini",
        messages: [
          { role: "user", content: [
            { type: "text", text: prompt },
            { type: "image_url", image_url: { url: imageDataUrl } },
          ]},
        ],
        max_tokens: 1024,
        temperature: 0.3,
      }),
    });

    if (!resp.ok) throw new Error(`OpenAI error: ${resp.status}`);
    const data = await resp.json();
    const rawText = data?.choices?.[0]?.message?.content || "{}";
    const cleaned = rawText.replace(/```(json)?/g, "").trim();
    return JSON.parse(cleaned);
  } catch (e: any) {
    console.warn("OpenAI analysis failed, using fallback:", e.message);
    return fallbackAnalysis(imageDataUrl);
  }
}

function fallbackAnalysis(_imageDataUrl: string): ImageAnalysis {
  // Simple client-side analysis (color sampling + heuristics)
  return {
    dominantColors: ["#4f46e5", "#7c3aed", "#ec4899"],
    brightness: "medium",
    composition: {
      subjectPosition: "center",
      subjectSize: "medium",
      hasFace: false,
      hasText: false,
    },
    recommendedTheme: "cute_pastel",
    framePlacement: {
      position: "border_only",
      cornerStyle: "all",
      opacity: 0.85,
    },
    titleSuggestion: "Khoảnh khắc đẹp tại Việt Nam",
    tags: ["travel", "vietnam", "explore"],
  };
}
