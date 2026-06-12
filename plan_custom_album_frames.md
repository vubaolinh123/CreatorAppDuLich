## Part 9: Canvas Integration — fabric.js Interactive Editor

### 9.1 Tại sao cần Canvas?

User yêu cầu thao tác trực tiếp với Canvas để:
1. **Đọc ảnh từ canvas** — click chọn ảnh trên canvas, xem thông tin (kích thước, vị trí)
2. **Đọc element trên canvas** — chọn text, shape, logo, xem thuộc tính (font, màu, nội dung)
3. **Chỉnh sửa element** — kéo thả, resize, đổi màu, sửa text, xóa/thêm element

Hiện tại `AlbumScreen.tsx` chỉ hiển thị ảnh output static (file JPG), không có canvas editor.

### 9.2 fabric.js Integration

Module mới: `dulich-desktop/src/components/canvas/FrameCanvas.tsx`

```typescript
import { fabric } from "fabric";

// Canvas state = JSON string → có thể lưu, gửi AI, restore
interface CanvasState {
  version: string;
  objects: CanvasObject[];
  background: string;
  width: number;
  height: number;
}

// Mỗi object trên canvas có type riêng
type CanvasObject = 
  | TextObject      // "Chữ: nội dung, font, size, màu, góc"
  | ImageObject     // "Ảnh: source, crop, filter"
  | ShapeObject     // "Hình: rect, circle, line, polygon"
  | GroupObject;    // "Nhóm các object"
```

**Luồng tương tác:**
```
1. User upload Canva PNG → AI phân tích → tái tạo thành canvas objects
2. User thấy canvas với các layer: ảnh nền, khung viền, text, logo
3. User click chọn text → sửa nội dung, font, màu
4. User kéo thả ảnh → resize, reposition
5. User click "Xuất Album" → canvas → 10 format images
```

### 9.3 AI + Canvas Interaction

AI không chỉ phân tích ảnh PNG tĩnh, mà cần hiểu và thao tác được canvas state:

```typescript
// Canvas state gửi lên AI
const canvasJson = canvas.toJSON([
  "id", "name", "type", "fontFamily", "fontSize", 
  "fill", "stroke", "opacity", "clipPath"
]);

// AI response: instructions để modify canvas
interface AICanvasEdit {
  operations: [
    { type: "modify_text", objectId: "title_1", newContent: "PHÚ QUỐC", fontSize: 72, color: "#ffcc00" },
    { type: "replace_image", objectId: "bg_1", source: "pexels://phu-quoc-beach-123" },
    { type: "resize", objectId: "logo_1", scaleX: 1.2, scaleY: 1.2 },
    { type: "add_element", element: { type: "text", content: "#travel", x: 100, y: 1800, fontSize: 24 } },
    { type: "remove_element", objectId: "old_hashtag" },
  ]
}
```

**Chi tiết luồng:**

```
┌────────────────────────────────────────────────────────────────────┐
│                    AI + Canvas Workflow                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. User uploads Canva PNG                                          │
│     │                                                               │
│     ▼                                                               │
│  2. Frame Analyzer (Pass 1 + 2) → JSON metadata                     │
│     │                                                               │
│     ▼                                                               │
│  3. Canvas Builder tái tạo từ metadata:                              │
│     ├─ fabric.Rect cho border                                        │
│     ├─ fabric.Text cho title/subtitle placeholder                    │
│     ├─ fabric.Image cho logo/decorations                             │
│     └─ fabric.Rect (transparent fill) cho image area (placeholder)  │
│     │                                                               │
│     ▼                                                               │
│  4. User thấy canvas → có thể:                                      │
│     ├─ Click chọn text → sửa nội dung trực tiếp                     │
│     ├─ Kéo thả ảnh vào vùng transparent                             │
│     ├─ resize, xoay, đổi màu các element                            │
│     └─ Thêm/xóa element tùy thích                                    │
│     │                                                               │
│     ▼                                                               │
│  5. Khi user bấm "Sinh Album":                                       │
│     ├─ Canvas → JSON (toJSON)                                        │
│     ├─ AI gợi ý chỉnh sửa nếu cần (auto-fit text, crop ảnh)        │
│     ├─ Canvas → PNG (canvas.toDataURL) → image_composer export      │
│     └─ Lưu canvas state để sau có thể edit lại                       │
│     │                                                               │
│     ▼                                                               │
│  6. Sau này user mở lại: restore từ canvas JSON → tiếp tục edit    │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

### 9.4 fabric.js Canvas Editor UI

```tsx
// FrameCanvas.tsx — Component chính
export default function FrameCanvas({ 
  frameMetadata,  // từ Vision AI analysis
  onExport,
  formatName,     // "story" | "feed_square" | ...
}: Props) {
  const canvasRef = useRef<fabric.Canvas>(null);
  const [objects, setObjects] = useState<fabric.Object[]>([]);
  const [selectedObject, setSelectedObject] = useState<fabric.Object | null>(null);

  useEffect(() => {
    const canvas = new fabric.Canvas(canvasRef.current, {
      width: FORMATS[formatName].width,
      height: FORMATS[formatName].height,
      backgroundColor: "#1e1b4b",
      preserveObjectStacking: true,
    });
    
    // Load elements from AI analysis
    loadFrameToCanvas(canvas, frameMetadata);
    
    // Event: click chọn element → hiện properties panel
    canvas.on("selection:created", (e) => setSelectedObject(e.selected?.[0]));
    canvas.on("selection:updated", (e) => setSelectedObject(e.selected?.[0]));
    canvas.on("selection:cleared", () => setSelectedObject(null));
    
    canvasRef.current = canvas;
    return () => canvas.dispose();
  }, [frameMetadata]);

  return (
    <div style={styles.editorLayout}>
      {/* Canvas chính */}
      <div style={styles.canvasArea}>
        <canvas ref={canvasRef} />
      </div>
      
      {/* Properties Panel */}
      <div style={styles.propertiesPanel}>
        {selectedObject ? (
          <ObjectEditor object={selectedObject} canvas={canvasRef.current} />
        ) : (
          <EmptyState text="Click chọn element để chỉnh sửa" />
        )}
      </div>
      
      {/* Layer Panel */}
      <div style={styles.layerPanel}>
        <LayerList canvas={canvasRef.current} />
      </div>
    </div>
  );
}
```

### 9.5 Object Properties Editor

Khi user chọn 1 element trên canvas, properties panel hiện ra:

| Object Type | Có thể chỉnh sửa |
|-------------|------------------|
| **Text** | Nội dung, font (dropdown), size, màu chữ, bold/italic, align, letter-spacing, line-height, shadow, opacity, rotate |
| **Image** | Replace image (click chọn file mới), scale, crop, flip, filter (grayscale, sepia, brightness), opacity |
| **Shape** | Fill color, stroke, strokeWidth, rx/ry (bo góc), opacity, rotate |
| **Group** | Scale đồng bộ, ungroup để edit từng phần tử |

```tsx
// ObjectEditor.tsx — Dynamic properties based on object type
function ObjectEditor({ object, canvas }: Props) {
  if (object.type === "text" || object.type === "i-text") {
    return <TextEditor text={object as fabric.Text} canvas={canvas} />;
  }
  if (object.type === "image") {
    return <ImageEditor image={object as fabric.Image} canvas={canvas} />;
  }
  if (object.type === "rect" || object.type === "circle") {
    return <ShapeEditor shape={object as fabric.Object} canvas={canvas} />;
  }
  return <GenericEditor object={object} canvas={canvas} />;
}

function TextEditor({ text, canvas }: { text: fabric.Text; canvas: fabric.Canvas }) {
  const [content, setContent] = useState(text.text);
  const [fontSize, setFontSize] = useState(text.fontSize);
  const [color, setColor] = useState(text.fill as string);
  
  const update = () => {
    text.set({ text: content, fontSize, fill: color });
    canvas.renderAll();
  };
  
  return (
    <div>
      <label>Nội dung:</label>
      <input value={content} onChange={e => { setContent(e.target.value); update(); }} />
      <label>Font size:</label>
      <input type="number" value={fontSize} onChange={e => { setFontSize(+e.target.value); update(); }} />
      <label>Màu:</label>
      <input type="color" value={color} onChange={e => { setColor(e.target.value); update(); }} />
    </div>
  );
}
```

### 9.6 AI Canvas Analyzer — Đọc element trên Canvas

Khi user đã chỉnh sửa canvas, AI có thể "đọc" trạng thái canvas để đưa ra gợi ý:

```typescript
// Gửi canvas state lên AI
async function aiSuggestCanvasEdits(canvas: fabric.Canvas): Promise<AICanvasEdit> {
  const state = canvas.toJSON();
  
  // Vision AI đọc canvas để hiểu layout
  const dataUrl = canvas.toDataURL({ format: "png", multiplier: 0.5 });
  
  const response = await fetch("/api/ai/canvas-suggest", {
    method: "POST",
    body: JSON.stringify({
      canvas_state: state,
      canvas_preview: dataUrl, // gửi cả ảnh preview để AI "nhìn"
    }),
  });
  
  return response.json(); // Trả về operations để tự động chỉnh sửa
}
```

**Server-side handler** (`/api/ai/canvas-suggest`):
```python
def handle_canvas_suggest(canvas_state: dict, canvas_preview_b64: str):
    """
    AI nhìn canvas và đưa ra gợi ý:
    - Text có bị tràn? → giảm font size
    - Ảnh bị vỡ aspect ratio? → fix crop
    - Bố cục lệch? → căn lại
    - Thiếu hashtag? → thêm
    """
    prompt = f"""
    You are a graphic design AI assistant.
    Here is the current canvas state as JSON: {json.dumps(canvas_state)}
    And here is the visual preview (base64 image).

    Analyze and suggest edits to make this social media image better.
    Return JSON with operations array.
    """
    
    vision_response = vision_provider.analyze(canvas_preview_b64, prompt)
    return vision_response
```

### 9.7 Canvas → 10 Format Export

Khi user đã ưng canvas, export thành 10 format:

```typescript
async function exportCanvasToAllFormats(canvas: fabric.Canvas): Promise<void> {
  // 1. Lấy canvas state hiện tại
  const currentState = canvas.toJSON();
  
  // 2. Với mỗi format, tạo canvas mới với kích thước khác
  for (const [fmt, { width, height }] of Object.entries(FORMATS)) {
    const tempCanvas = new fabric.Canvas(null, { width, height });
    
    // 3. AI tự động điều chỉnh layout cho format đó
    const adaptedState = await aiAdaptLayout(currentState, fmt, width, height);
    
    // 4. Load lên temp canvas
    tempCanvas.loadFromJSON(adaptedState, () => {
      // 5. Export PNG
      const pngData = tempCanvas.toDataURL({ format: "png", multiplier: 2 });
      
      // 6. Gửi xuống image_composer để thêm hiệu ứng cuối
      // Hoặc nếu canvas đã đủ, save trực tiếp
      saveImage(pngData, `output/albums/album_${fmt}.png`);
    });
  }
}
```

### 9.8 Canvas State Persistence

Lưu canvas state để user có thể quay lại edit sau:

```typescript
// Khi save
const canvasState = canvas.toJSON();
await invoke("save_canvas_state", {
  albumId: jobId,
  formatName: formatName,
  canvasState: JSON.stringify(canvasState),
});

// Khi load
const savedState = await invoke("get_canvas_state", {
  albumId: jobId,
  formatName: formatName,
});
canvas.loadFromJSON(JSON.parse(savedState));
```

**MongoDB schema cho canvas state:**
```javascript
// Collection: canvas_states
{
  "album_id": "job_123",
  "format": "story",
  "creator_id": "lan_anh",
  "canvas_state": { ... },  // fabric.JSON
  "updated_at": "2026-06-11T10:00:00Z",
  "version": 3               // support undo/history
}
```
