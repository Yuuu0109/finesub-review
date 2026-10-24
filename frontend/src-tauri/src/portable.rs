//! Verified bytes are passed from the updater, never a path supplied by the UI.
use std::{fs, io::{self, Write}, path::Path};

pub fn validate(bytes: &[u8]) -> Result<(), String> {
    if bytes.len() < 64 || bytes.len() > 256 * 1024 * 1024 || !bytes.starts_with(b"MZ") {
        return Err("更新程序格式无效".into());
    }
    let offset = u32::from_le_bytes(bytes[60..64].try_into().unwrap()) as usize;
    let header = bytes.get(offset..offset.saturating_add(26)).ok_or("更新程序头部不完整")?;
    if &header[..4] != b"PE\0\0" || header[4..6] != [0x64, 0x86] || header[24..26] != [0x0b, 0x02] {
        return Err("更新包不是 Windows x64 程序".into());
    }
    Ok(())
}

pub fn save_download(directory: &Path, version: &str, bytes: &[u8]) -> Result<String, String> {
    validate(bytes)?;
    if version.is_empty() || version.len() > 80 || !version.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | '+')) {
        return Err("更新版本无效".into());
    }
    for index in 0..100 {
        let suffix = if index == 0 { String::new() } else { format!("-{index}") };
        let path = directory.join(format!("FineSub-Review-{version}{suffix}-portable.exe"));
        match fs::OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(mut file) => {
                if let Err(error) = file.write_all(bytes).and_then(|_| file.sync_all()) {
                    drop(file);
                    let _ = fs::remove_file(&path);
                    return Err(format!("无法保存更新程序：{error}"));
                }
                return Ok(path.to_string_lossy().into_owned());
            }
            Err(error) if error.kind() == io::ErrorKind::AlreadyExists => continue,
            Err(error) => return Err(format!("无法保存到下载目录：{error}")),
        }
    }
    Err("下载目录中已有过多同版本文件，请整理后重试".into())
}

pub fn replace_verified(original: &Path, bytes: &[u8], replace: impl FnOnce(&Path) -> io::Result<()>) -> Result<(), String> {
    validate(bytes)?;
    let parent = original.parent().ok_or("无法确定程序所在目录")?;
    // Preflight writable space before allowing the library to rename the running EXE.
    let mut candidate = tempfile::Builder::new().prefix(".finesub-update-").suffix(".exe").tempfile_in(parent)
        .map_err(|e| format!("程序目录不可写，可另存新版：{e}"))?;
    candidate.write_all(bytes).and_then(|_| candidate.as_file().sync_all()).map_err(|e| format!("写入更新失败：{e}"))?;
    let mut backup = tempfile::Builder::new().prefix(".finesub-rollback-").suffix(".exe").tempfile_in(parent).map_err(|e| e.to_string())?;
    io::copy(&mut fs::File::open(original).map_err(|e| e.to_string())?, &mut backup)
        .and_then(|_| backup.as_file().sync_all()).map_err(|e| format!("备份当前程序失败：{e}"))?;
    // Close the candidate handle before self-replace copies it on Windows.
    let candidate = candidate.into_temp_path();
    if let Err(error) = replace(&candidate) {
        // A failed copy may leave a partial EXE at the original path.
        let unchanged = fs::read(original).ok().zip(fs::read(backup.path()).ok())
            .is_some_and(|(current, saved)| current == saved);
        if !unchanged {
            if let Err(restore) = fs::copy(backup.path(), original) {
                let (_, path) = backup.keep().map_err(|e| format!("更新失败，保留恢复文件失败：{e}"))?;
                return Err(format!("更新未完成：{error}；恢复失败：{restore}。旧程序保存在 {}", path.display()));
            }
        }
        return Err(format!("未能替换当前程序，可重试或另存新版：{error}"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    pub fn executable() -> Vec<u8> {
        let mut bytes = vec![0; 128];
        bytes[..2].copy_from_slice(b"MZ");
        bytes[60..64].copy_from_slice(&64u32.to_le_bytes());
        bytes[64..68].copy_from_slice(b"PE\0\0");
        bytes[68..70].copy_from_slice(&[0x64, 0x86]);
        bytes[88..90].copy_from_slice(&[0x0b, 0x02]);
        bytes
    }
    #[test]
    fn rejects_truncated_wrong_architecture_and_path_versions() {
        assert!(validate(b"MZbad").is_err());
        let mut wrong = executable(); wrong[68] = 0x4c;
        assert!(validate(&wrong).is_err());
        let dir = tempfile::tempdir().unwrap();
        assert!(save_download(dir.path(), "../bad", &executable()).is_err());
        let first = save_download(dir.path(), "0.2.5", &executable()).unwrap();
        let second = save_download(dir.path(), "0.2.5", &executable()).unwrap();
        assert_ne!(first, second);
        assert_eq!(fs::read(first).unwrap(), executable());
    }
    #[test]
    fn recovers_original_if_replacement_fails_after_rename() {
        let dir = tempfile::tempdir().unwrap();
        let original = dir.path().join("review.exe");
        fs::write(&original, b"old executable").unwrap();
        let result = replace_verified(&original, &executable(), |_| {
            fs::remove_file(&original)?;
            Err(io::Error::new(io::ErrorKind::PermissionDenied, "simulated locked destination"))
        });
        assert!(result.is_err());
        assert_eq!(fs::read(&original).unwrap(), b"old executable");
        assert_eq!(fs::read_dir(dir.path()).unwrap().count(), 1);
    }
    #[test]
    fn stages_exact_verified_bytes_and_cleans_its_temporary_files() {
        let dir = tempfile::tempdir().unwrap();
        let original = dir.path().join("review.exe");
        fs::write(&original, b"old executable").unwrap();
        replace_verified(&original, &executable(), |candidate| {
            fs::copy(candidate, &original).map(|_| ())
        }).unwrap();
        assert_eq!(fs::read(original).unwrap(), executable());
        assert_eq!(fs::read_dir(dir.path()).unwrap().count(), 1);
    }
    #[test]
    fn restores_original_if_failed_copy_leaves_a_partial_executable() {
        let dir = tempfile::tempdir().unwrap();
        let original = dir.path().join("review.exe");
        fs::write(&original, b"old executable").unwrap();
        assert!(replace_verified(&original, &executable(), |_| {
            fs::write(&original, b"partial update")?;
            Err(io::Error::new(io::ErrorKind::Other, "simulated disk full"))
        }).is_err());
        assert_eq!(fs::read(original).unwrap(), b"old executable");
        assert_eq!(fs::read_dir(dir.path()).unwrap().count(), 1);
    }
}
