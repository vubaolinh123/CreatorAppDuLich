import { NextResponse } from "next/server";
import { connectToDatabase } from "@/lib/db";

export const runtime = "nodejs";

export async function GET() {
  try {
    const { db } = await connectToDatabase();
    const items = await db.collection("seeding").find({}).toArray();
    
    // Map to frontend format
    const mapped = items.map((item) => ({
      id: item._id.toString(),
      name: item.name,
      category: item.category || "restaurant",
      location: item.location || "Vietnam",
      description: item.description || "",
      mention_guide: item.mention_guide || "",
      status: item.status || "active",
    }));

    return NextResponse.json({ success: true, data: mapped });
  } catch (error: any) {
    console.error("GET /api/seeding error:", error);
    return NextResponse.json(
      { success: false, error: "Không thể tải danh sách seeding", details: error.message },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const { db } = await connectToDatabase();
    const body = await request.json();
    const { name, category, location, description, mention_guide } = body;

    if (!name || !location) {
      return NextResponse.json(
        { success: false, error: "Tên địa điểm và khu vực là bắt buộc" },
        { status: 400 }
      );
    }

    const doc = {
      name,
      category: category || "restaurant",
      location,
      description: description || "",
      mention_guide: mention_guide || "",
      status: "active",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    const result = await db.collection("seeding").insertOne(doc);

    return NextResponse.json({
      success: true,
      data: {
        id: result.insertedId.toString(),
        ...doc,
      }
    });
  } catch (error: any) {
    console.error("POST /api/seeding error:", error);
    return NextResponse.json(
      { success: false, error: "Không thể lưu địa điểm seeding", details: error.message },
      { status: 500 }
    );
  }
}
