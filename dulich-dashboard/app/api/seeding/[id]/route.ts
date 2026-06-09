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
    const { name, category, location, description, mention_guide, status } = body;

    let query: any = { _id: params.id };
    try {
      if (ObjectId.isValid(params.id)) {
        query = { _id: new ObjectId(params.id) };
      }
    } catch (e) {}

    const patchDoc: any = {};
    if (name) patchDoc.name = name;
    if (category) patchDoc.category = category;
    if (location) patchDoc.location = location;
    if (description !== undefined) patchDoc.description = description;
    if (mention_guide !== undefined) patchDoc.mention_guide = mention_guide;
    if (status) patchDoc.status = status;
    patchDoc.updated_at = new Date().toISOString();

    const result = await db.collection("seeding").updateOne(query as any, { $set: patchDoc });

    if (result.matchedCount === 0) {
      const strResult = await db.collection("seeding").updateOne({ _id: params.id } as any, { $set: patchDoc });
      if (strResult.matchedCount === 0) {
        return NextResponse.json(
          { success: false, error: "Không tìm thấy địa điểm seeding" },
          { status: 404 }
        );
      }
    }

    return NextResponse.json({ success: true, message: "Cập nhật thành công!" });
  } catch (error: any) {
    console.error("PATCH /api/seeding/[id] error:", error);
    return NextResponse.json(
      { success: false, error: "Lỗi hệ thống khi cập nhật", details: error.message },
      { status: 500 }
    );
  }
}

export async function DELETE(
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

    const result = await db.collection("seeding").deleteOne(query as any);

    if (result.deletedCount === 0) {
      const strResult = await db.collection("seeding").deleteOne({ _id: params.id } as any);
      if (strResult.deletedCount === 0) {
        return NextResponse.json(
          { success: false, error: "Không tìm thấy địa điểm seeding" },
          { status: 404 }
        );
      }
    }

    return NextResponse.json({ success: true, message: "Đã xóa địa điểm seeding" });
  } catch (error: any) {
    console.error("DELETE /api/seeding/[id] error:", error);
    return NextResponse.json(
      { success: false, error: "Lỗi hệ thống khi xóa", details: error.message },
      { status: 500 }
    );
  }
}
