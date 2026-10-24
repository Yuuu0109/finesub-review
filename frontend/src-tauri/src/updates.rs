use crate::portable;
use serde::Serialize;
use std::{sync::{Mutex, atomic::{AtomicBool, Ordering}}, time::Duration};
use tauri::{ipc::Channel, AppHandle, Manager, State};
use tauri_plugin_updater::{Update, UpdaterExt};
use url::Url;

#[derive(Default)]
pub struct PendingUpdate {
    inner: Mutex<UpdateState>,
    busy: AtomicBool,
}
#[derive(Default)]
struct UpdateState {
    available: Option<Update>,
    ready: Option<VerifiedPortable>,
}
#[derive(Clone)]
struct VerifiedPortable {
    info: UpdateInfo,
    bytes: Vec<u8>,
}
struct Operation<'a>(&'a AtomicBool);
impl Drop for Operation<'_> {
    fn drop(&mut self) { self.0.store(false, Ordering::Release); }
}
impl PendingUpdate {
    fn begin(&self) -> Result<Operation<'_>, String> {
        self.busy.compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
            .map_err(|_| "已有更新操作正在进行".to_string())?;
        Ok(Operation(&self.busy))
    }
}

#[derive(Clone, Serialize)]
pub struct UpdateInfo { version: String, notes: String, prepared: bool }
#[derive(Clone, Serialize)]
pub struct Progress { downloaded: u64, total: Option<u64> }

fn trusted_download(url: &Url, version: &str) -> bool {
    url.scheme() == "https" && url.host_str() == Some("github.com")
        && url.port_or_known_default() == Some(443)
        && url.username().is_empty() && url.password().is_none()
        && url.path() == format!("/Yuuu0109/finesub-review/releases/download/v{version}/finesub-review-{version}-windows-x64-portable.exe")
        && url.query().is_none() && url.fragment().is_none()
}

#[tauri::command]
pub async fn check_desktop_update(app: AppHandle, state: State<'_, PendingUpdate>) -> Result<Option<UpdateInfo>, String> {
    let _operation = state.begin()?;
    {
        let mut inner = state.inner.lock().map_err(|_| "更新状态不可用")?;
        if let Some(ready) = &inner.ready { return Ok(Some(ready.info.clone())); }
        inner.available = None;
    }
    let result = app.updater_builder().target("windows-x86_64-portable")
        .timeout(Duration::from_secs(120)).build().map_err(|e| e.to_string())?
        .check().await.map_err(|_| "更新源暂不可用，请稍后重试；尚未发布更新清单时也会出现此提示")?;
    if let Some(update) = result {
        if !trusted_download(&update.download_url, &update.version) {
            return Err("更新包地址或版本与官方免安装发布不一致".into());
        }
        let info = UpdateInfo { version: update.version.clone(), notes: update.body.clone().unwrap_or_default(), prepared: false };
        state.inner.lock().map_err(|_| "更新状态不可用")?.available = Some(update);
        Ok(Some(info))
    } else { Ok(None) }
}

#[tauri::command]
pub async fn download_desktop_update(state: State<'_, PendingUpdate>, version: String, on_progress: Channel<Progress>) -> Result<(), String> {
    let _operation = state.begin()?;
    let update = state.inner.lock().map_err(|_| "更新状态不可用")?.available.take().ok_or("请先重新检查更新")?;
    if update.version != version { return Err("待下载版本已变化，请重新检查更新".into()); }
    let mut downloaded = 0;
    // The official updater verifies the signature before returning any usable bytes.
    let bytes = update.download(|chunk, total| {
        downloaded += chunk as u64;
        let _ = on_progress.send(Progress { downloaded, total });
    }, || {}).await.map_err(|_| "下载或签名校验失败，请重新检查后重试。当前程序未改变")?;
    portable::validate(&bytes)?;
    state.inner.lock().map_err(|_| "更新状态不可用")?.ready = Some(VerifiedPortable {
        info: UpdateInfo { version, notes: update.body.unwrap_or_default(), prepared: true }, bytes,
    });
    Ok(())
}

#[tauri::command]
pub async fn apply_desktop_update(app: AppHandle, state: State<'_, PendingUpdate>) -> Result<(), String> {
    let _operation = state.begin()?;
    let ready = state.inner.lock().map_err(|_| "更新状态不可用")?.ready.clone().ok_or("请先下载并校验更新")?;
    // Cache the original path before self-replace moves the running image.
    let original = tauri::process::current_binary(&app.env()).map_err(|e| e.to_string())?;
    tauri::async_runtime::spawn_blocking(move || {
        portable::replace_verified(&original, &ready.bytes, |path| self_replace::self_replace(path))?;
        app.restart();
        #[allow(unreachable_code)]
        Ok::<(), String>(())
    }).await.map_err(|e| e.to_string())?
}

#[tauri::command]
pub fn save_desktop_update(app: AppHandle, state: State<'_, PendingUpdate>) -> Result<String, String> {
    let _operation = state.begin()?;
    let inner = state.inner.lock().map_err(|_| "更新状态不可用")?;
    let ready = inner.ready.as_ref().ok_or("请先下载并校验更新")?;
    let directory = app.path().download_dir().map_err(|e| e.to_string())?;
    portable::save_download(&directory, &ready.info.version, &ready.bytes)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn restricts_release_downloads_to_the_signed_portable_version() {
        let good = "https://github.com/Yuuu0109/finesub-review/releases/download/v0.3.0/finesub-review-0.3.0-windows-x64-portable.exe";
        assert!(trusted_download(&Url::parse(good).unwrap(), "0.3.0"));
        for value in [good.replace("https:", "http:"), good.replace("github.com", "github.com.evil.test"),
            good.replace("Yuuu0109", "other"), good.replace("-portable.exe", "-setup.exe"),
            good.replace("github.com/", "github.com:8443/"), format!("{good}?token=secret")] {
            assert!(!trusted_download(&Url::parse(&value).unwrap(), "0.3.0"));
        }
        assert!(!trusted_download(&Url::parse(good).unwrap(), "0.4.0"));
    }
    #[test]
    fn concurrent_update_operations_are_rejected_then_released() {
        let state = PendingUpdate::default();
        let first = state.begin().unwrap();
        assert!(state.begin().is_err());
        drop(first);
        assert!(state.begin().is_ok());
    }
}
