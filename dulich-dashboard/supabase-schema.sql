-- Supabase Schema for DuLichApp
-- Run this SQL in Supabase SQL Editor to create tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (replaces users.json)
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin', 'staff', 'news')),
  name TEXT,
  hook_style TEXT DEFAULT 'hook_red',
  voice TEXT DEFAULT 'gtts',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Content table (videos from pipeline)
CREATE TABLE IF NOT EXISTS content (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  content_type TEXT NOT NULL CHECK (content_type IN ('video', 'image')),
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'published')),
  title TEXT,
  topic TEXT,
  script JSONB DEFAULT '{}'::jsonb,
  drive_url TEXT,
  local_path TEXT,
  thumbnail_url TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  job_id TEXT,
  hook_style TEXT,
  hook_text TEXT,
  voice_provider TEXT,
  video_type TEXT DEFAULT 'personal',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Publishing logs (track where content was published)
CREATE TABLE IF NOT EXISTS publish_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  content_id UUID REFERENCES content(id) ON DELETE CASCADE,
  platform TEXT NOT NULL CHECK (platform IN ('tiktok', 'facebook', 'instagram', 'youtube')),
  platform_post_id TEXT,
  post_url TEXT,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'success', 'failed')),
  error_message TEXT,
  published_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_content_user_id ON content(user_id);
CREATE INDEX IF NOT EXISTS idx_content_status ON content(status);
CREATE INDEX IF NOT EXISTS idx_content_created_at ON content(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_publish_logs_content_id ON publish_logs(content_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Insert default users (same as users.json)
INSERT INTO users (username, password, role, name, hook_style, voice) VALUES
  ('admin', 'admin123', 'admin', 'Quản lý', 'hook_red', 'gtts'),
  ('nv1', '123', 'staff', 'Nhân viên 1', 'hook_red', 'gtts'),
  ('nv2', '123', 'staff', 'Nhân viên 2', 'hook_green', 'gtts'),
  ('nv3', '123', 'staff', 'Nhân viên 3', 'hook_brown', 'gtts'),
  ('nv4', '123', 'staff', 'Nhân viên 4', 'hook_serif', 'gtts'),
  ('nv5', '123', 'staff', 'Nhân viên 5', 'hook_meo', 'gtts'),
  ('tintuc', '123', 'news', 'Kênh tin tức Đà Lạt', 'hook_news', 'gtts')
ON CONFLICT (username) DO NOTHING;

-- Enable Row Level Security (RLS)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE content ENABLE ROW LEVEL SECURITY;
ALTER TABLE publish_logs ENABLE ROW LEVEL SECURITY;

-- RLS Policies (allow all for now - can be tightened later)
CREATE POLICY "Allow all operations on users" ON users FOR ALL USING (true);
CREATE POLICY "Allow all operations on content" ON content FOR ALL USING (true);
CREATE POLICY "Allow all operations on publish_logs" ON publish_logs FOR ALL USING (true);
