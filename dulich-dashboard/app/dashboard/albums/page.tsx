"use client";

import { useEffect, useState } from "react";
import { Images, Loader2, Eye, Calendar, User, ExternalLink, X } from "lucide-react";

interface AlbumItem {
  id: string;
  name: string;
  albumName?: string;
  topic: string;
  title: string;
  subtitle: string;
  creator: string;
  date: string;
  status: string;
  photos: { id: string; title: string; path: string; format?: string; source?: string }[];
  images: Record<string, string>;
}

export default function AlbumsPage() {
  const [albums, setAlbums] = useState<AlbumItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAlbum, setSelectedAlbum] = useState<AlbumItem | null>(null);

  useEffect(() => {
    const fetchAlbums = async () => {
      try {
        const res = await fetch("/api/albums");
        const data = await res.json();
        if (data.success) setAlbums(data.data);
      } catch (err) {
        console.error("Lỗi khi load albums:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchAlbums();
  }, []);

  return (
    <div className="p-8 max-w-[1400px] mx-auto text-gray-200">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Images size={24} className="text-purple-400" />
          Album Ảnh Seeding
        </h1>
        <p className="text-sm text-gray-500 mt-2">
          Danh sách album được tạo từ ứng dụng Desktop. Mở DuLichApp Desktop để tạo album mới.
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
            const photoCount = album.photos?.length || 0;
            const coverPhoto = album.photos?.[0];
            return (
              <div
                key={album.id}
                onClick={() => setSelectedAlbum(album)}
                className="bg-[#1a1a1a] rounded-xl border border-[#333] hover:border-purple-500/30 overflow-hidden cursor-pointer transition flex flex-col justify-between group"
              >
                <div className="aspect-square bg-gradient-to-tr from-indigo-900 to-purple-900 relative overflow-hidden flex items-center justify-center text-center p-4">
                  {coverPhoto && coverPhoto.path && coverPhoto.path.startsWith("data:") ? (
                    <img src={coverPhoto.path} alt={album.name} className="w-full h-full object-cover group-hover:scale-105 transition duration-300" />
                  ) : coverPhoto && coverPhoto.path && coverPhoto.path.startsWith("http") ? (
                    <img src={coverPhoto.path} alt={album.name} className="w-full h-full object-cover group-hover:scale-105 transition duration-300" />
                  ) : (
                    <div className="absolute inset-0 bg-gradient-to-br from-purple-600/20 to-blue-600/20 flex flex-col items-center justify-center p-6">
                      <Images size={32} className="text-purple-400 mb-2 opacity-60" />
                      <span className="text-[10px] text-purple-400 uppercase tracking-widest font-bold">Album Seeding</span>
                      <h4 className="text-sm font-bold text-white mt-2 truncate w-full">{album.albumName || album.name}</h4>
                    </div>
                  )}
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
                    <span className="px-3 py-1.5 bg-purple-600 text-white rounded-lg text-xs font-semibold flex items-center gap-1">
                      <Eye size={12} /> Xem chi tiết
                    </span>
                  </div>
                  <div className="absolute top-2 right-2 bg-black/60 backdrop-blur-sm text-white text-[10px] font-bold px-2 py-1 rounded-full">
                    {photoCount} ảnh
                  </div>
                </div>

                <div className="p-4 space-y-2">
                  <div className="flex justify-between items-start">
                    <h3 className="text-sm font-semibold text-white truncate flex-1 pr-2">{album.albumName || album.name}</h3>
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

      {/* MODAL XEM CHI TIẾT */}
      {selectedAlbum && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#161616] border border-[#333] rounded-2xl w-full max-w-4xl h-[80vh] flex flex-col overflow-hidden relative">
            <button
              onClick={() => setSelectedAlbum(null)}
              className="absolute top-4 right-4 p-2 bg-[#222] hover:bg-[#333] text-gray-400 hover:text-white rounded-full transition z-10"
            >
              <X size={16} />
            </button>

            <div className="p-6 border-b border-[#222]">
              <h2 className="text-lg font-bold text-white">{selectedAlbum.albumName || selectedAlbum.name}</h2>
              <p className="text-xs text-gray-400 mt-1">
                {selectedAlbum.topic} • {selectedAlbum.creator} • {selectedAlbum.date}
              </p>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {selectedAlbum.photos && selectedAlbum.photos.length > 0 ? (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {selectedAlbum.photos.map((photo) => (
                    <div key={photo.id} className="bg-[#1a1a1a] border border-[#222] rounded-xl overflow-hidden">
                      <div className="aspect-square bg-gradient-to-br from-indigo-900/30 to-purple-900/30 flex items-center justify-center">
                        {photo.path && photo.path.startsWith("data:") ? (
                          <img src={photo.path} alt={photo.title} className="w-full h-full object-cover" />
                        ) : photo.path && photo.path.startsWith("http") ? (
                          <img src={photo.path} alt={photo.title} className="w-full h-full object-cover" />
                        ) : (
                          <Images size={24} className="text-gray-600" />
                        )}
                      </div>
                      <div className="p-3">
                        <p className="text-xs font-medium text-white truncate">{photo.title}</p>
                        {photo.source && (
                          <span className={`inline-block mt-1 text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                            photo.source === "seeding" ? "bg-pink-500/15 text-pink-400" : "bg-blue-500/15 text-blue-400"
                          }`}>
                            {photo.source}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-16">
                  <Images className="mx-auto mb-3 text-gray-600" size={40} />
                  <p className="text-sm text-gray-500">Album này chưa có ảnh nào.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
