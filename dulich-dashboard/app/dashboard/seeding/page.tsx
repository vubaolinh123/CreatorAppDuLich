"use client";

import { useEffect, useState } from "react";
import { Store, Plus, Edit2, Trash2, Loader2, MapPin, Tag, Lightbulb, Info } from "lucide-react";

interface SeedingItem {
  id: string;
  name: string;
  category: string;
  location: string;
  description: string;
  mention_guide: string;
  status: string;
}

export default function SeedingPage() {
  const [items, setItems] = useState<SeedingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Form states
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("restaurant");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const [mentionGuide, setMentionGuide] = useState("");

  const fetchSeedingItems = async () => {
    setLoading(true);
    setErrorMsg("");
    try {
      const res = await fetch("/api/seeding");
      const data = await res.json();
      if (data.success) {
        setItems(data.data);
      } else {
        setErrorMsg(data.error || "Không thể tải danh sách seeding.");
      }
    } catch (err: any) {
      setErrorMsg(err.toString());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSeedingItems();
  }, []);

  const handleSaveSeeding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !location.trim()) {
      setErrorMsg("Vui lòng nhập tên địa điểm và khu vực.");
      return;
    }

    setSaving(true);
    setErrorMsg("");
    setSuccessMsg("");

    const payload = {
      name,
      category,
      location,
      description,
      mention_guide: mentionGuide,
    };

    try {
      const url = editingId ? `/api/seeding/${editingId}` : "/api/seeding";
      const method = editingId ? "PATCH" : "POST";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.success) {
        setSuccessMsg(editingId ? "Cập nhật thành công!" : "Thêm mới thành công!");
        resetForm();
        fetchSeedingItems();
        setTimeout(() => setSuccessMsg(""), 3000);
      } else {
        setErrorMsg(data.error || "Lưu thất bại.");
      }
    } catch (err: any) {
      setErrorMsg(err.toString());
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (item: SeedingItem) => {
    setEditingId(item.id);
    setName(item.name);
    setCategory(item.category);
    setLocation(item.location);
    setDescription(item.description);
    setMentionGuide(item.mention_guide);
    setErrorMsg("");
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Bạn có chắc chắn muốn xóa địa điểm seeding này?")) return;
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const res = await fetch(`/api/seeding/${id}`, {
        method: "DELETE",
      });
      const data = await res.json();
      if (data.success) {
        setSuccessMsg("Đã xóa địa điểm seeding.");
        fetchSeedingItems();
        setTimeout(() => setSuccessMsg(""), 3000);
      } else {
        setErrorMsg(data.error || "Xóa thất bại.");
      }
    } catch (err: any) {
      setErrorMsg(err.toString());
    }
  };

  const resetForm = () => {
    setEditingId(null);
    setName("");
    setCategory("restaurant");
    setLocation("");
    setDescription("");
    setMentionGuide("");
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto text-gray-200">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <MapPin size={24} className="text-purple-400" />
          📍 Quản lý Seeding Địa Điểm
        </h1>
        <p className="text-sm text-gray-500 mt-2">
          Thiết lập danh sách các nhà hàng, quán ăn, khách sạn để AI tự động lồng ghép khéo léo vào kịch bản (seeding).
        </p>
      </header>

      {errorMsg && <div className="bg-red-500/10 border border-red-500/25 text-red-400 p-4 rounded-xl text-sm mb-6">⚠ {errorMsg}</div>}
      {successMsg && <div className="bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 p-4 rounded-xl text-sm mb-6">✓ {successMsg}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Left Form (2 Cols) */}
        <div className="lg:col-span-2 bg-[#1a1a1a] rounded-xl border border-[#333] p-6 h-fit">
          <h2 className="text-sm font-semibold text-white mb-6 flex items-center gap-1.5">
            {editingId ? <Edit2 size={16} className="text-purple-400" /> : <Plus size={16} className="text-purple-400" />}
            {editingId ? "Chỉnh sửa địa điểm" : "Thêm mới địa điểm"}
          </h2>

          <form onSubmit={handleSaveSeeding} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Tên địa điểm <span className="text-red-500">*</span></label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="VD: Mỳ Quảng Bà Mua, Melia Resort..."
                className="w-full bg-[#111] border border-[#333] rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">Phân loại</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full bg-[#111] border border-[#333] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
                >
                  <option value="restaurant">🍜 Nhà hàng / Quán ăn</option>
                  <option value="hotel">🏨 Khách sạn / Resort</option>
                  <option value="sightseeing">🏔️ Tham quan / Check-in</option>
                  <option value="other">🏕️ Khác</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">Khu vực / Tỉnh thành <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="VD: Đà Nẵng, Phú Quốc..."
                  className="w-full bg-[#111] border border-[#333] rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Mô tả đặc trưng</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="VD: Nổi tiếng với món mỳ ếch, bãi biển riêng ngắm hoàng hôn cực đỉnh..."
                className="w-full bg-[#111] border border-[#333] rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-purple-500 min-h-[80px] resize-y"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Gợi ý cách lồng ghép (Mention Guide)</label>
              <input
                type="text"
                value={mentionGuide}
                onChange={(e) => setMentionGuide(e.target.value)}
                placeholder="VD: Đề xuất là địa điểm ăn trưa không thể bỏ lỡ..."
                className="w-full bg-[#111] border border-[#333] rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              {editingId && (
                <button
                  type="button"
                  onClick={resetForm}
                  className="px-4 py-2 bg-transparent hover:bg-[#222] border border-[#333] text-gray-400 hover:text-white rounded-lg text-xs font-medium transition"
                >
                  Hủy
                </button>
              )}
              <button
                type="submit"
                disabled={saving}
                className="px-5 py-2 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white rounded-lg text-xs font-semibold transition disabled:opacity-50 flex items-center gap-1.5"
              >
                {saving && <Loader2 className="animate-spin" size={12} />}
                {editingId ? "💾 Cập nhật" : "➕ Thêm địa điểm"}
              </button>
            </div>
          </form>
        </div>

        {/* Right List (3 Cols) */}
        <div className="lg:col-span-3 space-y-4">
          <div className="bg-[#1a1a1a] rounded-xl border border-[#333] p-6">
            <h2 className="text-sm font-semibold text-white mb-6">Danh sách seeding ({items.length})</h2>

            {loading ? (
              <div className="flex flex-col items-center justify-center py-20">
                <Loader2 className="animate-spin text-purple-500 mb-2" size={24} />
                <p className="text-xs text-gray-500">Đang tải danh sách...</p>
              </div>
            ) : items.length === 0 ? (
              <div className="text-center py-20 border border-dashed border-[#333] rounded-xl">
                <Store className="mx-auto text-gray-600 mb-2" size={32} />
                <p className="text-xs text-gray-500">Chưa có địa điểm seeding nào.</p>
              </div>
            ) : (
              <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
                {items.map((item) => (
                  <div key={item.id} className="bg-[#111] border border-[#222] rounded-xl p-4 hover:border-purple-500/20 transition">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-base">
                          {item.category === "restaurant" ? "🍜" : item.category === "hotel" ? "🏨" : "🏔️"}
                        </span>
                        <h3 className="text-sm font-semibold text-white">{item.name}</h3>
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/15 px-2 py-0.5 rounded-full uppercase">
                          {item.location}
                        </span>
                      </div>
                      
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleEdit(item)}
                          className="p-1 hover:bg-[#222] text-gray-400 hover:text-white rounded transition"
                          title="Sửa"
                        >
                          <Edit2 size={12} />
                        </button>
                        <button
                          onClick={() => handleDelete(item.id)}
                          className="p-1 hover:bg-[#222] text-gray-400 hover:text-red-400 rounded transition"
                          title="Xóa"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>

                    <p className="text-xs text-gray-400 leading-relaxed mb-3">{item.description || "Chưa có mô tả chi tiết."}</p>
                    
                    {item.mention_guide && (
                      <div className="bg-purple-500/5 border border-purple-500/10 rounded-lg p-2.5 flex items-start gap-2">
                        <Lightbulb size={12} className="text-purple-400 mt-0.5 flex-shrink-0" />
                        <p className="text-[11px] text-purple-300 leading-normal">
                          <strong>Gợi ý lồng ghép: </strong> {item.mention_guide}
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
