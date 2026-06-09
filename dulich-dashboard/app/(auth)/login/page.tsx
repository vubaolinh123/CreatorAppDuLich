import LoginForm from "./LoginForm";

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900">
      <div className="w-full max-w-md bg-gray-800 rounded-xl p-8 shadow-2xl">
        <h1 className="text-2xl font-bold text-white text-center mb-2">
          DuLichApp
        </h1>
        <p className="text-gray-400 text-center text-sm mb-8">
          Hệ thống quản lý nội dung du lịch
        </p>
        <LoginForm />
      </div>
    </div>
  );
}
