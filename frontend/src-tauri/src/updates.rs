use serde::Serialize;
use std::{sync::Mutex, time::Duration};
use tauri::{ipc::Channel, AppHandle, State};
use tauri_plugin_updater::{Update, UpdaterExt};
use url::Url;

#[derive(Default)]
pub struct PendingUpdate(Mutex<Option<Update>>);

#[derive(Serialize)]
pub struct UpdateInfo {
    version: String,
    notes: String,
}

#[derive(Clone, Serialize)]
pub struct Progress {
    downloaded: u64,
    total: Option<u64>,
}

fn update_endpoint(server: &str) -> Result<Url, String> {
    let mut url = Url::parse(server).map_err(|_| "服务器地址无效")?;
    if url.scheme() != "https" || !url.username().is_empty() || url.password().is_some()
        || url.path() != "/" || url.query().is_some() || url.fragment().is_some()
    {
        return Err("更新服务必须使用 HTTPS 服务器根地址".into());
    }
    url.set_path("/api/desktop/updates/latest.json");
    Ok(url)
}

#[tauri::command]
pub async fn check_desktop_update(app: AppHandle, state: State<'_, PendingUpdate>, server: String) -> Result<Option<UpdateInfo>, String> {
    *state.0.lock().map_err(|_| "更新状态不可用")? = None;
    let endpoint = update_endpoint(&server)?;
    let result = app.updater_builder()
        .endpoints(vec![endpoint.clone()]).map_err(|e| e.to_string())?
        .timeout(Duration::from_secs(120))
        .build().map_err(|e| e.to_string())?
        .check().await.map_err(|_| "无法检查更新，请确认服务器已部署更新接口及更新包")?;
    if let Some(update) = result {
        // No credentials or private GitHub tokens are sent. Only our server can host the installer.
        if update.download_url.scheme() != "https" || update.download_url.origin() != endpoint.origin() {
            return Err("更新包地址必须与审核服务器同源并使用 HTTPS".into());
        }
        let info = UpdateInfo { version: update.version.clone(), notes: update.body.clone().unwrap_or_default() };
        *state.0.lock().map_err(|_| "更新状态不可用")? = Some(update);
        Ok(Some(info))
    } else {
        Ok(None)
    }
}

#[tauri::command]
pub async fn install_desktop_update(state: State<'_, PendingUpdate>, version: String, on_progress: Channel<Progress>) -> Result<(), String> {
    let update = state.0.lock().map_err(|_| "更新状态不可用")?.take().ok_or("请先重新检查更新")?;
    if update.version != version {
        return Err("待安装版本已变化，请重新检查更新".into());
    }
    let mut downloaded = 0;
    // The official updater verifies the signed bytes before invoking NSIS, then restarts on Windows.
    update.download_and_install(|chunk, total| {
        downloaded += chunk as u64;
        let _ = on_progress.send(Progress { downloaded, total });
    }, || {}).await.map_err(|e| format!("更新未完成，请重新检查后重试：{e}"))
}

#[cfg(test)]
mod tests {
    use super::update_endpoint;
    #[test]
    fn requires_https_origin() {
        assert_eq!(update_endpoint("https://review.example.com").unwrap().as_str(), "https://review.example.com/api/desktop/updates/latest.json");
        for value in ["http://review.example.com", "https://user:pass@example.com", "https://example.com/api", "https://example.com?key=x", "https://example.com/#x"] {
            assert!(update_endpoint(value).is_err());
        }
    }
}
