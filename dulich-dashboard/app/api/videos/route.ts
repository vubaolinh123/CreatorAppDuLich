import { NextResponse } from "next/server";
import { connectToDatabase } from "@/lib/db";

export const runtime = "nodejs";

export async function GET() {
  try {
    const { db } = await connectToDatabase();
    
    // Fetch all personal_video or video items from content collection
    const contents = await db.collection("content")
      .find({ content_type: { $in: ["personal_video", "video"] } })
      .sort({ created_at: -1 })
      .toArray();

    // Map to frontend VideoItem format
    const videos = contents.map((doc) => {
      const data = doc.data || {};
      const script = data.script || {};
      
      // Determine name
      let topic = data.topic || "Du lịch";
      let name = data.name || doc.name || `Video ${topic}`;
      
      let status = "Chờ duyệt";
      if (doc.status === "approved" || doc.status === "approved_review" || doc.status === "Đã duyệt") {
        status = "Đã duyệt";
      } else if (doc.status === "published" || doc.status === "Đã đăng") {
        status = "Đã đăng";
      } else if (doc.status === "rendering" || doc.status === "running") {
        status = "Đang render";
      }

      return {
        id: doc._id.toString(),
        name,
        creator: data.creator_name || data.creator_id || "Lan Anh",
        status,
        date: doc.created_at ? doc.created_at.split("T")[0] : new Date().toISOString().split("T")[0],
        topic,
        templateId: data.template_id || "default",
        seeds: data.seeds || [],
        script: {
          hook: script.hook || data.hook_text || "",
          body: script.body || "",
          cta: script.cta || "",
        },
        captions: data.captions || {
          hooks: [data.hook_text || ""],
          caption_short: script.hook || "",
          caption_long: script.body || "",
          hashtags: [],
        },
        images: data.images || {
          description: data.image_assets ? `Bộ ảnh du lịch ${topic}` : "",
          prompts: data.image_assets || [],
        },
        videoPath: data.video_path || "",
        audioPath: data.audio_path || "",
      };
    });

    return NextResponse.json({ success: true, data: videos });
  } catch (error: any) {
    console.error("GET /api/videos error:", error);
    return NextResponse.json(
      { success: false, error: "Không thể lấy danh sách video", details: error.message },
      { status: 500 },
    );
  }
}

export async function POST(request: Request) {
  try {
    const { db } = await connectToDatabase();
    const payload = await request.json();

    // Check if it is a personal/album run payload from pipeline
    if (payload.channel === "personal") {
      const jobId = payload.job_id;
      const creatorId = payload.creator_id;
      
      const existing = await db.collection("content").findOne({ job_id: jobId });
      if (existing) {
        return NextResponse.json({ success: true, data: existing, message: "Video already synced in MongoDB" });
      }

      const doc = {
        job_id: jobId,
        content_type: "personal_video",
        status: "pending_review",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        data: {
          creator_id: creatorId,
          video_path: payload.video_path,
          audio_path: payload.audio_path,
          script: payload.script,
          hook_style: payload.hook_style,
          hook_text: payload.hook_text,
        }
      };

      await db.collection("content").insertOne(doc);
      return NextResponse.json({ success: true, data: doc });
    }

    if (payload.channel === "album") {
      const jobId = payload.job_id;
      
      const existing = await db.collection("content").findOne({ job_id: jobId });
      if (existing) {
        return NextResponse.json({ success: true, data: existing, message: "Album already synced in MongoDB" });
      }

      const doc = {
        job_id: jobId,
        content_type: "album",
        status: "pending_review",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        data: {
          topic: payload.topic,
          title: payload.title,
          subtitle: payload.subtitle,
          images: payload.images,
        }
      };

      await db.collection("content").insertOne(doc);
      return NextResponse.json({ success: true, data: doc });
    }

    // Default manual or legacy POST handler
    const { topic, templateId, seeds, creator, script, captions, images } = payload;
    const doc = {
      content_type: "video",
      status: "pending_review",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      data: {
        topic: topic || "Vietnam",
        template_id: templateId || "default",
        creator_name: creator || "AI Pipeline",
        seeds: seeds || [],
        script,
        captions,
        images,
      }
    };
    await db.collection("content").insertOne(doc);
    return NextResponse.json({ success: true, data: doc });

  } catch (error: any) {
    console.error("POST /api/videos error:", error);
    return NextResponse.json(
      { success: false, error: "Lỗi hệ thống khi lưu video", details: error.message },
      { status: 500 },
    );
  }
}
