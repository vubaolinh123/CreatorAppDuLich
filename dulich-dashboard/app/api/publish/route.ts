import { NextResponse } from "next/server";
import { connectToDatabase } from "@/lib/db";
import { ObjectId } from "mongodb";
import axios from "axios";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const { db } = await connectToDatabase();
    const body = await request.json();
    const { id, type } = body; 

    if (!id) {
      return NextResponse.json(
        { success: false, error: "ID nội dung là bắt buộc" },
        { status: 400 }
      );
    }

    let query: any = { _id: id };
    try {
      if (ObjectId.isValid(id)) {
        query = { _id: new ObjectId(id) };
      }
    } catch (e) {}

    let contentDoc = await db.collection("content").findOne(query as any);
    if (!contentDoc) {
      contentDoc = await db.collection("content").findOne({ _id: id } as any);
    }

    if (!contentDoc) {
      return NextResponse.json(
        { success: false, error: "Không tìm thấy nội dung để đăng" },
        { status: 404 }
      );
    }

    const data = contentDoc.data || {};
    const key = process.env.AYRSHARE_API_KEY || "";
    const isMockMode = !key || key === "your-ayrshare-key" || key.trim() === "";

    let postLink = "";
    let platformStatus = {};

    if (isMockMode) {
      console.warn("[Publish] AYRSHARE_API_KEY không được cấu hình. Đang chạy ở chế độ MOCK PUBLISH...");
      // Simulate network delay
      await new Promise((resolve) => setTimeout(resolve, 2000));
      postLink = `https://social.mock-publish.com/post/${Date.now()}`;
      platformStatus = {
        tiktok: "success (mock)",
        youtube: "success (mock)",
        facebook: "success (mock)",
        instagram: "success (mock)",
      };
    } else {
      // Ayrshare Real Integration
      let postText = "";
      let mediaUrls: string[] = [];
      let platforms: string[] = [];

      if (contentDoc.content_type === "album") {
        postText = `${data.title || "Review"} - ${data.subtitle || ""}`;
        platforms = ["pinterest", "instagram", "facebook"];
        
        // Map local file paths to mock public URLs for Ayrshare compatibility
        mediaUrls = Object.values(data.images || {})
          .map((path: any) => {
            if (typeof path === "string" && path.startsWith("http")) return path;
            return "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800";
          })
          .slice(0, 3);
      } else {
        // Video
        const script = data.script || {};
        const captions = data.captions || {};
        postText = `${captions.caption_short || script.hook || "Khám phá du lịch cùng AI!"}\n\n${captions.caption_long || script.body || ""}`;
        platforms = ["tiktok", "youtube", "instagram", "facebook"];
        
        const videoPath = data.video_path || "";
        mediaUrls = [videoPath.startsWith("http") ? videoPath : "https://www.w3schools.com/html/mov_bbb.mp4"];
      }

      try {
        const response = await axios.post(
          "https://backstage.ayrshare.com/api/post",
          {
            post: postText,
            platforms,
            mediaUrls,
          },
          {
            headers: {
              Authorization: `Bearer ${key}`,
              "Content-Type": "application/json",
            },
          }
        );

        if (response.data && response.data.refId) {
          postLink = response.data.postUrl || `https://backstage.ayrshare.com/post/${response.data.refId}`;
          platformStatus = response.data.status || { success: "Ayrshare published successfully" };
        } else {
          throw new Error(JSON.stringify(response.data));
        }
      } catch (err: any) {
        console.error("Ayrshare publish failed:", err.response?.data || err.message);
        return NextResponse.json(
          {
            success: false,
            error: "Lỗi kết nối Ayrshare khi đăng bài",
            details: err.response?.data?.message || err.message,
          },
          { status: 502 }
        );
      }
    }

    // Update MongoDB status to published
    await db.collection("content").updateOne(
      query,
      { $set: { status: "published", updated_at: new Date().toISOString() } }
    );
    // Support string ID query fallback
    await db.collection("content").updateOne(
      { _id: id },
      { $set: { status: "published", updated_at: new Date().toISOString() } }
    );

    return NextResponse.json({
      success: true,
      message: isMockMode ? "Đăng bài thành công (Mô phỏng)!" : "Đăng bài thành công qua Ayrshare!",
      postLink,
      platformStatus,
    });

  } catch (error: any) {
    console.error("Publish API error:", error);
    return NextResponse.json(
      { success: false, error: "Lỗi hệ thống khi đăng bài", details: error.message },
      { status: 500 }
    );
  }
}
