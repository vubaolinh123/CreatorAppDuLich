// Google Drive API utilities for desktop app
// Uses Rust backend via Tauri invoke for OAuth + file operations

export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  size: string;
  createdTime: string;
  webViewLink: string;
  thumbnailLink?: string;
}

export interface DriveFolder {
  id: string;
  name: string;
  files: DriveFile[];
}

export async function listFiles(folderId?: string): Promise<DriveFile[]> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<DriveFile[]>("list_drive_files", { folderId });
}

export async function uploadFile(
  localPath: string,
  driveFolderId: string,
  fileName: string
): Promise<DriveFile> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<DriveFile>("upload_to_drive", {
    localPath,
    driveFolderId,
    fileName,
  });
}

export async function downloadFile(fileId: string, localPath: string): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("download_from_drive", { fileId, localPath });
}

export async function createFolder(name: string, parentId?: string): Promise<DriveFolder> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<DriveFolder>("create_drive_folder", { name, parentId });
}
