use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::process::{Command as StdCommand, Stdio};
use std::io::{BufRead, BufReader};
use tauri::{Window, Emitter};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemInfo {
    pub total_memory_gb: f64,
    pub cpu_count: usize,
    pub os: String,
    pub recommended_workers: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PipelineLogPayload {
    pub time: String,
    pub level: String,
    pub text: String,
}


#[derive(Debug, Serialize, Deserialize)]
pub struct VideoMeta {
    pub id: String,
    pub name: String,
    pub creator: String,
    pub date: String,
    pub status: String,
    pub path: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AlbumMeta {
    pub id: String,
    pub name: String,
    pub template_id: String,
    pub creator: String,
    pub date: String,
    pub status: String,
    pub path: String,
}

#[tauri::command]
pub fn read_file(path: String) -> Result<String, String> {
    fs::read_to_string(&path).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn write_file(path: String, content: String) -> Result<(), String> {
    if let Some(parent) = PathBuf::from(&path).parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::write(&path, content).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn list_directory(path: String) -> Result<Vec<String>, String> {
    let entries = fs::read_dir(&path).map_err(|e| e.to_string())?;
    let mut files = Vec::new();
    for entry in entries {
        let entry = entry.map_err(|e| e.to_string())?;
        files.push(entry.file_name().to_string_lossy().to_string());
    }
    Ok(files)
}

#[tauri::command]
pub fn get_videos() -> Result<Vec<VideoMeta>, String> {
    Ok(Vec::new())
}

#[tauri::command]
pub fn get_albums() -> Result<Vec<AlbumMeta>, String> {
    Ok(Vec::new())
}

#[tauri::command]
pub fn save_album(album: AlbumMeta) -> Result<AlbumMeta, String> {
    Ok(album)
}

#[tauri::command]
pub fn get_projects() -> Result<Vec<String>, String> {
    Ok(Vec::new())
}

#[tauri::command]
pub fn save_project(name: String) -> Result<String, String> {
    Ok(name)
}

#[tauri::command]
pub fn delete_project(name: String) -> Result<(), String> {
    Ok(())
}

#[tauri::command]
pub async fn run_pipeline(
    window: Window,
    topic: String,
    sheet_id: Option<String>,
    provider: Option<String>,
) -> Result<String, String> {
    // 1. Find dulich-pipeline directory
    let mut pipeline_dir = PathBuf::from(".");
    let mut found = false;
    
    // Check various common paths relative to current exe or cwd
    let paths_to_check = vec![
        PathBuf::from("../dulich-pipeline"),
        PathBuf::from("../../dulich-pipeline"),
        PathBuf::from("./dulich-pipeline"),
    ];
    
    for path in paths_to_check {
        if path.join("main.py").exists() {
            pipeline_dir = match fs::canonicalize(&path) {
                Ok(p) => p,
                Err(_) => path, // Fallback if canonicalize fails
            };
            found = true;
            break;
        }
    }
    
    if !found {
        return Err("Không tìm thấy thư mục dulich-pipeline hoặc file main.py. Hãy đảm bảo thư mục này nằm song song với dulich-desktop.".to_string());
    }
    
    // 2. Find python executable
    let mut python_exe = PathBuf::from("python"); // default fallback
    let windows_venv = pipeline_dir.join(".venv").join("Scripts").join("python.exe");
    let unix_venv = pipeline_dir.join(".venv").join("bin").join("python");
    
    if windows_venv.exists() {
        python_exe = windows_venv;
    } else if unix_venv.exists() {
        python_exe = unix_venv;
    }
    
    // 3. Prepare arguments
    let mut args = vec!["main.py".to_string(), "--topic".to_string(), topic];
    if let Some(sid) = sheet_id {
        if !sid.trim().is_empty() {
            args.push("--sheet-id".to_string());
            args.push(sid);
        }
    }
    if let Some(prov) = provider {
        if !prov.trim().is_empty() {
            args.push("--provider".to_string());
            args.push(prov);
        }
    }
    
    // 4. Spawn process
    let mut child = StdCommand::new(python_exe)
        .args(&args)
        .current_dir(&pipeline_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start python pipeline: {}", e))?;
        
    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;
    
    // Read stdout line-by-line in a separate task or thread
    let window_clone = window.clone();
    let stdout_reader = BufReader::new(stdout);
    
    let handle_stdout = tokio::task::spawn_blocking(move || {
        for line in stdout_reader.lines() {
            if let Ok(line_str) = line {
                let now = chrono::Local::now().format("%H:%M:%S").to_string();
                let mut level = "info".to_string();
                
                if line_str.contains("[WARNING]") || line_str.contains("[warning]") {
                    level = "warning".to_string();
                } else if line_str.contains("[SUCCESS]") || line_str.contains("[success]") || line_str.contains("✓") {
                    level = "success".to_string();
                } else if line_str.contains("[ERROR]") || line_str.contains("[error]") || line_str.contains("❌") {
                    level = "error".to_string();
                }
                
                let payload = PipelineLogPayload {
                    time: now,
                    level,
                    text: line_str,
                };
                let _ = window_clone.emit("pipeline-log", payload);
            }
        }
    });
    
    let window_clone2 = window.clone();
    let stderr_reader = BufReader::new(stderr);
    let handle_stderr = tokio::task::spawn_blocking(move || {
        for line in stderr_reader.lines() {
            if let Ok(line_str) = line {
                let now = chrono::Local::now().format("%H:%M:%S").to_string();
                let payload = PipelineLogPayload {
                    time: now,
                    level: "error".to_string(),
                    text: line_str,
                };
                let _ = window_clone2.emit("pipeline-log", payload);
            }
        }
    });
    
    // Wait for process to exit
    let status = child.wait().map_err(|e| e.to_string())?;
    
    // Ensure all output is read
    let _ = tokio::join!(handle_stdout, handle_stderr);
    
    if status.success() {
        // Look for the generated output/latest_run.json
        let result_json_path = pipeline_dir.join("output").join("latest_run.json");
        if result_json_path.exists() {
            let content = fs::read_to_string(result_json_path).map_err(|e| e.to_string())?;
            Ok(content)
        } else {
            Ok("{\"status\": \"success\", \"message\": \"Pipeline complete, but no output JSON found.\"}".to_string())
        }
    } else {
        Err(format!("Pipeline failed with exit status: {:?}", status))
    }
}

// ── Batch pipeline (News Channel) ────────────────────────────────────────────

#[tauri::command]
pub async fn run_batch_pipeline(
    window: Window,
    topics: Vec<String>,
    workers: usize,
    channel: String,
    voice_provider: String,
    ram_gb: f64,
    cpu_cores: usize,
) -> Result<String, String> {
    let topics_str = topics.join(",");
    let batch_count = topics.len().to_string();

    // Find pipeline dir
    let mut pipeline_dir = PathBuf::from("../dulich-pipeline");
    let paths = vec![
        PathBuf::from("../dulich-pipeline"),
        PathBuf::from("../../dulich-pipeline"),
    ];
    for path in &paths {
        if path.join("main.py").exists() {
            pipeline_dir = fs::canonicalize(path).unwrap_or(path.clone());
            break;
        }
    }

    // Find Python executable
    let python_exe = if pipeline_dir.join(".venv/Scripts/python.exe").exists() {
        pipeline_dir.join(".venv/Scripts/python.exe")
    } else if pipeline_dir.join(".venv/bin/python").exists() {
        pipeline_dir.join(".venv/bin/python")
    } else {
        PathBuf::from("python")
    };

    let args = vec![
        "main.py".to_string(),
        "--channel".to_string(), channel,
        "--batch".to_string(), batch_count,
        "--topics".to_string(), topics_str,
        "--workers".to_string(), workers.to_string(),
        "--provider".to_string(), voice_provider,
        "--ram-gb".to_string(), ram_gb.to_string(),
        "--cpu-cores".to_string(), cpu_cores.to_string(),
    ];

    let mut child = StdCommand::new(&python_exe)
        .args(&args)
        .current_dir(&pipeline_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start batch pipeline: {}", e))?;

    let stdout = child.stdout.take().ok_or("No stdout")?;
    let stderr = child.stderr.take().ok_or("No stderr")?;

    let win1 = window.clone();
    let handle_out = tokio::task::spawn_blocking(move || {
        for line in BufReader::new(stdout).lines() {
            if let Ok(text) = line {
                let level = if text.contains("[SUCCESS]") || text.contains("✓") || text.contains("✅") {
                    "success"
                } else if text.contains("[WARNING]") || text.contains("⚠") {
                    "warning"
                } else if text.contains("[ERROR]") || text.contains("❌") {
                    "error"
                } else {
                    "info"
                };
                let payload = PipelineLogPayload {
                    time: chrono::Local::now().format("%H:%M:%S").to_string(),
                    level: level.to_string(),
                    text,
                };
                let _ = win1.emit("pipeline-log", payload);
            }
        }
    });

    let win2 = window.clone();
    let handle_err = tokio::task::spawn_blocking(move || {
        for line in BufReader::new(stderr).lines() {
            if let Ok(text) = line {
                let payload = PipelineLogPayload {
                    time: chrono::Local::now().format("%H:%M:%S").to_string(),
                    level: "error".to_string(),
                    text,
                };
                let _ = win2.emit("pipeline-log", payload);
            }
        }
    });

    let status = child.wait().map_err(|e| e.to_string())?;
    let _ = tokio::join!(handle_out, handle_err);

    if status.success() {
        let result_path = pipeline_dir.join("output").join("latest_run.json");
        if result_path.exists() {
            Ok(fs::read_to_string(result_path).unwrap_or_default())
        } else {
            Ok("{\"status\":\"success\"}".to_string())
        }
    } else {
        Err(format!("Batch pipeline failed: {:?}", status))
    }
}

// ── System info ───────────────────────────────────────────────────────────────

#[tauri::command]
pub fn get_system_info() -> SystemInfo {
    let cpu_count = std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(2);

    // Conservative default: 8GB on Windows, 4GB otherwise
    #[cfg(target_os = "windows")]
    let total_memory_gb = 8.0f64;
    #[cfg(not(target_os = "windows"))]
    let total_memory_gb = 4.0f64;

    let recommended_workers = ((total_memory_gb / 0.5) as usize)
        .min(cpu_count)
        .max(1);

    SystemInfo {
        total_memory_gb,
        cpu_count,
        os: std::env::consts::OS.to_string(),
        recommended_workers,
    }
}

// ── Personal pipeline helper & commands ───────────────────────────────────────

fn get_python_exe_and_dir() -> Result<(PathBuf, PathBuf), String> {
    let mut pipeline_dir = PathBuf::from("../dulich-pipeline");
    let paths = vec![
        PathBuf::from("../dulich-pipeline"),
        PathBuf::from("../../dulich-pipeline"),
        PathBuf::from("./dulich-pipeline"),
    ];
    let mut found = false;
    for path in &paths {
        if path.join("main.py").exists() {
            pipeline_dir = fs::canonicalize(path).unwrap_or(path.clone());
            found = true;
            break;
        }
    }
    if !found {
        return Err("Không tìm thấy thư mục dulich-pipeline hoặc file main.py. Hãy đảm bảo thư mục này nằm song song với dulich-desktop.".to_string());
    }

    let python_exe = if pipeline_dir.join(".venv/Scripts/python.exe").exists() {
        pipeline_dir.join(".venv/Scripts/python.exe")
    } else if pipeline_dir.join(".venv/bin/python").exists() {
        pipeline_dir.join(".venv/bin/python")
    } else {
        PathBuf::from("python")
    };

    Ok((python_exe, pipeline_dir))
}

#[tauri::command]
pub async fn get_creators() -> Result<String, String> {
    let (python_exe, pipeline_dir) = get_python_exe_and_dir()?;
    let output = StdCommand::new(python_exe)
        .current_dir(pipeline_dir)
        .args(&["db_cli.py", "get_creators"])
        .output()
        .map_err(|e| format!("Failed to run db_cli.py: {}", e))?;
    
    if output.status.success() {
        let stdout_str = String::from_utf8_lossy(&output.stdout);
        Ok(stdout_str.into_owned())
    } else {
        let stderr_str = String::from_utf8_lossy(&output.stderr);
        Err(format!("db_cli.py failed: {}", stderr_str))
    }
}

#[tauri::command]
pub async fn save_creator(creator_json: String) -> Result<String, String> {
    let (python_exe, pipeline_dir) = get_python_exe_and_dir()?;
    let output = StdCommand::new(python_exe)
        .current_dir(pipeline_dir)
        .args(&["db_cli.py", "save_creator", &creator_json])
        .output()
        .map_err(|e| format!("Failed to run db_cli.py: {}", e))?;
    
    if output.status.success() {
        let stdout_str = String::from_utf8_lossy(&output.stdout);
        Ok(stdout_str.into_owned())
    } else {
        let stderr_str = String::from_utf8_lossy(&output.stderr);
        Err(format!("db_cli.py failed: {}", stderr_str))
    }
}

#[tauri::command]
pub async fn analyze_hook_video(video_path: String) -> Result<String, String> {
    let (python_exe, pipeline_dir) = get_python_exe_and_dir()?;
    let output = StdCommand::new(python_exe)
        .current_dir(pipeline_dir)
        .args(&["db_cli.py", "analyze_video", &video_path])
        .output()
        .map_err(|e| format!("Failed to run db_cli.py: {}", e))?;
    
    if output.status.success() {
        let stdout_str = String::from_utf8_lossy(&output.stdout);
        Ok(stdout_str.into_owned())
    } else {
        let stderr_str = String::from_utf8_lossy(&output.stderr);
        Err(format!("db_cli.py failed: {}", stderr_str))
    }
}

#[tauri::command]
pub async fn run_personal_pipeline(
    window: Window,
    creator_id: String,
    script_text: String,
    clips: Vec<String>,
    hook_style: String,
    hook_text: String,
    voice_provider: String,
) -> Result<String, String> {
    let (python_exe, pipeline_dir) = get_python_exe_and_dir()?;
    
    let clips_str = clips.join(",");
    
    let mut args = vec![
        "main.py".to_string(),
        "--channel".to_string(), "personal".to_string(),
        "--creator".to_string(), creator_id,
        "--script".to_string(), script_text,
        "--hook-style".to_string(), hook_style,
        "--hook-text".to_string(), hook_text,
    ];
    
    if !voice_provider.trim().is_empty() {
        args.push("--provider".to_string());
        args.push(voice_provider);
    }
    
    if !clips_str.is_empty() {
        args.push("--clips".to_string());
        args.push(clips_str);
    }
    
    let mut child = StdCommand::new(&python_exe)
        .args(&args)
        .current_dir(&pipeline_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start personal pipeline: {}", e))?;
        
    let stdout = child.stdout.take().ok_or("No stdout")?;
    let stderr = child.stderr.take().ok_or("No stderr")?;
    
    let win1 = window.clone();
    let handle_out = tokio::task::spawn_blocking(move || {
        for line in BufReader::new(stdout).lines() {
            if let Ok(text) = line {
                let level = if text.contains("[SUCCESS]") || text.contains("✓") || text.contains("✅") {
                    "success"
                } else if text.contains("[WARNING]") || text.contains("⚠") {
                    "warning"
                } else if text.contains("[ERROR]") || text.contains("❌") {
                    "error"
                } else {
                    "info"
                };
                let payload = PipelineLogPayload {
                    time: chrono::Local::now().format("%H:%M:%S").to_string(),
                    level: level.to_string(),
                    text,
                };
                let _ = win1.emit("pipeline-log", payload);
            }
        }
    });
    
    let win2 = window.clone();
    let handle_err = tokio::task::spawn_blocking(move || {
        for line in BufReader::new(stderr).lines() {
            if let Ok(text) = line {
                let payload = PipelineLogPayload {
                    time: chrono::Local::now().format("%H:%M:%S").to_string(),
                    level: "error".to_string(),
                    text,
                };
                let _ = win2.emit("pipeline-log", payload);
            }
        }
    });
    
    let status = child.wait().map_err(|e| e.to_string())?;
    let _ = tokio::join!(handle_out, handle_err);
    
    if status.success() {
        let result_path = pipeline_dir.join("output").join("latest_run.json");
        if result_path.exists() {
            Ok(fs::read_to_string(result_path).unwrap_or_default())
        } else {
            Ok("{\"status\":\"success\"}".to_string())
        }
    } else {
        Err(format!("Personal pipeline failed: {:?}", status))
    }
}

// ── Seeding & Album Commands ─────────────────────────────────────────────────

#[tauri::command]
pub async fn get_seeding() -> Result<String, String> {
    let (python_exe, pipeline_dir) = get_python_exe_and_dir()?;
    let output = StdCommand::new(python_exe)
        .current_dir(pipeline_dir)
        .args(&["db_cli.py", "get_seeding"])
        .output()
        .map_err(|e| format!("Failed to run db_cli.py: {}", e))?;
    
    if output.status.success() {
        let stdout_str = String::from_utf8_lossy(&output.stdout);
        Ok(stdout_str.into_owned())
    } else {
        let stderr_str = String::from_utf8_lossy(&output.stderr);
        Err(format!("db_cli.py failed: {}", stderr_str))
    }
}

#[tauri::command]
pub async fn save_seeding(seeding_json: String) -> Result<String, String> {
    let (python_exe, pipeline_dir) = get_python_exe_and_dir()?;
    let output = StdCommand::new(python_exe)
        .current_dir(pipeline_dir)
        .args(&["db_cli.py", "save_seeding", &seeding_json])
        .output()
        .map_err(|e| format!("Failed to run db_cli.py: {}", e))?;
    
    if output.status.success() {
        let stdout_str = String::from_utf8_lossy(&output.stdout);
        Ok(stdout_str.into_owned())
    } else {
        let stderr_str = String::from_utf8_lossy(&output.stderr);
        Err(format!("db_cli.py failed: {}", stderr_str))
    }
}

#[tauri::command]
pub async fn delete_seeding(id: String) -> Result<String, String> {
    let (python_exe, pipeline_dir) = get_python_exe_and_dir()?;
    let output = StdCommand::new(python_exe)
        .current_dir(pipeline_dir)
        .args(&["db_cli.py", "delete_seeding", &id])
        .output()
        .map_err(|e| format!("Failed to run db_cli.py: {}", e))?;
    
    if output.status.success() {
        let stdout_str = String::from_utf8_lossy(&output.stdout);
        Ok(stdout_str.into_owned())
    } else {
        let stderr_str = String::from_utf8_lossy(&output.stderr);
        Err(format!("db_cli.py failed: {}", stderr_str))
    }
}

#[tauri::command]
pub async fn run_album_pipeline(
    window: Window,
    topic: String,
    title: String,
    subtitle: String,
    frame: String,
    creator_id: String,
) -> Result<String, String> {
    let (python_exe, pipeline_dir) = get_python_exe_and_dir()?;
    
    let mut args = vec![
        "main.py".to_string(),
        "--action".to_string(), "album".to_string(),
        "--topic".to_string(), topic,
        "--title".to_string(), title,
        "--subtitle".to_string(), subtitle,
        "--creator".to_string(), creator_id,
    ];
    
    if !frame.trim().is_empty() {
        args.push("--frame".to_string());
        args.push(frame);
    }
    
    let mut child = StdCommand::new(&python_exe)
        .args(&args)
        .current_dir(&pipeline_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start album pipeline: {}", e))?;
        
    let stdout = child.stdout.take().ok_or("No stdout")?;
    let stderr = child.stderr.take().ok_or("No stderr")?;
    
    let win1 = window.clone();
    let handle_out = tokio::task::spawn_blocking(move || {
        for line in BufReader::new(stdout).lines() {
            if let Ok(text) = line {
                let level = if text.contains("[SUCCESS]") || text.contains("✓") || text.contains("✅") {
                    "success"
                } else if text.contains("[WARNING]") || text.contains("⚠") {
                    "warning"
                } else if text.contains("[ERROR]") || text.contains("❌") {
                    "error"
                } else {
                    "info"
                };
                let payload = PipelineLogPayload {
                    time: chrono::Local::now().format("%H:%M:%S").to_string(),
                    level: level.to_string(),
                    text,
                };
                let _ = win1.emit("pipeline-log", payload);
            }
        }
    });
    
    let win2 = window.clone();
    let handle_err = tokio::task::spawn_blocking(move || {
        for line in BufReader::new(stderr).lines() {
            if let Ok(text) = line {
                let payload = PipelineLogPayload {
                    time: chrono::Local::now().format("%H:%M:%S").to_string(),
                    level: "error".to_string(),
                    text,
                };
                let _ = win2.emit("pipeline-log", payload);
            }
        }
    });
    
    let status = child.wait().map_err(|e| e.to_string())?;
    let _ = tokio::join!(handle_out, handle_err);
    
    if status.success() {
        let result_path = pipeline_dir.join("output").join("latest_run.json");
        if result_path.exists() {
            Ok(fs::read_to_string(result_path).unwrap_or_default())
        } else {
            Ok("{\"status\":\"success\"}".to_string())
        }
    } else {
        Err(format!("Album pipeline failed: {:?}", status))
    }
}

#[tauri::command]
pub fn select_folder() -> Result<Option<String>, String> {
    let folder = rfd::FileDialog::new()
        .pick_folder();
    Ok(folder.map(|path| path.to_string_lossy().to_string()))
}

#[tauri::command]
pub fn select_files() -> Result<Option<Vec<String>>, String> {
    let files = rfd::FileDialog::new()
        .add_filter("Videos", &["mp4", "mkv", "avi", "mov"])
        .pick_files();
    Ok(files.map(|paths| paths.into_iter().map(|p| p.to_string_lossy().to_string()).collect()))
}

#[tauri::command]
pub fn show_in_folder(path: String) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        let path_obj = std::path::Path::new(&path);
        let path_str = path_obj.to_string_lossy().to_string();
        if path_obj.exists() {
            let mut cmd = std::process::Command::new("explorer");
            cmd.arg(format!("/select,{}", path_str));
            cmd.spawn().map_err(|e| e.to_string())?;
        } else if let Some(parent) = path_obj.parent() {
            if parent.exists() {
                std::process::Command::new("explorer")
                    .arg(parent.to_string_lossy().to_string())
                    .spawn()
                    .map_err(|e| e.to_string())?;
            }
        }
    }
    
    #[cfg(target_os = "macos")]
    {
        let path_obj = std::path::Path::new(&path);
        if path_obj.exists() {
            std::process::Command::new("open")
                .arg("-R")
                .arg(path_obj)
                .spawn()
                .map_err(|e| e.to_string())?;
        } else if let Some(parent) = path_obj.parent() {
            if parent.exists() {
                std::process::Command::new("open")
                    .arg(parent)
                    .spawn()
                    .map_err(|e| e.to_string())?;
            }
        }
    }

    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    {
        let path_obj = std::path::Path::new(&path);
        let folder = if path_obj.is_dir() {
            path_obj
        } else {
            path_obj.parent().unwrap_or(path_obj)
        };
        if folder.exists() {
            std::process::Command::new("xdg-open")
                .arg(folder)
                .spawn()
                .map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}


