import { NextResponse } from "next/server";
import { connectToDatabase } from "@/lib/db";

export const runtime = "nodejs";

export async function GET() {
  try {
    const { db } = await connectToDatabase();

    const contents = await db.collection("content")
      .find({ content_type: "album" })
      .sort({ created_at: -1 })
      .toArray();

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
        name: data.album_name || doc.name || `Album ${data.topic || "Du lịch"}`,
        albumName: data.album_name || "",
        topic: data.topic || "Du lịch",
        title: data.title || "",
        subtitle: data.subtitle || "",
        creator: data.creator_id || "lan_anh",
        date: doc.created_at ? doc.created_at.split("T")[0] : new Date().toISOString().split("T")[0],
        status,
        images: data.images || {},
        photos: data.photos || [],
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

// ── POST: Desktop sync album lên dashboard ──────────────────────────
export async function POST(request: Request) {
  try {
    const { db } = await connectToDatabase();
    const body = await request.json();
    const { albumName, topic, creatorId, description, photos } = body;

    if (!albumName || !albumName.trim()) {
      return NextResponse.json(
        { success: false, error: "Tên album không được để trống" },
        { status: 400 },
      );
    }

    const now = new Date().toISOString();
    const doc = {
      content_type: "album",
      name: albumName.trim(),
      status: "draft",
      created_at: now,
      updated_at: now,
      data: {
        album_name: albumName.trim(),
        topic: topic || "Du lịch",
        title: albumName.trim(),
        subtitle: description || "",
        creator_id: creatorId || "lan_anh",
        photos: photos || [],
        images: {},
      },
    };

    const result = await db.collection("content").insertOne(doc);

    return NextResponse.json({
      success: true,
      data: {
        id: result.insertedId.toString(),
        albumName: albumName.trim(),
      },
    });
  } catch (error: any) {
    console.error("POST /api/albums error:", error);
    return NextResponse.json(
      { success: false, error: "Không thể sync album", details: error.message },
      { status: 500 },
    );
  }
}
