//! Load `.meris/settings.{yaml,yml,json}` with optional local override.

use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

const SHARED: &[&str] = &["settings.yaml", "settings.yml", "settings.json"];
const LOCAL: &[&str] = &[
    "settings.local.yaml",
    "settings.local.yml",
    "settings.local.json",
];

fn first_existing(dir: &Path, names: &[&str]) -> Option<PathBuf> {
    names
        .iter()
        .map(|n| dir.join(n))
        .find(|p| p.is_file())
}

fn load_file(path: &Path) -> HashMap<String, Value> {
    let text = fs::read_to_string(path).unwrap_or_default();
    if path.extension().and_then(|e| e.to_str()) == Some("json") {
        return serde_json::from_str(&text).unwrap_or_default();
    }
    serde_yaml::from_str(&text).unwrap_or_default()
}

fn deep_merge(base: HashMap<String, Value>, override_map: HashMap<String, Value>) -> HashMap<String, Value> {
    let mut out = base;
    for (key, val) in override_map {
        match (out.get(&key), &val) {
            (Some(Value::Object(a)), Value::Object(b)) => {
                let mut merged = a.clone();
                for (k, v) in b {
                    merged.insert(k.clone(), v.clone());
                }
                out.insert(key, Value::Object(merged));
            }
            _ => {
                out.insert(key, val);
            }
        }
    }
    out
}

pub fn load_settings(workspace: &Path) -> HashMap<String, Value> {
    let hroot = workspace.join(".meris");
    let mut merged = HashMap::new();
    if let Some(shared) = first_existing(&hroot, SHARED) {
        merged = load_file(&shared);
    }
    if let Some(local) = first_existing(&hroot, LOCAL) {
        merged = deep_merge(merged, load_file(&local));
    }
    merged
}
