"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";

export default function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const res = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });

    if (res?.error) {
      setError("Email hoặc mật khẩu không đúng");
      setLoading(false);
    } else {
      router.refresh();
      router.push("/dashboard");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-red-500/10 border border-red-500 text-red-400 rounded-lg px-4 py-2 text-sm">
          {error}
        </div>
      )}
      <div>
        <label className="block text-gray-400 text-sm mb-1">Tài khoản hoặc Email</label>
        <input
          type="text"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
          placeholder="admin hoặc creator@dulichapp.com"
          required
        />
      </div>
      <div>
        <label className="block text-gray-400 text-sm mb-1">Mật khẩu</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
          placeholder="••••••"
          required
        />
      </div>
      <button
        type="submit"
        disabled={loading}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white font-medium rounded-lg px-4 py-2 transition"
      >
        {loading ? "Đang đăng nhập..." : "Đăng nhập"}
      </button>
    </form>
  );
}
