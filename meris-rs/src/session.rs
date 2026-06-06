//! Session persistence — parity with meris.harness.sessions (P5-4 M1).

use chrono::Utc;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::SystemTime;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionRecord {
    pub id: String,
    pub task: String,
    pub mode: String,
    #[serde(default = "default_status")]
    pub status: String,
    #[serde(default = "now_iso")]
    pub created_at: String,
    #[serde(default = "now_iso")]
    pub updated_at: String,
    #[serde(default)]
    pub messages: Vec<Value>,
    #[serde(default)]
    pub turn: u32,
    #[serde(default = "default_max_turns")]
    pub max_turns: u32,
    #[serde(default)]
    pub workspace: String,
}

fn default_status() -> String {
    "running".into()
}

fn default_max_turns() -> u32 {
    30
}

pub fn now_iso() -> String {
    Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string()
}

pub fn new_session_id() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    format!("{:012x}", (nanos as u64) ^ ((nanos >> 48) as u64))
}

pub fn sessions_dir(workspace: &Path) -> PathBuf {
    workspace.join(".meris").join("sessions")
}

pub fn session_path(workspace: &Path, session_id: &str) -> PathBuf {
    sessions_dir(workspace).join(format!("{session_id}.json"))
}

pub fn save_session(workspace: &Path, record: &mut SessionRecord) -> Result<PathBuf, String> {
    record.updated_at = now_iso();
    let dir = sessions_dir(workspace);
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let path = session_path(workspace, &record.id);
    let text = serde_json::to_string_pretty(record).map_err(|e| e.to_string())?;
    fs::write(&path, text).map_err(|e| e.to_string())?;
    Ok(path)
}

pub fn load_session(workspace: &Path, session_id: &str) -> Result<Option<SessionRecord>, String> {
    let path = session_path(workspace, session_id);
    if !path.is_file() {
        return Ok(None);
    }
    let text = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let record: SessionRecord = serde_json::from_str(&text).map_err(|e| e.to_string())?;
    Ok(Some(record))
}

pub fn list_sessions(workspace: &Path) -> Result<Vec<SessionRecord>, String> {
    let dir = sessions_dir(workspace);
    if !dir.is_dir() {
        return Ok(vec![]);
    }
    let mut records: Vec<(SystemTime, SessionRecord)> = Vec::new();
    for entry in fs::read_dir(&dir).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let text = match fs::read_to_string(&path) {
            Ok(t) => t,
            Err(_) => continue,
        };
        let record: SessionRecord = match serde_json::from_str(&text) {
            Ok(r) => r,
            Err(_) => continue,
        };
        let mtime = fs::metadata(&path)
            .ok()
            .and_then(|m| m.modified().ok())
            .unwrap_or_else(SystemTime::now);
        records.push((mtime, record));
    }
    records.sort_by(|a, b| b.0.cmp(&a.0));
    Ok(records.into_iter().map(|(_, r)| r).collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use tempfile::TempDir;

    #[test]
    fn roundtrip_session() {
        let dir = TempDir::new().unwrap();
        let mut rec = SessionRecord {
            id: new_session_id(),
            task: "hello".into(),
            mode: "ask".into(),
            status: "running".into(),
            created_at: now_iso(),
            updated_at: now_iso(),
            messages: vec![json!({"role": "user", "content": "hi"})],
            turn: 0,
            max_turns: 5,
            workspace: dir.path().to_string_lossy().into(),
        };
        save_session(dir.path(), &mut rec).unwrap();
        let loaded = load_session(dir.path(), &rec.id).unwrap().unwrap();
        assert_eq!(loaded.task, "hello");
        assert_eq!(loaded.messages.len(), 1);
    }
}
