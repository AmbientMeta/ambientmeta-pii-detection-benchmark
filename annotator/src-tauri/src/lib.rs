use serde_json::Value;
use std::fs;
use std::path::PathBuf;

#[tauri::command]
fn load_jsonl(path: String) -> Result<Vec<Value>, String> {
    let content = fs::read_to_string(&path).map_err(|e| format!("Failed to read {}: {}", path, e))?;
    let mut samples = Vec::new();
    for (i, line) in content.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        match serde_json::from_str::<Value>(line) {
            Ok(val) => samples.push(val),
            Err(e) => return Err(format!("Invalid JSON on line {}: {}", i + 1, e)),
        }
    }
    Ok(samples)
}

#[tauri::command]
fn save_jsonl(path: String, samples: Vec<Value>) -> Result<usize, String> {
    let mut lines = Vec::new();
    for sample in &samples {
        lines.push(
            serde_json::to_string(sample).map_err(|e| format!("Serialization error: {}", e))?,
        );
    }
    let content = lines.join("\n") + "\n";
    fs::write(&path, content).map_err(|e| format!("Failed to write {}: {}", path, e))?;
    Ok(samples.len())
}

#[tauri::command]
fn load_state(path: String) -> Result<Value, String> {
    if !PathBuf::from(&path).exists() {
        return Ok(Value::Object(serde_json::Map::new()));
    }
    let content =
        fs::read_to_string(&path).map_err(|e| format!("Failed to read state: {}", e))?;
    serde_json::from_str(&content).map_err(|e| format!("Invalid state JSON: {}", e))
}

#[tauri::command]
fn save_state(path: String, state: Value) -> Result<(), String> {
    // Ensure parent directory exists
    if let Some(parent) = PathBuf::from(&path).parent() {
        fs::create_dir_all(parent)
            .map_err(|e| format!("Failed to create directory: {}", e))?;
    }
    let content =
        serde_json::to_string_pretty(&state).map_err(|e| format!("Serialization error: {}", e))?;
    fs::write(&path, content).map_err(|e| format!("Failed to save state: {}", e))
}

#[tauri::command]
fn export_bio(path: String, content: String) -> Result<(), String> {
    fs::write(&path, content).map_err(|e| format!("Failed to write BIO: {}", e))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            load_jsonl,
            save_jsonl,
            load_state,
            save_state,
            export_bio,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
