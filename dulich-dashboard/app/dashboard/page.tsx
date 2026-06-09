"use client";

import { useEffect, useState } from "react";
import { Film, Images, CheckCircle, Clock, Loader2, ArrowRight } from "lucide-react";
import type { VideoItem } from "@/lib/mock_db";
import Link from "next/link";

export default function DashboardPage() {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchVideos = async () => {
      try {
        const res = await fetch("/api/videos");
        const data = await res.json();
        if (data.success) {
          setVideos(data.data);
        }
      } catch (err) {
        console.error("Lỗi khi fetch stats:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchVideos();
  }, []);

  // Compute stats
  const totalCount = videos.length;
  const pendingCount = videos.filter((v) => v.status === "Chờ duyệt").length;
  const approvedCount = videos.filter((v) => v.status === "Đã duyệt" || v.status === "Đã đăng").length;
  const renderingCount = videos.filter((v) => v.status === "Đang render").length;

  const stats = [
    { label: "Tổng video bài viết", value: totalCount.toString(), icon: Film, color: "text-blue-400" },
    { label: "Đang render video", value: renderingCount.toString(), icon: Loader2, color: "text-amber-400" },
    { label: "Đã duyệt / Đăng", value: approvedCount.toString(), icon: CheckCircle, color: "text-emerald-400" },
    { label: "Chờ phê duyệt", value: pendingCount.toString(), icon: Clock, color: "text-yellow-400" },
  ];

  const recentVideos = videos.slice(0, 5); // top 5 recent

  return (
    <div className="p-8 max-w-[1200px] mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Tổng quan</h1>
          <p className="text-sm text-gray-500">Báo cáo hoạt động sản xuất nội dung du lịch</p>
        </div>
        <Link
          href="/dashboard/create"
          className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-medium px-4 py-2 rounded-xl text-sm transition"
        >
          + Tạo bài (Local)
        </Link>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2 className="animate-spin text-purple-500 mb-2" size={32} />
          <p className="text-gray-500 text-sm">Đang tải báo cáo tổng quan...</p>
        </div>
      ) : (
        <>
          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {stats.map((stat) => (
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
              <h2 className="text-base font-semibold text-white">Hoạt động sản xuất gần đây</h2>
              <Link
                href="/dashboard/videos"
                className="text-xs text-purple-400 hover:text-purple-300 font-medium flex items-center gap-1 transition"
              >
                Quản lý chi tiết <ArrowRight size={12} />
              </Link>
            </div>
            {recentVideos.length === 0 ? (
              <div className="p-12 text-center text-gray-500 text-sm">
                Không có dữ liệu video nào gần đây.
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
        </>
      )}
    </div>
  );
}
