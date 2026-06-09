import { LayoutTemplate } from "lucide-react";

export default function TemplatesPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-white mb-6">Quản lý Templates</h1>
      <div className="bg-[#1a1a1a] rounded-xl border border-[#333] p-12 text-center">
        <LayoutTemplate className="mx-auto mb-4 text-gray-600" size={48} />
        <p className="text-gray-400">Danh sách video templates sẽ hiển thị ở đây</p>
      </div>
    </div>
  );
}
