import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import type { User } from "@auth/core/types";

const users: Record<string, { password: string; name: string; role: string }> = {
  "admin": { password: "admin@123", name: "Admin", role: "admin" },
  "admin@dulichapp.com": { password: "admin123", name: "Admin", role: "admin" },
  "creator1@dulichapp.com": { password: "creator123", name: "Creator 1", role: "creator" },
  "creator2@dulichapp.com": { password: "creator123", name: "Creator 2", role: "creator" },
  "creator3@dulichapp.com": { password: "creator123", name: "Creator 3", role: "creator" },
  "creator4@dulichapp.com": { password: "creator123", name: "Creator 4", role: "creator" },
  "creator5@dulichapp.com": { password: "creator123", name: "Creator 5", role: "creator" },
};

export const { handlers, auth } = NextAuth({
  providers: [
    Credentials({
      id: "credentials",
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;

        const email = credentials.email as string;
        const password = credentials.password as string;

        const user = users[email];
        if (!user || user.password !== password) return null;

        return { email, name: user.name, role: user.role } as User;
      },
    }),
  ],
  session: { strategy: "jwt" },
  pages: { signIn: "/login" },
  secret: process.env.NEXTAUTH_SECRET || "dulichapp-secret-key",
});

export const { GET, POST } = handlers;
