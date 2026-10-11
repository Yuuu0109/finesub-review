use serde::Serialize;
use std::{fs::OpenOptions, io::Write, path::Path, sync::Mutex, time::Duration};
use tauri::{ipc::Channel, AppHandle, Manager, State};
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
        .target("windows-x86_64-portable")
        .timeout(Duration::from_secs(120))
        .build().map_err(|e| e.to_string())?
        .check().await.map_err(|_| "无法连接 GitHub 更新服务，请检查网络后重试")?;
    if let Some(update) = result {
        // Release downloads are public; review-server credentials are never sent here.
        if !trusted_download(&update.download_url) || !update.download_url.path().ends_with("-portable.exe") {
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
pub async fn download_desktop_update(app: AppHandle, state: State<'_, PendingUpdate>, version: String, on_progress: Channel<Progress>) -> Result<String, String> {
    let update = state.0.lock().map_err(|_| "更新状态不可用")?.take().ok_or("请先重新检查更新")?;
    if update.version != version {
        return Err("待下载版本已变化，请重新检查更新".into());
    }
    let mut downloaded = 0;
    // Download verifies the signature. Never invoke an installer for the portable client.
    let bytes = update.download(|chunk, total| {
        downloaded += chunk as u64;
        let _ = on_progress.send(Progress { downloaded, total });
    }, || {}).await.map_err(|e| format!("下载未完成，请重新检查后重试：{e}"))?;
    let directory = app.path().download_dir().map_err(|e| e.to_string())?;
    save_portable(&directory, &version, &bytes)
}

fn save_portable(directory: &Path, version: &str, bytes: &[u8]) -> Result<String, String> {
    if !bytes.starts_with(b"MZ") || !version.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | '+')) {
        return Err("更新程序格式无效".into());
    }
    for index in 0..100 {
        let suffix = if index == 0 { String::new() } else { format!("-{index}") };
        let path = directory.join(format!("FineSub-Review-{version}{suffix}-portable.exe"));
        match OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(mut file) => {
                if let Err(error) = file.write_all(bytes).and_then(|_| file.sync_all()) {
                    drop(file);
                    let _ = std::fs::remove_file(&path);
                    return Err(format!("无法保存更新程序：{error}"));
                }
                return Ok(path.to_string_lossy().into_owned());
            }
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(error) => return Err(format!("无法保存到下载目录：{error}")),
        }
    }
    Err("下载目录中已有过多同版本文件，请整理后重试".into())
}

#[cfg(test)]
mod tests {
    use super::{save_portable, trusted_download, Url};
    #[test]
    fn preserves_existing_downloads_and_rejects_invalid_files() {
        let dir = std::env::temp_dir().join(format!("finesub-portable-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        assert!(save_portable(&dir, "../bad", b"MZdata").is_err());
        assert!(save_portable(&dir, "0.2.1", b"not executable").is_err());
        let first = save_portable(&dir, "0.2.1", b"MZfirst").unwrap();
        let second = save_portable(&dir, "0.2.1", b"MZsecond").unwrap();
        assert_ne!(first, second);
        assert_eq!(std::fs::read(&first).unwrap(), b"MZfirst");
        assert_eq!(std::fs::read(&second).unwrap(), b"MZsecond");
        std::fs::remove_file(first).unwrap();
        std::fs::remove_file(second).unwrap();
        std::fs::remove_dir(dir).unwrap();
    }
    #[test]
    fn restricts_release_downloads() {
        assert!(trusted_download(&Url::parse("https://github.com/Yuuu0109/finesub-review/releases/download/v0.2.0/app.exe").unwrap()));
        for value in ["http://github.com/Yuuu0109/finesub-review/releases/download/v1/app.exe", "https://github.com/other/repo/releases/download/v1/app.exe", "https://github.com.evil.test/Yuuu0109/finesub-review/releases/download/v1/app.exe", "https://user:pass@github.com/Yuuu0109/finesub-review/releases/download/v1/app.exe", "https://github.com:8443/Yuuu0109/finesub-review/releases/download/v1/app.exe"] {
            assert!(!trusted_download(&Url::parse(value).unwrap()));
        }
    }
}
