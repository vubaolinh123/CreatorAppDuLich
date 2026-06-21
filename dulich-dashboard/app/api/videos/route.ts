import { NextResponse } from "next/server";
import { supabase, getAllContent } from "@/lib/supabase";

export const runtime = "nodejs";

export async function GET() {
  try {
    // Fetch all video content from Supabase
    const { data: contents, error } = await supabase
      .from("content")
      .select("*")
      .order("created_at", { ascending: false });

    if (error) {
      console.error("[GET /api/videos] Supabase error:", error);
      return NextResponse.json(
        { success: false, error: "Không thể lấy danh sách video", details: error.message },
        { status: 500 }
      );
    }

    // Map to frontend VideoItem format
    const videos = (contents || []).map((doc: any) => {
      const script = doc.script || {};
      
      // Determine status for frontend
      let status = "Chờ duyệt";
      if (doc.status === "approved") {
        status = "Đã duyệt";
      } else if (doc.status === "published") {
        status = "Đã đăng";
      } else if (doc.status === "rejected") {
        status = "Từ chối";
      } else if (doc.status === "rendering") {
        status = "Đang render";
      }

      return {
        id: doc.id,
        name: doc.title || `Video ${doc.topic || "Du lịch"}`,
        creator: doc.user_id || "Unknown",
        status,
        date: doc.created_at ? doc.created_at.split("T")[0] : new Date().toISOString().split("T")[0],
        topic: doc.topic || "Du lịch",
        templateId: "default",
        seeds: [],
        script: {
          hook: script.hook || doc.hook_text || "",
          body: script.body || "",
          cta: script.cta || "",
        },
        captions: {
          hooks: [doc.hook_text || ""],
          caption_short: script.hook || "",
          caption_long: script.body || "",
          hashtags: [],
        },
        images: {
          description: "",
          prompts: [],
        },
        videoPath: doc.drive_url || doc.local_path || "",
        audioPath: "",
        driveUrl: doc.drive_url || "",
        localPath: doc.local_path || "",
      };
    });

    return NextResponse.json({ success: true, data: videos });
  } catch (error: any) {
    console.error("GET /api/videos error:", error);
    return NextResponse.json(
      { success: false, error: "Không thể lấy danh sách video", details: error.message },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const { title, topic, script, drive_url, local_path, user_id, hook_style, hook_text, video_type } = payload;

    // Insert new content into Supabase
    const { data, error } = await supabase
      .from("content")
      .insert({
        user_id: user_id || null,
        content_type: video_type || "video",
        status: "pending",
        title: title || "Video mới",
        topic: topic || "Du lịch",
        script: script || {},
        drive_url: drive_url || "",
        local_path: local_path || "",
        hook_style: hook_style || "",
        hook_text: hook_text || "",
        video_type: video_type || "video",
      })
      .select()
      .single();

    if (error) {
      console.error("[POST /api/videos] Supabase error:", error);
      return NextResponse.json(
        { success: false, error: "Không thể lưu video", details: error.message },
        { status: 500 }
      );
    }

    return NextResponse.json({ success: true, data });
  } catch (error: any) {
    console.error("POST /api/videos error:", error);
    return NextResponse.json(
      { success: false, error: "Lỗi hệ thống khi lưu video", details: error.message },
      { status: 500 }
    );
  }
}
