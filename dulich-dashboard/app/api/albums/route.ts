import { NextResponse } from "next/server";
import { connectToDatabase } from "@/lib/db";

export const runtime = "nodejs";

export async function GET() {
  try {
    const { db } = await connectToDatabase();
    
    // Fetch all album items from content collection
    const contents = await db.collection("content")
      .find({ content_type: "album" })
      .sort({ created_at: -1 })
      .toArray();

    // Map to frontend Album format
    const albums = contents.map((doc) => {
      const data = doc.data || {};
      
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
        name: data.title || doc.name || `Album ${data.topic || "Du lịch"}`,
        topic: data.topic || "Du lịch",
        title: data.title || "Review",
        subtitle: data.subtitle || "",
        templateId: data.canva_frame_used || "default",
        creator: data.creator_id || "lan_anh",
        date: doc.created_at ? doc.created_at.split("T")[0] : new Date().toISOString().split("T")[0],
        status,
        images: data.images || {},
      };
    });

    return NextResponse.json({ success: true, data: albums });
  } catch (error: any) {
    console.error("GET /api/albums error:", error);
    return NextResponse.json(
      { success: false, error: "Không thể lấy danh sách album", details: error.message },
      { status: 500 },
    );
  }
}
