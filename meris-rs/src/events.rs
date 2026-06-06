//! JSONL event stream — parity with meris.harness.protocol.EventStream (P5-4 M4).

use serde_json::{json, Value};
use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

pub struct EventStream {
    sink: Option<File>,
}

impl EventStream {
    pub fn open(path: &Path) -> Result<Self, String> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .map_err(|e| e.to_string())?;
        Ok(EventStream { sink: Some(file) })
    }

    fn now_ts() -> f64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64()
    }

    pub fn emit(&mut self, kind: &str, message: &str, fields: &HashMap<String, Value>) {
        let Some(file) = self.sink.as_mut() else {
            return;
        };
        let mut data = json!({
            "type": "event",
            "ts": Self::now_ts(),
            "kind": kind,
        });
        if !message.is_empty() {
            data["message"] = json!(message);
        }
        if let Some(obj) = data.as_object_mut() {
            for (k, v) in fields {
                obj.insert(k.clone(), v.clone());
            }
        }
        let line = serde_json::to_string(&data).unwrap_or_else(|_| "{}".into());
        let _ = writeln!(file, "{line}");
        let _ = file.flush();
    }

    pub fn emit_simple(&mut self, kind: &str, message: &str) {
        self.emit(kind, message, &HashMap::new());
    }
}

pub fn emit_submission(stream: &mut Option<EventStream>, action: &str, task: &str, session: &str) {
    if let Some(s) = stream.as_mut() {
        let mut fields = HashMap::new();
        fields.insert("action".into(), json!(action));
        fields.insert("task".into(), json!(&task[..task.len().min(500)]));
        fields.insert("session".into(), json!(session));
        s.emit("submission", action, &fields);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn writes_jsonl_line() {
        let dir = TempDir::new().unwrap();
        let path = dir.path().join("events.jsonl");
        let mut es = EventStream::open(&path).unwrap();
        es.emit_simple("done", "ok");
        let text = std::fs::read_to_string(path).unwrap();
        assert!(text.contains("\"kind\":\"done\""));
    }
}
