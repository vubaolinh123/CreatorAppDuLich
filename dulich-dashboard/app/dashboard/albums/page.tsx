"use client";

import { useEffect, useState } from "react";
import { Images, Loader2, Eye, Calendar, User, ExternalLink, X } from "lucide-react";

interface AlbumItem {
  id: string;
  name: string;
  topic: string;
  title: string;
  subtitle: string;
  templateId: string;
  creator: string;
  date: string;
  status: string;
  images: Record<string, string>;
}

const FORMAT_LABELS: Record<string, string> = {
  story: "Story (1080x1920)",
  feed_square: "Feed Vuông (1080x1080)",
  feed_portrait: "Feed Portrait (1080x1350)",
  reels_cover: "Reels Cover (1080x1920)",
  youtube_thumb: "YouTube Thumb (1280x720)",
  facebook_cover: "Facebook Cover (820x312)",
  pinterest: "Pinterest Pin (1000x1500)",
  carousel_slide: "Carousel (1080x1080)",
  blog_header: "Blog Header (1200x630)",
  seeding_card: "Seeding Card (800x800)",
};

export default function AlbumsPage() {
  const [albums, setAlbums] = useState<AlbumItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAlbum, setSelectedAlbum] = useState<AlbumItem | null>(null);
  const [activeFormat, setActiveFormat] = useState<string | null>(null);

  useEffect(() => {
    const fetchAlbums = async () => {
      try {
        const res = await fetch("/api/albums");
        const data = await res.json();
        if (data.success) {
          setAlbums(data.data);
        }
      } catch (err) {
        console.error("Lỗi khi load albums:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchAlbums();
  }, []);

  const openZoomModal = (album: AlbumItem) => {
    setSelectedAlbum(album);
    const formats = Object.keys(album.images);
    if (formats.length > 0) {
      setActiveFormat(formats[0]);
    } else {
      setActiveFormat(null);
    }
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto text-gray-200">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Images size={24} className="text-purple-400" />
          Album Ảnh Seeding
        </h1>
        <p className="text-sm text-gray-500 mt-2">
          Danh sách album seeding sản xuất hàng loạt với 10 kích thước định dạng khác nhau để đăng bài đa nền tảng.
        </p>
      </header>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 bg-[#161616] rounded-xl border border-[#333]">
          <Loader2 className="animate-spin text-purple-500 mb-3" size={32} />
          <p className="text-gray-400 text-sm">Đang tải danh sách album...</p>
        </div>
      ) : albums.length === 0 ? (
        <div className="bg-[#1a1a1a] rounded-xl border border-[#333] p-16 text-center">
          <Images className="mx-auto mb-4 text-gray-600" size={48} />
          <h3 className="text-white font-medium mb-1">Chưa có album nào</h3>
          <p className="text-gray-500 text-sm">
            Tạo album seeding mới từ ứng dụng Desktop để xem kết quả tại đây!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {albums.map((album) => {
            const formats = Object.keys(album.images);
            const coverFormat = formats.includes("feed_square") ? "feed_square" : formats[0];
            const coverPath = album.images[coverFormat];
            const isLocalPath = coverPath && (coverPath.includes(":\\") || coverPath.includes("/"));
            
            return (
              <div
                key={album.id}
                onClick={() => openZoomModal(album)}
                className="bg-[#1a1a1a] rounded-xl border border-[#333] hover:border-purple-500/30 overflow-hidden cursor-pointer transition flex flex-col justify-between group"
              >
                <div className="aspect-square bg-gradient-to-tr from-indigo-900 to-purple-900 relative overflow-hidden flex items-center justify-center text-center p-4">
                  {!isLocalPath && coverPath ? (
                    <img src={coverPath} alt={album.name} className="w-full h-full object-cover group-hover:scale-105 transition duration-300" />
                  ) : (
                    <div className="absolute inset-0 bg-gradient-to-br from-purple-600/20 to-blue-600/20 flex flex-col items-center justify-center p-6">
                      <Images size={32} className="text-purple-400 mb-2 opacity-60" />
                      <span className="text-[10px] text-purple-400 uppercase tracking-widest font-bold">Album Seeding</span>
                      <h4 className="text-sm font-bold text-white mt-2 truncate w-full">{album.title}</h4>
                      <p className="text-xs text-gray-400 mt-1 line-clamp-2">{album.subtitle}</p>
                    </div>
                  )}
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
                    <span className="px-3 py-1.5 bg-purple-600 text-white rounded-lg text-xs font-semibold flex items-center gap-1">
                      <Eye size={12} /> Xem chi tiết
                    </span>
                  </div>
                </div>

                <div className="p-4 space-y-2">
                  <div className="flex justify-between items-start">
                    <h3 className="text-sm font-semibold text-white truncate flex-1 pr-2">{album.name}</h3>
                    <span className="text-[10px] bg-purple-500/15 text-purple-400 border border-purple-500/10 px-2 py-0.5 rounded uppercase font-bold">
                      {album.topic}
                    </span>
                  </div>
                  
                  <div className="flex justify-between items-center text-xs text-gray-500 border-t border-[#2a2a2a] pt-3 mt-1">
                    <span className="flex items-center gap-1"><User size={12} /> {album.creator}</span>
                    <span className="flex items-center gap-1"><Calendar size={12} /> {album.date}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* OVERLAY DETAILS & ZOOM MODAL */}
      {selectedAlbum && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#161616] border border-[#333] rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden relative">
            <button
              onClick={() => setSelectedAlbum(null)}
              className="absolute top-4 right-4 p-2 bg-[#222] hover:bg-[#333] text-gray-400 hover:text-white rounded-full transition z-10"
            >
              <X size={16} />
            </button>

            {/* Modal Header */}
            <div className="p-6 border-b border-[#222]">
              <h2 className="text-lg font-bold text-white">{selectedAlbum.name}</h2>
              <p className="text-xs text-gray-400 mt-1">
                Khu vực: {selectedAlbum.topic} • Biên tập bởi: {selectedAlbum.creator} • Ngày tạo: {selectedAlbum.date}
              </p>
            </div>

            {/* Modal Content Layout */}
            <div className="flex-1 flex overflow-hidden">
              {/* Left Selector (Formats list) */}
              <div className="w-64 border-r border-[#222] overflow-y-auto p-4 space-y-1">
                <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block mb-3 px-2">Định dạng ảnh</span>
                {Object.keys(selectedAlbum.images).map((fmt) => (
                  <button
                    key={fmt}
                    onClick={() => setActiveFormat(fmt)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition ${
                      activeFormat === fmt
                        ? "bg-purple-600 text-white"
                        : "text-gray-400 hover:text-white hover:bg-[#222]"
                    }`}
                  >
                    {FORMAT_LABELS[fmt] || fmt}
                  </button>
                ))}
              </div>

              {/* Right Showcase (Zoom View) */}
              <div className="flex-1 bg-[#0f0f0f] p-8 flex items-center justify-center overflow-hidden">
                {activeFormat ? (
                  <div className="flex flex-col items-center justify-center max-w-full max-h-full">
                    {selectedAlbum.images[activeFormat].includes(":\\") || selectedAlbum.images[activeFormat].includes("/") ? (
                      <div className="w-[360px] h-[360px] bg-gradient-to-br from-[#1e1b4b] to-[#431407] rounded-2xl border border-purple-500/25 p-8 flex flex-col justify-between shadow-2xl relative">
                        <div className="flex justify-between items-start">
                          <span className="text-[10px] text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded font-bold uppercase tracking-wider">
                            {activeFormat}
                          </span>
                          <span className="text-2xl">🌴</span>
                        </div>
                        
                        <div className="space-y-2">
                          <h1 className="text-2xl font-black text-white leading-tight uppercase bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-300">
                            {selectedAlbum.title}
                          </h1>
                          <p className="text-sm text-gray-300 line-clamp-3 leading-relaxed">
                            {selectedAlbum.subtitle}
                          </p>
                        </div>

                        <div className="flex justify-between items-end border-t border-white/10 pt-4 mt-2">
                          <span className="text-[10px] text-purple-400 font-bold tracking-widest uppercase">
                            #{selectedAlbum.topic.replace(/\s+/g, "")} #dulich
                          </span>
                          <span className="text-[10px] text-gray-500 font-medium">@dulichapp</span>
                        </div>
                      </div>
                    ) : (
                      <img
                        src={selectedAlbum.images[activeFormat]}
                        alt={activeFormat}
                        className="max-w-full max-h-[60vh] object-contain rounded-lg border border-[#333] shadow-xl"
                      />
                    )}
                    <span className="text-xs text-gray-500 mt-4 font-mono truncate w-full text-center">
                      File: {selectedAlbum.images[activeFormat].split("\\").pop()}
                    </span>
                  </div>
                ) : (
                  <div className="text-gray-500 text-xs">Không tìm thấy file hình ảnh.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
