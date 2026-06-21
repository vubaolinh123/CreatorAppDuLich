import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";

if (!supabaseUrl || !supabaseKey) {
  console.warn("[Supabase] NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY not configured");
}

export const supabase = createClient(supabaseUrl, supabaseKey);

// Types
export interface User {
  id: string;
  username: string;
  password: string;
  role: "admin" | "staff" | "news";
  name: string;
  hook_style: string;
  voice: string;
  created_at: string;
  updated_at: string;
}

export interface Content {
  id: string;
  user_id: string;
  content_type: "video" | "image";
  status: "pending" | "approved" | "rejected" | "published";
  title: string;
  topic: string;
  script: {
    hook?: string;
    body?: string;
    cta?: string;
  };
  drive_url: string;
  local_path: string;
  thumbnail_url: string;
  metadata: Record<string, any>;
  job_id: string;
  hook_style: string;
  hook_text: string;
  voice_provider: string;
  video_type: string;
  created_at: string;
  updated_at: string;
}

export interface PublishLog {
  id: string;
  content_id: string;
  platform: "tiktok" | "facebook" | "instagram" | "youtube";
  platform_post_id: string;
  post_url: string;
  status: "pending" | "success" | "failed";
  error_message: string;
  published_at: string;
}

// Helper functions
export async function getUser(username: string): Promise<User | null> {
  const { data, error } = await supabase
    .from("users")
    .select("*")
    .eq("username", username)
    .single();

  if (error || !data) return null;
  return data as User;
}

export async function verifyUser(username: string, password: string): Promise<User | null> {
  const user = await getUser(username);
  if (user && user.password === password) {
    return user;
  }
  return null;
}

export async function getAllContent(status?: string, contentType?: string): Promise<Content[]> {
  let query = supabase.from("content").select("*").order("created_at", { ascending: false });

  if (status) {
    query = query.eq("status", status);
  }
  if (contentType) {
    query = query.eq("content_type", contentType);
  }

  const { data, error } = await query;
  if (error) {
    console.error("[Supabase] getAllContent error:", error);
    return [];
  }
  return (data || []) as Content[];
}

export async function getContentById(id: string): Promise<Content | null> {
  const { data, error } = await supabase
    .from("content")
    .select("*")
    .eq("id", id)
    .single();

  if (error || !data) return null;
  return data as Content;
}

export async function updateContentStatus(id: string, status: string): Promise<boolean> {
  const { error } = await supabase
    .from("content")
    .update({ status, updated_at: new Date().toISOString() })
    .eq("id", id);

  if (error) {
    console.error("[Supabase] updateContentStatus error:", error);
    return false;
  }
  return true;
}

export async function createContent(content: Partial<Content>): Promise<Content | null> {
  const { data, error } = await supabase
    .from("content")
    .insert(content)
    .select()
    .single();

  if (error) {
    console.error("[Supabase] createContent error:", error);
    return null;
  }
  return data as Content;
}

export async function createPublishLog(log: Partial<PublishLog>): Promise<PublishLog | null> {
  const { data, error } = await supabase
    .from("publish_logs")
    .insert(log)
    .select()
    .single();

  if (error) {
    console.error("[Supabase] createPublishLog error:", error);
    return null;
  }
  return data as PublishLog;
}

export async function getPublishLogs(contentId: string): Promise<PublishLog[]> {
  const { data, error } = await supabase
    .from("publish_logs")
    .select("*")
    .eq("content_id", contentId)
    .order("published_at", { ascending: false });

  if (error) {
    console.error("[Supabase] getPublishLogs error:", error);
    return [];
  }
  return (data || []) as PublishLog[];
}
