//! Load `.meris/settings.json`.

use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

pub fn load_settings(workspace: &Path) -> HashMap<String, Value> {
    let path = workspace.join(".meris").join("settings.json");
    if !path.is_file() {
        return HashMap::new();
    }
    let text = fs::read_to_string(&path).unwrap_or_default();
    serde_json::from_str(&text).unwrap_or_default()
}
