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

fn trusted_download(url: &Url) -> bool {
    url.scheme() == "https" && url.host_str() == Some("github.com")
        && url.port_or_known_default() == Some(443)
        && url.username().is_empty() && url.password().is_none()
        && url.path().starts_with("/Yuuu0109/finesub-review/releases/download/")
        && url.query().is_none() && url.fragment().is_none()
}

#[tauri::command]
pub async fn check_desktop_update(app: AppHandle, state: State<'_, PendingUpdate>) -> Result<Option<UpdateInfo>, String> {
    *state.0.lock().map_err(|_| "更新状态不可用")? = None;
    let result = app.updater_builder()
        .timeout(Duration::from_secs(120))
        .build().map_err(|e| e.to_string())?
        .check().await.map_err(|_| "无法连接 GitHub 更新服务，请检查网络后重试")?;
    if let Some(update) = result {
        // Release downloads are public; review-server credentials are never sent here.
        if !trusted_download(&update.download_url) {
            return Err("更新包地址不属于官方 GitHub Release".into());
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
    use super::{trusted_download, Url};
    #[test]
    fn restricts_release_downloads() {
        assert!(trusted_download(&Url::parse("https://github.com/Yuuu0109/finesub-review/releases/download/v0.2.0/app.exe").unwrap()));
        for value in ["http://github.com/Yuuu0109/finesub-review/releases/download/v1/app.exe", "https://github.com/other/repo/releases/download/v1/app.exe", "https://github.com.evil.test/Yuuu0109/finesub-review/releases/download/v1/app.exe", "https://user:pass@github.com/Yuuu0109/finesub-review/releases/download/v1/app.exe", "https://github.com:8443/Yuuu0109/finesub-review/releases/download/v1/app.exe"] {
            assert!(!trusted_download(&Url::parse(value).unwrap()));
        }
    }
}
