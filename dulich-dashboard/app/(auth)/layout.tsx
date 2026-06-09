import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";

export default async function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();

  if (session) {
    redirect("/dashboard");
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900">
      {children}
    </div>
  );
}
