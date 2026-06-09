/**
 * Claude Service — Direct Anthropic API integration for content generation.
 * Used by the dashboard to generate scripts, captions, and image prompts.
 */

import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

export interface ScriptResult {
  hook: string;
  body: string;
  cta: string;
}

export interface CaptionResult {
  hooks: string[];
  caption_short: string;
  caption_long: string;
  hashtags: string[];
}

export interface ImagePromptResult {
  description: string;
  prompts: string[];
}

export interface GenerateResult {
  script: ScriptResult;
  captions: CaptionResult;
  images: ImagePromptResult;
}

const SCRIPT_SYSTEM_PROMPT = `You are a Vietnamese travel video scriptwriter.
Write a 60-second script for the topic: {topic}.
Structure: Hook (0-5s) -> Destination showcase (5-40s) -> Call to action (40-60s).
Seeding mentions: {seeds} -- integrate naturally, not as ads.
Tone: Energetic, authentic, cinematic.
Language: Vietnamese with travel-specific vocabulary.
Output JSON only: {{"hook": "...", "body": "...", "cta": "..."}}`;

const CAPTION_SYSTEM_PROMPT = `Given a script and video description, generate:
(1) 3 hook variants (first 3 words that stop scroll),
(2) 2 caption options (1 short under 125 chars, 1 long under 2200 chars),
(3) 15 hashtags (5 broad, 5 niche, 5 location-specific).
Output JSON only with keys: hooks, caption_short, caption_long, hashtags`;

const IMAGE_SYSTEM_PROMPT = `Given a destination name and template ID {template_id}, generate a photo album description and 5 image prompts for FLUX/Midjourney.
Each prompt: [subject], [style], [composition], [mood]. Match the template's aspect ratio and color palette.
Output JSON only: {{"description": "...", "prompts": ["...", "...", "...", "...", "..."]}}`;

function extractJSON(content: string): string {
  let cleaned = content.trim();
  if (cleaned.startsWith("```")) {
    cleaned = cleaned.split("\n", 1)[1];
    if (cleaned.endsWith("```")) {
      cleaned = cleaned.slice(0, -3).trim();
    }
  }
  return cleaned;
}

export async function generateScript(
  topic: string,
  seeds: string[] = [],
): Promise<ScriptResult> {
  try {
    const response = await anthropic.messages.create({
      model: "claude-sonnet-4-5-20250929",
      max_tokens: 1024,
      messages: [
        {
          role: "user",
          content: SCRIPT_SYSTEM_PROMPT.replace("{topic}", topic).replace(
            "{seeds}",
            seeds.length > 0 ? seeds.join(", ") : "none",
          ),
        },
      ],
    });

    const content = response.content[0];
    if (content.type === "text") {
      const parsed = JSON.parse(extractJSON(content.text));
      return {
        hook: parsed.hook || "",
        body: parsed.body || "",
        cta: parsed.cta || "",
      };
    }
    throw new Error("Unexpected response type");
  } catch {
    return {
      hook: `Bạn đã nghe về ${topic} chưa?`,
      body: `Hôm nay mình sẽ review ${topic} cho các bạn biết nhé!`,
      cta: "Follow để xem thêm nội dung du lịch mỗi ngày!",
    };
  }
}

export async function generateCaptions(
  script: ScriptResult,
  videoDesc: string = "Travel video",
): Promise<CaptionResult> {
  try {
    const scriptJson = JSON.stringify(script);
    const response = await anthropic.messages.create({
      model: "claude-sonnet-4-5-20250929",
      max_tokens: 1024,
      messages: [
        {
          role: "user",
          content: `${CAPTION_SYSTEM_PROMPT}\n\nScript: ${scriptJson}\nVideo: ${videoDesc}`,
        },
      ],
    });

    const content = response.content[0];
    if (content.type === "text") {
      const parsed = JSON.parse(extractJSON(content.text));
      return {
        hooks: parsed.hooks || [],
        caption_short: parsed.caption_short || "",
        caption_long: parsed.caption_long || "",
        hashtags: parsed.hashtags || [],
      };
    }
    throw new Error("Unexpected response type");
  } catch {
    return {
      hooks: ["Xem ngay!", "Bạn không tin nổi", "Check this out"],
      caption_short: "Khám phá điểm đến hot nhất hôm nay! #dulich",
      caption_long:
        "Hôm nay mình mang đến cho các bạn những địa điểm cực hot!\n\nXem hết video để không bỏ lỡ nhé!\n\n#dulich #vietnam #travel",
      hashtags: ["#dulich", "#vietnam", "#travel", "#xanh", "#review", "#phuquoc", "#danang", "#hanoi"],
    };
  }
}

export async function generateImagePrompts(
  destination: string,
  templateId: string = "default",
): Promise<ImagePromptResult> {
  try {
    const response = await anthropic.messages.create({
      model: "claude-sonnet-4-5-20250929",
      max_tokens: 1024,
      messages: [
        {
          role: "user",
          content: IMAGE_SYSTEM_PROMPT.replace("{template_id}", templateId) +
            `\n\nDestination: ${destination}`,
        },
      ],
    });

    const content = response.content[0];
    if (content.type === "text") {
      const parsed = JSON.parse(extractJSON(content.text));
      return {
        description: parsed.description || `Photo album về ${destination}`,
        prompts: parsed.prompts || [],
      };
    }
    throw new Error("Unexpected response type");
  } catch {
    return {
      description: `Photo album về ${destination}`,
      prompts: [
        `Beautiful landscape of ${destination}, golden hour, wide angle, cinematic`,
        `Street food in ${destination}, vibrant colors, close-up, appetizing`,
        `Sunset over ${destination}, silhouette, dramatic lighting, travel photography`,
        `Local market in ${destination}, candid, documentary style, authentic`,
        `Beach/resort in ${destination}, turquoise water, drone view, luxury travel`,
      ],
    };
  }
}

export async function generateAll(params: {
  topic: string;
  templateId?: string;
  seeds?: string[];
}): Promise<GenerateResult> {
  const { topic, templateId = "default", seeds = [] } = params;

  const [script, captions, images] = await Promise.all([
    generateScript(topic, seeds),
    generateCaptions({ hook: "", body: "", cta: "" }, "Travel video"),
    generateImagePrompts(topic, templateId),
  ]);

  // Re-generate captions with actual script
  const finalCaptions = await generateCaptions(script, "Travel video");

  return {
    script,
    captions: finalCaptions,
    images,
  };
}
