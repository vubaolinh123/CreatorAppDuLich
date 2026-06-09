"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import {
  User,
  LogOut,
  Film,
  Images,
  Store,
  LayoutTemplate,
  Users,
  Settings,
  Home,
  Wand2,
} from "lucide-react";

const navItems = [
  { href: "/dashboard", icon: Home, label: "Tổng quan" },
  { href: "/dashboard/create", icon: Wand2, label: "Tạo bài (Local)" },
  { href: "/dashboard/videos", icon: Film, label: "Video" },
  { href: "/dashboard/albums", icon: Images, label: "Album ảnh" },
  { href: "/dashboard/seeding", icon: Store, label: "Seeding" },
  { href: "/dashboard/templates", icon: LayoutTemplate, label: "Templates" },
  { href: "/dashboard/creators", icon: Users, label: "Creators" },
  { href: "/dashboard/settings", icon: Settings, label: "Cài đặt" },
];

export default function Sidebar({ user }: { user: { name?: string | null; email?: string | null; role?: string } }) {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-[#111] border-r border-[#333] flex flex-col">
      <div className="h-16 flex items-center px-6 border-b border-[#333]">
        <h1 className="text-lg font-bold text-white">DuLichApp</h1>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition ${
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:text-white hover:bg-[#222]"
              }`}
            >
              <item.icon size={18} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-[#333]">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
            <User size={16} className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-white truncate">{user?.name || "User"}</p>
            <p className="text-xs text-gray-500 truncate">{user?.email || ""}</p>
          </div>
        </div>
        <button
          onClick={() => signOut()}
          className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-[#222] rounded-lg transition"
        >
          <LogOut size={16} />
          Đăng xuất
        </button>
      </div>
    </aside>
  );
}
