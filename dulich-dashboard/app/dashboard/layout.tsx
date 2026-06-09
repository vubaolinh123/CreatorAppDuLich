import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import Sidebar from "@/components/Sidebar";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();

  if (!session) {
    redirect("/login");
  }

  return (
    <div className="flex h-screen bg-gray-900">
      <Sidebar user={session.user ?? {}} />
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
