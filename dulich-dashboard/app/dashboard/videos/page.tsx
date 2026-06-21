"use client";

import { useEffect, useState } from "react";
import {
  Film,
  Clock,
  CheckCircle2,
  Send,
  Loader2,
  Eye,
  FileText,
  Type,
  XCircle,
  ExternalLink,
  Share2,
} from "lucide-react";

interface VideoItem {
  id: string;
  name: string;
  creator: string;
  status: "Đang render" | "Chờ duyệt" | "Đã duyệt" | "Đã đăng" | "Từ chối";
  date: string;
  topic: string;
  script: {
    hook: string;
    body: string;
    cta: string;
  };
  captions: {
    hooks: string[];
    caption_short: string;
    caption_long: string;
    hashtags: string[];
  };
  videoPath: string;
  driveUrl: string;
  localPath: string;
}

export default function VideosPage() {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedVideo, setSelectedVideo] = useState<VideoItem | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [publishingId, setPublishingId] = useState<string | null>(null);

  const fetchVideos = async () => {
    try {
      const res = await fetch("/api/videos");
      const data = await res.json();
      if (data.success) {
        setVideos(data.data);
        // Default select the first one if none selected
        if (data.data.length > 0 && !selectedVideo) {
          setSelectedVideo(data.data[0]);
        }
      }
    } catch (err) {
      console.error("Lỗi khi load danh sách video:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVideos();
  }, []);

  const handleUpdateStatus = async (id: string, newStatus: VideoItem["status"]) => {
    setUpdatingId(id);
    try {
      const res = await fetch(`/api/videos/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      const data = await res.json();
      if (data.success) {
        // Update local state
        setVideos((prev) =>
          prev.map((v) => (v.id === id ? { ...v, status: newStatus } : v))
        );
        if (selectedVideo?.id === id) {
          setSelectedVideo((prev) => (prev ? { ...prev, status: newStatus } : null));
        }
      } else {
        alert(data.error || "Không thể cập nhật trạng thái");
      }
    } catch (err) {
      alert("Đã xảy ra lỗi kết nối");
    } finally {
      setUpdatingId(null);
    }
  };

  const handlePublishToSocial = async (id: string, platform: "tiktok" | "facebook") => {
    setPublishingId(id);
    try {
      const res = await fetch("/api/publish-social", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, platform }),
      });
      const data = await res.json();
      if (data.success) {
        alert(`Đăng bài lên ${platform === "tiktok" ? "TikTok" : "Facebook"} thành công!\nLink: ${data.postUrl || "N/A"}`);
        // Update status to published
        await handleUpdateStatus(id, "Đã đăng");
      } else {
        alert(data.error || `Không thể đăng bài lên ${platform}`);
      }
    } catch (err) {
      alert("Đã xảy ra lỗi khi đăng bài");
    } finally {
      setPublishingId(null);
    }
  };

  const getStatusBadge = (status: VideoItem["status"]) => {
    switch (status) {
      case "Đang render":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Loader2 className="animate-spin" size={12} />
            Đang render
          </span>
        );
      case "Chờ duyệt":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
            <Clock size={12} />
            Chờ duyệt
          </span>
        );
      case "Đã duyệt":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
            <CheckCircle2 size={12} />
            Đã duyệt
          </span>
        );
      case "Đã đăng":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Send size={12} />
            Đã đăng
          </span>
        );
      case "Từ chối":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
            <XCircle size={12} />
            Từ chối
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="p-8 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white mb-2">Quản lý Video & Bài viết</h1>
        <p className="text-sm text-gray-500">
          Danh sách video từ dulich-pipeline — Duyệt và đăng bài lên TikTok/Facebook
        </p>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 bg-[#161616] rounded-xl border border-[#333]">
          <Loader2 className="animate-spin text-purple-500 mb-3" size={32} />
          <p className="text-gray-400 text-sm">Đang tải danh sách video...</p>
        </div>
      ) : videos.length === 0 ? (
        <div className="bg-[#1a1a1a] rounded-xl border border-[#333] p-16 text-center">
          <Film className="mx-auto mb-4 text-gray-600" size={48} />
          <h3 className="text-white font-medium mb-1">Chưa có video nào</h3>
          <p className="text-gray-500 text-sm mb-6">
            Hãy tạo video từ dulich-pipeline và bấm &quot;Đăng lên Dashboard&quot;!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          {/* LEFT TABLE (3 cols) */}
          <div className="lg:col-span-3 space-y-4">
            <div className="bg-[#1a1a1a] rounded-xl border border-[#333] overflow-hidden">
              <div className="px-6 py-4 border-b border-[#333] flex justify-between items-center bg-[#1e1e1e]">
                <h2 className="text-sm font-semibold text-white">Danh sách nội dung ({videos.length})</h2>
                <button
                  onClick={fetchVideos}
                  className="text-xs text-purple-400 hover:text-purple-300 font-medium flex items-center gap-1 transition"
                >
                  🔄 Làm mới
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-gray-500 text-xs font-medium uppercase tracking-wider border-b border-[#333] bg-[#151515]">
                      <th className="px-6 py-4">Chủ đề / Tên Video</th>
                      <th className="px-6 py-4">Creator</th>
                      <th className="px-6 py-4">Ngày tạo</th>
                      <th className="px-6 py-4">Trạng thái</th>
                      <th className="px-6 py-4 text-right">Hành động</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#222]">
                    {videos.map((video) => (
                      <tr
                        key={video.id}
                        onClick={() => setSelectedVideo(video)}
                        className={`hover:bg-[#222]/50 cursor-pointer transition ${
                          selectedVideo?.id === video.id ? "bg-[#2d213f]/30 border-l-2 border-purple-500" : ""
                        }`}
                      >
                        <td className="px-6 py-4">
                          <div className="font-medium text-white">{video.name}</div>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-300">
                          <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-full bg-blue-600/20 text-blue-400 flex items-center justify-center text-xs font-bold">
                              {video.creator.slice(0, 2).toUpperCase()}
                            </div>
                            {video.creator}
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400">{video.date}</td>
                        <td className="px-6 py-4">{getStatusBadge(video.status)}</td>
                        <td className="px-6 py-4 text-right text-sm" onClick={(e) => e.stopPropagation()}>
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={() => setSelectedVideo(video)}
                              className="p-1.5 text-gray-400 hover:text-white hover:bg-[#333] rounded-lg transition"
                              title="Xem chi tiết"
                            >
                              <Eye size={16} />
                            </button>

                            {video.status === "Chờ duyệt" && (
                              <>
                                <button
                                  onClick={() => handleUpdateStatus(video.id, "Đã duyệt")}
                                  disabled={updatingId === video.id}
                                  className="px-2.5 py-1 text-xs bg-green-600 hover:bg-green-500 text-white font-medium rounded-lg transition disabled:opacity-50"
                                >
                                  Duyệt
                                </button>
                                <button
                                  onClick={() => handleUpdateStatus(video.id, "Từ chối")}
                                  disabled={updatingId === video.id}
                                  className="px-2.5 py-1 text-xs bg-red-600/50 hover:bg-red-500 text-white font-medium rounded-lg transition disabled:opacity-50"
                                >
                                  Từ chối
                                </button>
                              </>
                            )}

                            {video.status === "Đã duyệt" && (
                              <div className="flex gap-1">
                                <button
                                  onClick={() => handlePublishToSocial(video.id, "tiktok")}
                                  disabled={publishingId === video.id}
                                  className="px-2.5 py-1 text-xs bg-black hover:bg-gray-800 text-white font-medium rounded-lg transition disabled:opacity-50 flex items-center gap-1"
                                >
                                  {publishingId === video.id ? (
                                    <Loader2 className="animate-spin" size={12} />
                                  ) : (
                                    <Share2 size={12} />
                                  )}
                                  TikTok
                                </button>
                                <button
                                  onClick={() => handlePublishToSocial(video.id, "facebook")}
                                  disabled={publishingId === video.id}
                                  className="px-2.5 py-1 text-xs bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition disabled:opacity-50 flex items-center gap-1"
                                >
                                  {publishingId === video.id ? (
                                    <Loader2 className="animate-spin" size={12} />
                                  ) : (
                                    <Share2 size={12} />
                                  )}
                                  Facebook
                                </button>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* RIGHT DETAIL PREVIEW (2 cols) */}
          <div className="lg:col-span-2">
            {selectedVideo ? (
              <div className="bg-[#1a1a1a] rounded-xl border border-[#333] overflow-hidden sticky top-8">
                {/* Title Section */}
                <div className="p-6 border-b border-[#333] bg-[#1e1e1e] flex justify-between items-start">
                  <div>
                    <span className="text-xs font-medium text-purple-400 uppercase tracking-wider">
                      Chi tiết nội dung
                    </span>
                    <h2 className="text-lg font-bold text-white mt-1">{selectedVideo.name}</h2>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Tạo ngày {selectedVideo.date} • {selectedVideo.creator}
                    </p>
                  </div>
                  <div>{getStatusBadge(selectedVideo.status)}</div>
                </div>

                <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
                  {/* Video Preview */}
                  {(selectedVideo.videoPath || selectedVideo.driveUrl) && (
                    <div className="space-y-3">
                      <h3 className="text-sm font-semibold text-white flex items-center gap-2 border-b border-[#333] pb-2">
                        <Film size={16} className="text-purple-400" />
                        Video Preview
                      </h3>
                      <div className="bg-[#111] p-4 rounded-lg border border-[#222]">
                        <video
                          src={selectedVideo.driveUrl || selectedVideo.videoPath}
                          controls
                          className="w-full rounded-lg"
                          style={{ maxHeight: "400px" }}
                        />
                        <div className="mt-2 flex gap-2">
                          <a
                            href={selectedVideo.driveUrl || selectedVideo.videoPath}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                          >
                            <ExternalLink size={12} />
                            Mở trong tab mới
                          </a>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Script Details */}
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-white flex items-center gap-2 border-b border-[#333] pb-2">
                      <FileText size={16} className="text-blue-400" />
                      Kịch bản video
                    </h3>
                    <div className="space-y-3 bg-[#111] p-4 rounded-lg border border-[#222]">
                      <div>
                        <div className="text-[10px] font-bold text-purple-400 uppercase">Hook</div>
                        <p className="text-sm text-white mt-1">{selectedVideo.script.hook}</p>
                      </div>
                      <div className="border-t border-[#222] pt-2 mt-2">
                        <div className="text-[10px] font-bold text-blue-400 uppercase">Body</div>
                        <p className="text-sm text-gray-300 mt-1 whitespace-pre-line">
                          {selectedVideo.script.body}
                        </p>
                      </div>
                      <div className="border-t border-[#222] pt-2 mt-2">
                        <div className="text-[10px] font-bold text-green-400 uppercase">CTA</div>
                        <p className="text-sm text-white mt-1">{selectedVideo.script.cta}</p>
                      </div>
                    </div>
                  </div>

                  {/* Caption & Hashtag Details */}
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-white flex items-center gap-2 border-b border-[#333] pb-2">
                      <Type size={16} className="text-green-400" />
                      Caption Đăng Tải
                    </h3>
                    <div className="space-y-3 bg-[#111] p-4 rounded-lg border border-[#222]">
                      <div>
                        <div className="text-xs text-gray-500 font-medium">Caption ngắn:</div>
                        <p className="text-sm text-gray-200 mt-1 bg-[#181818] p-2.5 rounded border border-[#222]">
                          {selectedVideo.captions.caption_short}
                        </p>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500 font-medium">Caption chi tiết:</div>
                        <p className="text-sm text-gray-200 mt-1 bg-[#181818] p-2.5 rounded border border-[#222] whitespace-pre-line">
                          {selectedVideo.captions.caption_long}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Quick Action in detail */}
                  <div className="border-t border-[#333] pt-4 mt-2 flex gap-3">
                    {selectedVideo.status === "Chờ duyệt" && (
                      <>
                        <button
                          onClick={() => handleUpdateStatus(selectedVideo.id, "Đã duyệt")}
                          disabled={updatingId === selectedVideo.id}
                          className="flex-1 py-2.5 bg-green-600 hover:bg-green-500 text-white font-medium rounded-xl text-sm transition"
                        >
                          Duyệt video
                        </button>
                        <button
                          onClick={() => handleUpdateStatus(selectedVideo.id, "Từ chối")}
                          disabled={updatingId === selectedVideo.id}
                          className="flex-1 py-2.5 bg-red-600/50 hover:bg-red-500 text-white font-medium rounded-xl text-sm transition"
                        >
                          Từ chối
                        </button>
                      </>
                    )}
                    {selectedVideo.status === "Đã duyệt" && (
                      <div className="flex gap-2 w-full">
                        <button
                          onClick={() => handlePublishToSocial(selectedVideo.id, "tiktok")}
                          disabled={publishingId === selectedVideo.id}
                          className="flex-1 py-2.5 bg-black hover:bg-gray-800 text-white font-medium rounded-xl text-sm transition flex items-center justify-center gap-2"
                        >
                          <Share2 size={16} />
                          Đăng lên TikTok
                        </button>
                        <button
                          onClick={() => handlePublishToSocial(selectedVideo.id, "facebook")}
                          disabled={publishingId === selectedVideo.id}
                          className="flex-1 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl text-sm transition flex items-center justify-center gap-2"
                        >
                          <Share2 size={16} />
                          Đăng lên Facebook
                        </button>
                      </div>
                    )}
                    {selectedVideo.status === "Đã đăng" && (
                      <div className="w-full text-center py-2 bg-purple-500/10 text-purple-400 border border-purple-500/20 text-xs font-semibold rounded-lg">
                        Bài viết đã được đăng lên mạng xã hội!
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-[#1a1a1a] rounded-xl border border-[#333] p-12 text-center text-gray-500 text-sm">
                Chọn một video để xem chi tiết
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
