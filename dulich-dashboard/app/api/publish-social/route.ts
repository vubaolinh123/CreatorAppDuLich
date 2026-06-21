import { NextResponse } from "next/server";
import { supabase, getContentById, createPublishLog } from "@/lib/supabase";
import axios from "axios";

export const runtime = "nodejs";

// TikTok Content Posting API
async function publishToTikTok(videoUrl: string, caption: string, openId: string): Promise<{ success: boolean; postId?: string; error?: string }> {
  const accessToken = process.env.TIKTOK_ACCESS_TOKEN;
  
  if (!accessToken) {
    return { success: false, error: "TikTok access token chưa được cấu hình" };
  }

  try {
    // Step 1: Initialize video upload
    const initResponse = await axios.post(
      "https://open.tiktokapis.com/v2/post/publish/video/init/",
      {
        post_info: {
          title: caption.slice(0, 150),
          privacy_level: "PUBLIC_TO_EVERYONE",
          disable_duet: false,
          disable_comment: false,
          disable_stitch: false,
        },
        source_info: {
          source: "FILE_UPLOAD",
          video_size: 0,
        },
      },
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
      }
    );

    if (initResponse.data?.data?.upload_url) {
      // Step 2: Upload video file
      const uploadUrl = initResponse.data.data.upload_url;
      const publishId = initResponse.data.data.publish_id;

      // Download video from URL
      const videoResponse = await axios.get(videoUrl, { responseType: "arraybuffer" });
      
      // Upload to TikTok
      await axios.put(uploadUrl, videoResponse.data, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "video/mp4",
        },
      });

      return { success: true, postId: publishId };
    } else {
      return { success: false, error: "Không thể khởi tạo upload video" };
    }
  } catch (error: any) {
    console.error("[TikTok] Publish error:", error.response?.data || error.message);
    return { 
      success: false, 
      error: error.response?.data?.error?.message || error.message 
    };
  }
}

// Facebook Graph API
async function publishToFacebook(videoUrl: string, caption: string, pageId: string): Promise<{ success: boolean; postId?: string; error?: string }> {
  const accessToken = process.env.FACEBOOK_ACCESS_TOKEN;
  
  if (!accessToken || !pageId) {
    return { success: false, error: "Facebook access token hoặc page ID chưa được cấu hình" };
  }

  try {
    // Step 1: Create video container
    const containerResponse = await axios.post(
      `https://graph.facebook.com/v19.0/${pageId}/videos`,
      {
        file_url: videoUrl,
        title: caption.slice(0, 255),
        description: caption,
        access_token: accessToken,
      }
    );

    const videoId = containerResponse.data?.id;

    if (!videoId) {
      return { success: false, error: "Không thể tạo video container" };
    }

    // Step 2: Wait for processing and publish
    // Note: In production, you should poll for video status
    // For now, we'll assume it's published
    
    // Create post with the video
    const postResponse = await axios.post(
      `https://graph.facebook.com/v19.0/${pageId}/feed`,
      {
        message: caption,
        attached_media: [{ media_fbid: videoId }],
        access_token: accessToken,
      }
    );

    return { success: true, postId: postResponse.data?.id || videoId };
  } catch (error: any) {
    console.error("[Facebook] Publish error:", error.response?.data || error.message);
    return { 
      success: false, 
      error: error.response?.data?.error?.message || error.message 
    };
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { id, platform } = body;

    if (!id || !platform) {
      return NextResponse.json(
        { success: false, error: "ID và platform là bắt buộc" },
        { status: 400 }
      );
    }

    if (!["tiktok", "facebook"].includes(platform)) {
      return NextResponse.json(
        { success: false, error: "Platform không hợp lệ. Hỗ trợ: tiktok, facebook" },
        { status: 400 }
      );
    }

    // Get content from Supabase
    const content = await getContentById(id);
    if (!content) {
      return NextResponse.json(
        { success: false, error: "Không tìm thấy nội dung" },
        { status: 404 }
      );
    }

    const videoUrl = content.drive_url || content.local_path;
    if (!videoUrl) {
      return NextResponse.json(
        { success: false, error: "Không tìm thấy URL video" },
        { status: 400 }
      );
    }

    // Prepare caption
    const script = content.script || {};
    const caption = `${script.hook || content.hook_text || ""}\n\n${script.body || ""}\n\n${script.cta || ""}`.trim();

    // Publish based on platform
    let result: { success: boolean; postId?: string; error?: string };
    
    if (platform === "tiktok") {
      const openId = process.env.TIKTOK_OPEN_ID || "";
      result = await publishToTikTok(videoUrl, caption, openId);
    } else {
      const pageId = process.env.FACEBOOK_PAGE_ID || "";
      result = await publishToFacebook(videoUrl, caption, pageId);
    }

    // Log the publish attempt
    await createPublishLog({
      content_id: id,
      platform: platform as any,
      platform_post_id: result.postId || "",
      post_url: result.postId ? `https://${platform}.com/${result.postId}` : "",
      status: result.success ? "success" : "failed",
      error_message: result.error || "",
    });

    if (result.success) {
      // Update content status to published
      await supabase
        .from("content")
        .update({ status: "published", updated_at: new Date().toISOString() })
        .eq("id", id);

      return NextResponse.json({
        success: true,
        message: `Đăng bài lên ${platform === "tiktok" ? "TikTok" : "Facebook"} thành công!`,
        postId: result.postId,
        postUrl: result.postId ? `https://${platform}.com/${result.postId}` : "",
      });
    } else {
      return NextResponse.json(
        { success: false, error: result.error || "Đăng bài thất bại" },
        { status: 500 }
      );
    }
  } catch (error: any) {
    console.error("POST /api/publish-social error:", error);
    return NextResponse.json(
      { success: false, error: "Lỗi hệ thống khi đăng bài", details: error.message },
      { status: 500 }
    );
  }
}
