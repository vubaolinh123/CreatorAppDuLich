// Google Sheets API utilities for desktop app
// Uses Rust backend via Tauri invoke for OAuth + API calls

export interface VideoRow {
  id: string;
  name: string;
  creator: string;
  date: string;
  status: string;
  drive_link: string;
  drive_id: string;
  published_platforms: string;
}

export interface AlbumRow {
  id: string;
  name: string;
  template_id: string;
  creator: string;
  date: string;
  status: string;
  drive_link: string;
}

export interface CreatorRow {
  id: string;
  name: string;
  email: string;
  voice_id: string;
  template_id: string;
  drive_folder: string;
}

export interface SeedingRow {
  id: string;
  name: string;
  type: string;
  category: string;
  location: string;
  notes: string;
}

export async function getVideos(): Promise<VideoRow[]> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<VideoRow[]>("get_videos");
}

export async function getAlbums(): Promise<AlbumRow[]> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<AlbumRow[]>("get_albums");
}

export async function addVideoRow(row: VideoRow): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("add_video_row", { row });
}

export async function addAlbumRow(row: AlbumRow): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("add_album_row", { row });
}

export async function updateVideoStatus(id: string, status: string): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("update_video_status", { id, status });
}
