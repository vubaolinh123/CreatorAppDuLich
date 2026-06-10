import React, { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";

interface SeedingItem {
  id: string;
  name: string;
  category: string;
  location: string;
  description: string;
  mention_guide: string;
  status: string;
}

export default function SeedingManagerScreen() {
  const [items, setItems] = useState<SeedingItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Form states
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("restaurant");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const [mentionGuide, setMentionGuide] = useState("");

  useEffect(() => {
    fetchSeedingItems();
  }, []);

  const fetchSeedingItems = async () => {
    setLoading(true);
    setErrorMsg("");
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    try {
      let resStr = "";
      if (isTauri) {
        resStr = await invoke<string>("get_seeding");
      } else {
        // Fallback for browser mode
        resStr = JSON.stringify({
          success: true,
          data: [
            { id: "s-mock-1", name: "Cơm gà Bà Buội", category: "restaurant", location: "Hội An", description: "Cơm gà gia truyền nổi tiếng phố cổ", mention_guide: "Gợi ý quán ăn trưa", status: "active" },
            { id: "s-mock-2", name: "Mỳ Quảng Bà Mua", category: "restaurant", location: "Đà Nẵng", description: "Đặc sản mỳ quảng ếch Đà Nẵng", mention_guide: "Gợi ý ghé ăn trưa tiếp năng lượng", status: "active" },
            { id: "s-mock-3", name: "Resort InterContinental", category: "hotel", location: "Đà Nẵng", description: "Khu nghỉ dưỡng 5 sao sang trọng", mention_guide: "Gợi ý địa điểm nghỉ ngơi cao cấp", status: "active" }
          ]
        });
      }
      const res = JSON.parse(resStr);
      if (res.success && Array.isArray(res.data)) {
        setItems(res.data);
      } else {
        setErrorMsg(res.data || "Không thể tải danh sách seeding.");
      }
    } catch (err: any) {
      setErrorMsg(err.toString());
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSeeding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !location.trim()) {
      setErrorMsg("Vui lòng nhập tên địa điểm và khu vực.");
      return;
    }

    setLoading(true);
    setErrorMsg("");
    setSuccessMsg("");

    const payload = {
      id: editingId || undefined,
      name,
      category,
      location,
      description,
      mention_guide: mentionGuide,
      status: "active",
    };

    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    try {
      let resStr = "";
      if (isTauri) {
        resStr = await invoke<string>("save_seeding", { seedingJson: JSON.stringify(payload) });
      } else {
        // Mock save
        resStr = JSON.stringify({ success: true, data: "saved" });
      }
      const res = JSON.parse(resStr);
      if (res.success) {
        setSuccessMsg(editingId ? "Cập nhật thành công!" : "Thêm mới thành công!");
        resetForm();
        fetchSeedingItems();
        setTimeout(() => setSuccessMsg(""), 3000);
      } else {
        setErrorMsg(res.data || "Lưu thất bại.");
      }
    } catch (err: any) {
      setErrorMsg(err.toString());
    } finally {
      setLoading(false);
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
    setLoading(true);
    setErrorMsg("");
    setSuccessMsg("");
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    try {
      let resStr = "";
      if (isTauri) {
        resStr = await invoke<string>("delete_seeding", { id });
      } else {
        // Mock delete
        resStr = JSON.stringify({ success: true, data: "deleted" });
      }
      const res = JSON.parse(resStr);
      if (res.success) {
        setSuccessMsg("Đã xóa địa điểm seeding.");
        fetchSeedingItems();
        setTimeout(() => setSuccessMsg(""), 3000);
      } else {
        setErrorMsg(res.data || "Xóa thất bại.");
      }
    } catch (err: any) {
      setErrorMsg(err.toString());
    } finally {
      setLoading(false);
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
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>📍 Quản lý Seeding Địa Điểm</h1>
        <p style={styles.subtitle}>Thiết lập danh sách các nhà hàng, quán ăn, khách sạn để AI tự động lồng ghép tinh tế vào kịch bản.</p>
      </header>

      {errorMsg && <div style={styles.errorAlert}>⚠ {errorMsg}</div>}
      {successMsg && <div style={styles.successAlert}>✓ {successMsg}</div>}

      <div style={styles.layout}>
        {/* Form panel */}
        <div style={styles.glassPanel}>
          <h2 style={styles.panelTitle}>{editingId ? "📝 Chỉnh sửa Seeding" : "➕ Thêm địa điểm Seeding"}</h2>
          
          <form onSubmit={handleSaveSeeding} style={styles.form}>
            <div style={styles.formGroup}>
              <label style={styles.label}>Tên địa điểm <span style={styles.required}>*</span></label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="VD: Mỳ Quảng Bà Mua, Khách sạn Melia..."
                style={styles.input}
                required
              />
            </div>

            <div style={styles.formRow}>
              <div style={{ ...styles.formGroup, flex: 1 }}>
                <label style={styles.label}>Phân loại</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  style={styles.select}
                >
                  <option style={styles.option} value="restaurant">🍜 Nhà hàng / Quán ăn</option>
                  <option style={styles.option} value="hotel">🏨 Khách sạn / Resort</option>
                  <option style={styles.option} value="sightseeing">🏔️ Điểm tham quan</option>
                  <option style={styles.option} value="other">🏕️ Khác</option>
                </select>
              </div>

              <div style={{ ...styles.formGroup, flex: 1 }}>
                <label style={styles.label}>Khu vực / Tỉnh thành <span style={styles.required}>*</span></label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="VD: Đà Nẵng, Phú Quốc..."
                  style={styles.input}
                  required
                />
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>Mô tả ngắn gọn</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Mô tả đặc trưng nổi bật (món ăn ngon nhất, view đẹp nhất)..."
                style={styles.textarea}
              />
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>Hướng dẫn cách lồng ghép (Mention Guide)</label>
              <input
                type="text"
                value={mentionGuide}
                onChange={(e) => setMentionGuide(e.target.value)}
                placeholder="VD: Gợi ý làm nơi ăn sáng tuyệt vời, Resort nghỉ dưỡng đẳng cấp..."
                style={styles.input}
              />
            </div>

            <div style={styles.formActions}>
              {editingId && (
                <button type="button" onClick={resetForm} style={styles.cancelBtn}>
                  Huỷ bỏ
                </button>
              )}
              <button type="submit" disabled={loading} style={styles.submitBtn}>
                {loading ? "Đang lưu..." : editingId ? "💾 Cập nhật" : "➕ Thêm seeding"}
              </button>
            </div>
          </form>
        </div>

        {/* List panel */}
        <div style={styles.glassPanel}>
          <h2 style={styles.panelTitle}>📋 Danh sách địa điểm ({items.length})</h2>
          
          <div style={styles.listContainer}>
            {items.map((item) => (
              <div key={item.id} style={styles.itemCard}>
                <div style={styles.itemHeader}>
                  <div style={styles.itemTitleRow}>
                    <span style={styles.itemCategoryIcon}>
                      {item.category === "restaurant" ? "🍜" : item.category === "hotel" ? "🏨" : "🏔️"}
                    </span>
                    <span style={styles.itemName}>{item.name}</span>
                    <span style={styles.itemTag}>{item.location}</span>
                  </div>
                  
                  <div style={styles.itemActions}>
                    <button onClick={() => handleEdit(item)} style={styles.actionEditBtn} title="Sửa">✏️</button>
                    <button onClick={() => handleDelete(item.id)} style={styles.actionDeleteBtn} title="Xoá">🗑️</button>
                  </div>
                </div>

                <p style={styles.itemDesc}>{item.description || "Chưa có mô tả."}</p>
                {item.mention_guide && (
                  <div style={styles.itemGuide}>
                    <strong>💡 Gợi ý lồng ghép: </strong> {item.mention_guide}
                  </div>
                )}
              </div>
            ))}

            {items.length === 0 && (
              <div style={styles.emptyState}>Chưa có địa điểm seeding nào được thiết lập. Hãy thêm địa điểm ở khung bên trái.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    padding: 24,
    color: "#f3f4f6",
    fontFamily: "Inter, sans-serif",
    height: "100%",
    overflowY: "auto" as const,
  },
  header: {
    marginBottom: 24,
  },
  title: {
    fontSize: 26,
    fontWeight: 700,
    color: "#ffffff",
    margin: 0,
  },
  subtitle: {
    fontSize: 14,
    color: "#9ca3af",
    marginTop: 6,
    lineHeight: 1.5,
  },
  layout: {
    display: "grid",
    gridTemplateColumns: "1fr 1.2fr",
    gap: 24,
    alignItems: "flex-start",
  },
  glassPanel: {
    backgroundColor: "rgba(17, 12, 46, 0.4)",
    backdropFilter: "blur(16px)",
    borderRadius: 16,
    padding: 24,
    border: "1px solid rgba(255, 255, 255, 0.06)",
    boxShadow: "0 8px 32px 0 rgba(0, 0, 0, 0.3)",
  },
  panelTitle: {
    fontSize: 17,
    fontWeight: 600,
    color: "#ffffff",
    margin: "0 0 20px 0",
  },
  form: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 16,
  },
  formRow: {
    display: "flex",
    gap: 16,
  },
  formGroup: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 6,
  },
  label: {
    fontSize: 13,
    fontWeight: 500,
    color: "#d1d5db",
  },
  required: {
    color: "#ef4444",
  },
  input: {
    backgroundColor: "rgba(255, 255, 255, 0.04)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    borderRadius: 8,
    color: "#ffffff",
    fontSize: 13,
    padding: "10px 14px",
    outline: "none",
    width: "100%",
  },
  select: {
    backgroundColor: "#161233",
    border: "1px solid rgba(255, 255, 255, 0.15)",
    borderRadius: 8,
    color: "#ffffff",
    fontSize: 13,
    padding: "10px 14px",
    outline: "none",
  },
  option: {
    backgroundColor: "#161233",
    color: "#ffffff",
  },
  textarea: {
    backgroundColor: "rgba(255, 255, 255, 0.04)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    borderRadius: 8,
    color: "#ffffff",
    fontSize: 13,
    padding: "10px 14px",
    outline: "none",
    minHeight: 80,
    resize: "vertical" as const,
    fontFamily: "Inter, sans-serif",
  },
  formActions: {
    display: "flex",
    justifyContent: "flex-end",
    gap: 12,
    marginTop: 10,
  },
  submitBtn: {
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    border: "none",
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 600,
    padding: "11px 22px",
    cursor: "pointer",
    transition: "background-color 0.2s",
  },
  cancelBtn: {
    backgroundColor: "transparent",
    color: "#9ca3af",
    border: "1px solid rgba(255, 255, 255, 0.15)",
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 600,
    padding: "11px 22px",
    cursor: "pointer",
  },
  listContainer: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 16,
    maxHeight: 520,
    overflowY: "auto" as const,
    paddingRight: 6,
  },
  itemCard: {
    backgroundColor: "rgba(255, 255, 255, 0.02)",
    border: "1px solid rgba(255, 255, 255, 0.05)",
    borderRadius: 12,
    padding: 16,
    transition: "transform 0.15s, border-color 0.15s",
  },
  itemHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  itemTitleRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  itemCategoryIcon: {
    fontSize: 16,
  },
  itemName: {
    fontSize: 14.5,
    fontWeight: 600,
    color: "#ffffff",
  },
  itemTag: {
    fontSize: 10.5,
    fontWeight: 600,
    background: "rgba(124, 58, 237, 0.15)",
    border: "1px solid rgba(124, 58, 237, 0.3)",
    color: "#a78bfa",
    borderRadius: 12,
    padding: "2px 8px",
    textTransform: "uppercase" as const,
  },
  itemActions: {
    display: "flex",
    gap: 8,
  },
  actionEditBtn: {
    background: "none",
    border: "none",
    cursor: "pointer",
    fontSize: 13,
    padding: 4,
  },
  actionDeleteBtn: {
    background: "none",
    border: "none",
    cursor: "pointer",
    fontSize: 13,
    padding: 4,
  },
  itemDesc: {
    fontSize: 13,
    color: "#d1d5db",
    margin: "0 0 10px 0",
    lineHeight: 1.5,
  },
  itemGuide: {
    fontSize: 11.5,
    color: "#a78bfa",
    background: "rgba(124, 58, 237, 0.05)",
    borderRadius: 6,
    padding: "8px 10px",
    lineHeight: 1.4,
  },
  emptyState: {
    fontSize: 13,
    color: "#9ca3af",
    textAlign: "center" as const,
    padding: "40px 20px",
    border: "1px dashed rgba(255, 255, 255, 0.08)",
    borderRadius: 12,
  },
  errorAlert: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    border: "1px solid #ef4444",
    borderRadius: 8,
    color: "#fca5a5",
    fontSize: 13,
    padding: 12,
    marginBottom: 18,
  },
  successAlert: {
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    border: "1px solid #10b981",
    borderRadius: 8,
    color: "#6ee7b7",
    fontSize: 13,
    padding: 12,
    marginBottom: 18,
  }
};
