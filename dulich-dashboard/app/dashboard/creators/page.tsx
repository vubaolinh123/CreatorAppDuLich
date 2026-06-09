"use client";

import { useEffect, useState } from "react";
import { Users, Mail, Mic, Settings, Loader2 } from "lucide-react";

interface Creator {
  id: string;
  name: string;
  email: string;
  voice_provider: string;
  voice_id: string;
  hook_preference: string;
  videos: number;
}

export default function CreatorsPage() {
  const [creators, setCreators] = useState<Creator[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCreators = async () => {
      try {
        const res = await fetch("/api/creators");
        const data = await res.json();
        if (data.success) {
          setCreators(data.data);
        }
      } catch (err) {
        console.error("Lỗi khi load creators:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchCreators();
  }, []);

  return (
    <div className="p-8 max-w-[1200px] mx-auto">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white">Quản lý Creators</h1>
        <p className="text-sm text-gray-500">Thông tin cấu hình tài khoản và giọng nói AI của các Creator</p>
      </header>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 bg-[#161616] rounded-xl border border-[#333]">
          <Loader2 className="animate-spin text-purple-500 mb-3" size={32} />
          <p className="text-gray-400 text-sm">Đang tải danh sách creator...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {creators.map((creator) => (
            <div key={creator.id} className="bg-[#1a1a1a] rounded-xl border border-[#333] p-6 hover:border-purple-500/30 transition flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-4 mb-4">
                  <div className="w-12 h-12 rounded-full bg-gradient-to-tr from-purple-600 to-blue-600 flex items-center justify-center text-white font-bold text-lg">
                    {creator.name.charAt(0)}
                  </div>
                  <div>
                    <h3 className="text-white font-semibold text-base">{creator.name}</h3>
                    <p className="text-xs text-gray-500 flex items-center gap-1.5 mt-0.5">
                      <Mail size={12} /> {creator.email}
                    </p>
                  </div>
                </div>

                <div className="space-y-2 border-t border-[#2a2a2a] pt-4 mt-2">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500 font-medium">TTS Provider:</span>
                    <span className="text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/10 uppercase font-bold text-[10px]">
                      {creator.voice_provider}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500 font-medium">Giọng đọc AI:</span>
                    <span className="text-gray-300 font-mono flex items-center gap-1">
                      <Mic size={12} className="text-blue-400" /> {creator.voice_id}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500 font-medium">Hiệu ứng Hook:</span>
                    <span className="text-gray-300 flex items-center gap-1">
                      <Settings size={12} className="text-amber-400" /> {creator.hook_preference}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs border-t border-[#2a2a2a] pt-4 mt-6 text-gray-500">
                <span>Trạng thái: Hoạt động</span>
                <span className="text-white font-semibold bg-gray-800 px-2.5 py-1 rounded-full">
                  {creator.videos} videos
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
