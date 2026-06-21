import { NextResponse } from "next/server";
import { supabase, getContentById, updateContentStatus } from "@/lib/supabase";

export const runtime = "nodejs";

export async function PATCH(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json();
    const { status } = body;

    if (!status) {
      return NextResponse.json(
        { success: false, error: "Status là bắt buộc" },
        { status: 400 }
      );
    }

    // Map frontend status to Supabase status
    let supabaseStatus = "pending";
    if (status === "Đã duyệt") {
      supabaseStatus = "approved";
    } else if (status === "Đã đăng") {
      supabaseStatus = "published";
    } else if (status === "Từ chối") {
      supabaseStatus = "rejected";
    }

    // Update in Supabase
    const { error } = await supabase
      .from("content")
      .update({ status: supabaseStatus, updated_at: new Date().toISOString() })
      .eq("id", params.id);

    if (error) {
      console.error("[PATCH /api/videos/[id]] Supabase error:", error);
      return NextResponse.json(
        { success: false, error: "Không thể cập nhật trạng thái", details: error.message },
        { status: 500 }
      );
    }

    return NextResponse.json({ success: true, message: `Cập nhật trạng thái thành: ${status}` });
  } catch (error: any) {
    console.error("PATCH /api/videos/[id] error:", error);
    return NextResponse.json(
      { success: false, error: "Lỗi hệ thống khi cập nhật trạng thái", details: error.message },
      { status: 500 }
    );
  }
}

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    // Get content from Supabase
    const { data: videoDoc, error } = await supabase
      .from("content")
      .select("*")
      .eq("id", params.id)
      .single();

    if (error || !videoDoc) {
      return NextResponse.json(
        { success: false, error: "Không tìm thấy video" },
        { status: 404 }
      );
    }

    // Map to frontend format
    const script = videoDoc.script || {};
    
    let status = "Chờ duyệt";
    if (videoDoc.status === "approved") {
      status = "Đã duyệt";
    } else if (videoDoc.status === "published") {
      status = "Đã đăng";
    } else if (videoDoc.status === "rejected") {
      status = "Từ chối";
    } else if (videoDoc.status === "rendering") {
      status = "Đang render";
    }

    const video = {
      id: videoDoc.id,
      name: videoDoc.title || `Video ${videoDoc.topic || "Du lịch"}`,
      creator: videoDoc.user_id || "Unknown",
      status,
      date: videoDoc.created_at ? videoDoc.created_at.split("T")[0] : new Date().toISOString().split("T")[0],
      topic: videoDoc.topic || "Du lịch",
      templateId: "default",
      seeds: [],
      script: {
        hook: script.hook || videoDoc.hook_text || "",
        body: script.body || "",
        cta: script.cta || "",
      },
      captions: {
        hooks: [videoDoc.hook_text || ""],
        caption_short: script.hook || "",
        caption_long: script.body || "",
        hashtags: [],
      },
      images: {
        description: "",
        prompts: [],
      },
      videoPath: videoDoc.drive_url || videoDoc.local_path || "",
      audioPath: "",
      driveUrl: videoDoc.drive_url || "",
      localPath: videoDoc.local_path || "",
    };

    return NextResponse.json({ success: true, data: video });
  } catch (error: any) {
    console.error("GET /api/videos/[id] error:", error);
    return NextResponse.json(
      { success: false, error: "Không thể lấy thông tin video", details: error.message },
      { status: 500 }
    );
  }
}
