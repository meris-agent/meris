//! Load `.meris/settings.json` (legacy `.forge/` fallback).

use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

fn harness_settings_path(workspace: &Path) -> std::path::PathBuf {
    let meris = workspace.join(".meris").join("settings.json");
    if meris.is_file() {
        return meris;
    }
    workspace.join(".forge").join("settings.json")
}

pub fn load_settings(workspace: &Path) -> HashMap<String, Value> {
    let path = harness_settings_path(workspace);
    if !path.is_file() {
        return HashMap::new();
    }
    let text = fs::read_to_string(&path).unwrap_or_default();
    serde_json::from_str(&text).unwrap_or_default()
}
