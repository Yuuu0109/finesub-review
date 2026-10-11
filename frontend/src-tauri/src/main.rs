#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
mod updates;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(updates::PendingUpdate::default())
        .invoke_handler(tauri::generate_handler![updates::check_desktop_update, updates::download_desktop_update])
        .setup(|app| {
            tauri::WebviewWindowBuilder::new(app, "main", tauri::WebviewUrl::App("index.html".into()))
                .title("FineSub 知识库审核")
                .inner_size(1280.0, 860.0)
                .min_inner_size(900.0, 640.0)
                // Preserve HTML file drop for the existing import interface.
                .disable_drag_drop_handler()
                .on_navigation(|url| {
                    let production = (matches!(url.scheme(), "http" | "https")
                        && url.host_str() == Some("tauri.localhost"))
                        || (url.scheme() == "tauri" && url.host_str() == Some("localhost"));
                    let development = cfg!(debug_assertions)
                        && url.scheme() == "http"
                        && url.host_str() == Some("127.0.0.1")
                        && url.port() == Some(5173);
                    production || development
                })
                .build()?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("无法启动 FineSub 审核客户端");
}
