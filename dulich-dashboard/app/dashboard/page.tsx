"use client";

import { useEffect, useState } from "react";
import { Film, CheckCircle, Clock, Loader2, ArrowRight } from "lucide-react";
import Link from "next/link";

interface VideoStats {
  total: number;
  pending: number;
  approved: number;
  published: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<VideoStats>({ total: 0, pending: 0, approved: 0, published: 0 });
  const [recentVideos, setRecentVideos] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch("/api/videos");
        const data = await res.json();
        if (data.success) {
          const videos = data.data;
          
          // Compute stats
          const total = videos.length;
          const pending = videos.filter((v: any) => v.status === "Chờ duyệt").length;
          const approved = videos.filter((v: any) => v.status === "Đã duyệt").length;
          const published = videos.filter((v: any) => v.status === "Đã đăng").length;
          
          setStats({ total, pending, approved, published });
          setRecentVideos(videos.slice(0, 5));
        }
      } catch (err) {
        console.error("Lỗi khi fetch stats:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const statCards = [
    { label: "Tổng video", value: stats.total.toString(), icon: Film, color: "text-blue-400" },
    { label: "Chờ duyệt", value: stats.pending.toString(), icon: Clock, color: "text-yellow-400" },
    { label: "Đã duyệt", value: stats.approved.toString(), icon: CheckCircle, color: "text-green-400" },
    { label: "Đã đăng", value: stats.published.toString(), icon: Loader2, color: "text-purple-400" },
  ];

  return (
    <div className="p-8 max-w-[1200px] mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Tổng quan</h1>
          <p className="text-sm text-gray-500">Quản lý video từ dulich-pipeline</p>
        </div>
        <Link
          href="/dashboard/videos"
          className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-medium px-4 py-2 rounded-xl text-sm transition"
        >
          Quản lý video →
        </Link>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2 className="animate-spin text-purple-500 mb-2" size={32} />
          <p className="text-gray-500 text-sm">Đang tải báo cáo...</p>
        </div>
      ) : (
        <>
          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {statCards.map((stat) => (
              <div key={stat.label} className="bg-[#1a1a1a] rounded-xl p-5 border border-[#333] hover:border-gray-700 transition">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-gray-400 text-sm font-medium">{stat.label}</span>
                  <stat.icon size={20} className={stat.color} />
                </div>
                <p className="text-3xl font-bold text-white">{stat.value}</p>
              </div>
            ))}
          </div>

          {/* Recent videos */}
          <div className="bg-[#1a1a1a] rounded-xl border border-[#333] overflow-hidden">
            <div className="p-5 border-b border-[#333] flex justify-between items-center bg-[#1e1e1e]">
              <h2 className="text-base font-semibold text-white">Video gần đây</h2>
              <Link
                href="/dashboard/videos"
                className="text-xs text-purple-400 hover:text-purple-300 font-medium flex items-center gap-1 transition"
              >
                Xem tất cả <ArrowRight size={12} />
              </Link>
            </div>
            {recentVideos.length === 0 ? (
              <div className="p-12 text-center text-gray-500 text-sm">
                Chưa có video nào. Hãy tạo video từ dulich-pipeline!
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-gray-500 text-xs uppercase border-b border-[#333] bg-[#151515]">
                      <th className="text-left px-6 py-3">Tên video</th>
                      <th className="text-left px-6 py-3">Creator</th>
                      <th className="text-left px-6 py-3">Trạng thái</th>
                      <th className="text-left px-6 py-3">Ngày</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentVideos.map((video) => (
                      <tr key={video.id} className="border-b border-[#222] hover:bg-[#222]/50 transition">
                        <td className="px-6 py-4 text-sm font-medium text-white">{video.name}</td>
                        <td className="px-6 py-4 text-sm text-gray-400">{video.creator}</td>
                        <td className="px-6 py-4">
                          <span className={`text-xs px-2.5 py-1 rounded-full border ${
                            video.status === "Đã duyệt" ? "bg-green-500/10 text-green-400 border-green-500/20" :
                            video.status === "Chờ duyệt" ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/20" :
                            video.status === "Đã đăng" ? "bg-purple-500/10 text-purple-400 border-purple-500/20" :
                            "bg-blue-500/10 text-blue-400 border-blue-500/20"
                          }`}>
                            {video.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400">{video.date}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Instructions */}
          <div className="mt-8 bg-[#1a1a1a] rounded-xl border border-[#333] p-6">
            <h3 className="text-base font-semibold text-white mb-3">📋 Hướng dẫn sử dụng</h3>
            <ol className="space-y-2 text-sm text-gray-400">
              <li>1. Tạo video từ dulich-pipeline (http://localhost:7788)</li>
              <li>2. Sau khi render xong, bấm nút <span className="text-blue-400">📤</span> trên video để đăng lên Dashboard</li>
              <li>3. Vào trang <Link href="/dashboard/videos" className="text-purple-400 hover:underline">Quản lý video</Link> để duyệt</li>
              <li>4. Sau khi duyệt, bấm nút TikTok hoặc Facebook để đăng bài</li>
            </ol>
          </div>
        </>
      )}
    </div>
  );
}
