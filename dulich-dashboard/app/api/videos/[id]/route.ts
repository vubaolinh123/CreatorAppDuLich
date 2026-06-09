import { NextResponse } from "next/server";
import { connectToDatabase } from "@/lib/db";
import { ObjectId } from "mongodb";

export const runtime = "nodejs";

export async function PATCH(
  request: Request,
  { params }: { params: { id: string } },
) {
  try {
    const { db } = await connectToDatabase();
    const body = await request.json();
    const { status } = body;

    if (!status) {
      return NextResponse.json(
        { success: false, error: "Status là bắt buộc" },
        { status: 400 },
      );
    }

    // Map frontend status to MongoDB status
    let mongoStatus = "pending_review";
    if (status === "Đã duyệt") {
      mongoStatus = "approved";
    } else if (status === "Đã đăng") {
      mongoStatus = "published";
    }

    let query: any = { _id: params.id };
    try {
      if (ObjectId.isValid(params.id)) {
        query = { _id: new ObjectId(params.id) };
      }
    } catch (e) {}

    const result = await db.collection("content").updateOne(
      query as any,
      { $set: { status: mongoStatus, updated_at: new Date().toISOString() } }
    );

    if (result.matchedCount === 0) {
      // Fallback query if id is not matching ObjectId but string
      const strResult = await db.collection("content").updateOne(
        { _id: params.id } as any,
        { $set: { status: mongoStatus, updated_at: new Date().toISOString() } }
      );
      if (strResult.matchedCount === 0) {
        return NextResponse.json(
          { success: false, error: "Không tìm thấy video với ID yêu cầu" },
          { status: 404 },
        );
      }
    }

    return NextResponse.json({ success: true, message: `Cập nhật trạng thái thành: ${status}` });
  } catch (error: any) {
    console.error("PATCH /api/videos/[id] error:", error);
    return NextResponse.json(
      { success: false, error: "Lỗi hệ thống khi cập nhật trạng thái", details: error.message },
      { status: 500 },
    );
  }
}

export async function GET(
  request: Request,
  { params }: { params: { id: string } },
) {
  try {
    const { db } = await connectToDatabase();

    let query: any = { _id: params.id };
    try {
      if (ObjectId.isValid(params.id)) {
        query = { _id: new ObjectId(params.id) };
      }
    } catch (e) {}

    let videoDoc = await db.collection("content").findOne(query as any);
    if (!videoDoc) {
      videoDoc = await db.collection("content").findOne({ _id: params.id } as any);
    }

    if (!videoDoc) {
      return NextResponse.json(
        { success: false, error: "Không tìm thấy video" },
        { status: 404 },
      );
    }

    // Map to frontend format
    const data = videoDoc.data || {};
    const script = data.script || {};
    
    let status = "Chờ duyệt";
    if (videoDoc.status === "approved" || videoDoc.status === "approved_review" || videoDoc.status === "Đã duyệt") {
      status = "Đã duyệt";
    } else if (videoDoc.status === "published" || videoDoc.status === "Đã đăng") {
      status = "Đã đăng";
    } else if (videoDoc.status === "rendering" || videoDoc.status === "running") {
      status = "Đang render";
    }

    const video = {
      id: videoDoc._id.toString(),
      name: data.name || videoDoc.name || `Video ${data.topic || "Du lịch"}`,
      creator: data.creator_name || data.creator_id || "Lan Anh",
      status,
      date: videoDoc.created_at ? videoDoc.created_at.split("T")[0] : new Date().toISOString().split("T")[0],
      topic: data.topic || "Du lịch",
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
        description: data.image_assets ? `Bộ ảnh du lịch ${data.topic}` : "",
        prompts: data.image_assets || [],
      },
      videoPath: data.video_path || "",
      audioPath: data.audio_path || "",
    };

    return NextResponse.json({ success: true, data: video });
  } catch (error: any) {
    console.error("GET /api/videos/[id] error:", error);
    return NextResponse.json(
      { success: false, error: "Lỗi hệ thống khi lấy thông tin video", details: error.message },
      { status: 500 },
    );
  }
}
