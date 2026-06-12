// Prevents additional console window on Windows in release builds
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
use commands::{
    get_projects, save_project, delete_project,
    run_pipeline, run_batch_pipeline, get_system_info,
    get_creators, save_creator, analyze_hook_video, run_personal_pipeline,
    get_seeding, save_seeding, delete_seeding, run_album_pipeline,
    select_folder, select_files, show_in_folder,
    select_single_file, generate_scene_plan, assemble_from_scenes, set_api_keys,
    preview_voice,
};

fn main() {
    std::env::set_var("PYTHONUTF8", "1");
    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            get_projects,
            save_project,
            delete_project,
            commands::read_file,
            commands::write_file,
            commands::list_directory,
            commands::get_videos,
            commands::get_albums,
            commands::save_album,
            run_pipeline,
            run_batch_pipeline,
            get_system_info,
            get_creators,
            save_creator,
            analyze_hook_video,
            run_personal_pipeline,
            get_seeding,
            save_seeding,
            delete_seeding,
            run_album_pipeline,
            select_folder,
            select_files,
            show_in_folder,
            select_single_file,
            generate_scene_plan,
            assemble_from_scenes,
            set_api_keys,
            preview_voice,
            upload_canva_frames,
            list_learned_frames,
            analyze_single_frame,
            delete_learned_frame,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
