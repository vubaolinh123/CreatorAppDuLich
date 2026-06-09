import { NextResponse } from "next/server";
import { connectToDatabase } from "@/lib/db";

export const runtime = "nodejs";

const DEFAULT_CREATORS = [
  { id: "lan_anh", name: "Lan Anh", email: "lananh@dulichapp.com", voice_provider: "vbee", voice_id: "hn_female_lananh", hook_preference: "zoom_in", videos: 0 },
  { id: "minh_tuan", name: "Minh Tuấn", email: "minhtuan@dulichapp.com", voice_provider: "vbee", voice_id: "hn_male_minhtuan", hook_preference: "glitch", videos: 0 },
  { id: "thu_ha", name: "Thu Hà", email: "thuha@dulichapp.com", voice_provider: "vbee", voice_id: "hn_female_thutrang", hook_preference: "cinematic_vignette", videos: 0 },
  { id: "duc_anh", name: "Đức Anh", email: "ducanh@dulichapp.com", voice_provider: "vbee", voice_id: "hcm_male_ducanh", hook_preference: "zoom_out", videos: 0 },
  { id: "ngoc_mai", name: "Ngọc Mai", email: "ngocmai@dulichapp.com", voice_provider: "vbee", voice_id: "hn_female_ngocmai", hook_preference: "zoom_in", videos: 0 }
];

export async function GET() {
  try {
    const { db } = await connectToDatabase();
    const dbCreators = await db.collection("creators").find({}).toArray();

    // Aggregate counts of videos per creator
    const videoCounts = await db.collection("content")
      .aggregate([
        { $match: { content_type: { $in: ["personal_video", "video"] } } },
        { $group: { _id: "$data.creator_id", count: { $sum: 1 } } }
      ]).toArray();

    const countsMap: Record<string, number> = {};
    videoCounts.forEach(c => {
      if (c._id) countsMap[c._id] = c.count;
    });

    let creatorsList = [];
    if (dbCreators.length > 0) {
      creatorsList = dbCreators.map(c => ({
        id: c._id.toString(),
        name: c.name,
        email: `${c._id}@dulichapp.com`,
        voice_provider: c.voice_provider || "vbee",
        voice_id: c.voice_id || "default",
        hook_preference: c.hook_preference || "zoom_in",
        videos: countsMap[c._id.toString()] || 0
      }));
    } else {
      creatorsList = DEFAULT_CREATORS.map(c => ({
        ...c,
        videos: countsMap[c.id] || 0
      }));
    }

    return NextResponse.json({ success: true, data: creatorsList });
  } catch (error: any) {
    console.error("GET /api/creators error:", error);
    return NextResponse.json(
      { success: false, error: "Không thể lấy danh sách creator", details: error.message },
      { status: 500 }
    );
  }
}
