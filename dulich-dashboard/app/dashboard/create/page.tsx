"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Wand2,
  Sparkles,
  Download,
  Info,
  Server,
  Monitor,
  ArrowRight,
  Copy,
  Check,
  Code,
  Laptop
} from "lucide-react";

export default function CreatePage() {
  const router = useRouter();
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  // Lấy dashboard URL hiện tại từ client-side
  const dashboardUrl = typeof window !== "undefined" ? window.location.origin : "http://localhost:3000";

  const handleCopyUrl = () => {
    navigator.clipboard.writeText(dashboardUrl);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 mb-8">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Sparkles className="text-white animate-pulse" size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Tạo bài mới & Sản xuất Video</h1>
            <p className="text-sm text-gray-500">
              Vận hành AI video pipeline thông qua ứng dụng máy tính
            </p>
          </div>
        </div>
      </div>

      {/* Info Alert Box */}
      <div className="bg-[#1c1917] border border-[#d97706]/30 rounded-2xl p-6 mb-8 flex gap-4 items-start shadow-md">
        <div className="p-2 rounded-xl bg-[#d97706]/10 text-[#f59e0b] mt-0.5">
          <Info size={20} />
        </div>
        <div>
          <h3 className="font-semibold text-white mb-1">Kiến trúc Zero-Timeout & Local First</h3>
          <p className="text-sm text-gray-400 leading-relaxed">
            Quy trình tạo video AI (bao gồm: Phân tích trend, Viết kịch bản, Sinh giọng nói ElevenLabs, Render video bằng FFmpeg) tốn rất nhiều tài nguyên phần cứng và thời gian xử lý.
            Để tránh việc bị giới hạn thời gian chạy của máy chủ serverless trên **Vercel (Timeout 10-60 giây)**, tính năng tạo video đã được chuyển đổi hoàn toàn sang **Ứng dụng Local (Tauri Desktop App)**. 
          </p>
        </div>
      </div>

      {/* Architecture Visual Diagram */}
      <div className="bg-[#161616] border border-[#252525] rounded-2xl p-8 mb-8 text-center shadow-inner">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-6">Mô hình hoạt động</h3>
        <div className="flex flex-col md:flex-row items-center justify-center gap-6">
          {/* Local App Card */}
          <div className="bg-[#1e1e1e] border border-[#333] rounded-xl p-5 w-full md:w-64 flex flex-col items-center gap-3">
            <div className="p-3 bg-indigo-500/10 text-indigo-400 rounded-xl">
              <Monitor size={28} />
            </div>
            <div>
              <h4 className="font-bold text-white text-sm">DuLichApp Desktop</h4>
              <p className="text-xs text-gray-500 mt-1">Chạy Python Pipeline, render video, lưu trữ source file local nặng.</p>
            </div>
          </div>

          {/* Sync Arrow */}
          <div className="flex flex-col items-center text-indigo-400 gap-1 animate-pulse">
            <span className="text-[10px] uppercase font-bold tracking-widest text-indigo-400">Sync API</span>
            <div className="flex items-center gap-1">
              <ArrowRight size={24} className="rotate-90 md:rotate-0" />
            </div>
          </div>

          {/* Cloud Dashboard Card */}
          <div className="bg-[#1e1e1e] border border-[#333] rounded-xl p-5 w-full md:w-64 flex flex-col items-center gap-3">
            <div className="p-3 bg-pink-500/10 text-pink-400 rounded-xl">
              <Server size={28} />
            </div>
            <div>
              <h4 className="font-bold text-white text-sm">Vercel Dashboard</h4>
              <p className="text-xs text-gray-500 mt-1">Duyệt bài viết, theo dõi thống kê, bấm nút đăng trực tiếp lên mạng xã hội.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Installation Steps */}
      <div className="space-y-6 mb-8">
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          <Laptop size={18} className="text-indigo-400" />
          Hướng dẫn 3 bước cài đặt nhanh
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Step 1 */}
          <div className="bg-[#161616] border border-[#252525] rounded-xl p-6 relative overflow-hidden">
            <div className="text-4xl font-extrabold text-[#222] absolute right-4 top-2 select-none">01</div>
            <h4 className="font-bold text-white mb-2 relative z-10">Tải & Cài đặt App</h4>
            <p className="text-xs text-gray-400 leading-relaxed">
              Tải bộ cài đặt phần mềm Tauri cho Windows (file .exe) về máy tính cá nhân của bạn.
            </p>
          </div>

          {/* Step 2 */}
          <div className="bg-[#161616] border border-[#252525] rounded-xl p-6 relative overflow-hidden">
            <div className="text-4xl font-extrabold text-[#222] absolute right-4 top-2 select-none">02</div>
            <h4 className="font-bold text-white mb-2 relative z-10">Cấu hình Endpoint</h4>
            <p className="text-xs text-gray-400 leading-relaxed">
              Mở app, vào tab **Cài đặt** và dán địa chỉ Dashboard này vào phần **Dashboard URL** để đồng bộ.
            </p>
          </div>

          {/* Step 3 */}
          <div className="bg-[#161616] border border-[#252525] rounded-xl p-6 relative overflow-hidden">
            <div className="text-4xl font-extrabold text-[#222] absolute right-4 top-2 select-none">03</div>
            <h4 className="font-bold text-white mb-2 relative z-10">Tạo video 1-Click</h4>
            <p className="text-xs text-gray-400 leading-relaxed">
              Bắt đầu tạo video, theo dõi live log và bấm **Đồng bộ** để đẩy kết quả lên web này duyệt và đăng.
            </p>
          </div>
        </div>
      </div>

      {/* Configuration Copy Box */}
      <div className="bg-[#161616] border border-[#252525] rounded-2xl p-6 mb-8">
        <h4 className="font-bold text-white text-sm mb-4 flex items-center gap-2">
          <Code size={16} className="text-purple-400" />
          Thông tin cấu hình cho Desktop App
        </h4>
        
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Dashboard URL</label>
            <div className="flex gap-2">
              <input
                type="text"
                readOnly
                value={dashboardUrl}
                className="flex-1 bg-[#111] border border-[#2c2c2c] rounded-lg px-4 py-2 text-sm text-gray-300 focus:outline-none"
              />
              <button
                onClick={handleCopyUrl}
                className="px-4 py-2 bg-[#222] hover:bg-[#333] border border-[#333] hover:border-gray-600 rounded-lg text-sm font-medium text-gray-300 transition flex items-center gap-1.5 min-w-[90px] justify-center"
              >
                {copiedUrl ? (
                  <>
                    <Check size={14} className="text-green-400" />
                    <span className="text-green-400">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy size={14} />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
            <p className="text-[11px] text-gray-500 mt-2">Dán giá trị này vào phần Cài đặt của DuLichApp Desktop để kết nối hai ứng dụng.</p>
          </div>
        </div>
      </div>

      {/* Download Action Section */}
      <div className="bg-gradient-to-r from-indigo-900/40 via-purple-900/40 to-pink-900/40 border border-indigo-500/20 rounded-2xl p-8 flex flex-col md:flex-row items-center justify-between gap-6 shadow-lg">
        <div>
          <h3 className="text-lg font-bold text-white mb-2">Bạn đã sẵn sàng sản xuất video?</h3>
          <p className="text-sm text-gray-300 max-w-lg leading-relaxed">
            Tải bộ cài đặt phần mềm **DuLichApp Desktop** phiên bản mới nhất dành cho Windows 10/11.
          </p>
        </div>
        <button
          onClick={() => alert("Chức năng tải file bộ cài đặt Desktop app đang được chuẩn bị. Bạn có thể tự build source code Tauri local bằng lệnh 'npm run tauri:build'.")}
          className="flex items-center gap-2 px-6 py-4 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 text-white font-bold rounded-xl transition shadow-lg shadow-indigo-500/30 hover:scale-[1.02] active:scale-[0.98] whitespace-nowrap"
        >
          <Download size={18} />
          Tải phần mềm cho Windows (.exe)
        </button>
      </div>
    </div>
  );
}
