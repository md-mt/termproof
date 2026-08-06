//! Configuration types mirroring Python `config.py`.

use std::collections::HashMap;

/// Docker backend configuration.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DockerBackendConfig {
    /// Docker image.
    pub image: String,
    /// Working directory inside the container.
    pub workdir: String,
    /// Volume specs.
    pub volumes: Vec<String>,
    /// Extra env.
    pub env: HashMap<String, String>,
}

impl Default for DockerBackendConfig {
    fn default() -> Self {
        Self {
            image: String::new(),
            workdir: "/workspace".to_string(),
            volumes: vec![".:/workspace".to_string()],
            env: HashMap::new(),
        }
    }
}

/// Global defaults.
#[derive(Debug, Clone, PartialEq)]
pub struct GlobalDefaults {
    /// Default timeout seconds.
    pub timeout_seconds: f64,
    /// Default cols.
    pub cols: u16,
    /// Default rows.
    pub rows: u16,
    /// Default video fps.
    pub video_fps: u32,
    /// Default output dir.
    pub out_dir: String,
}

impl Default for GlobalDefaults {
    fn default() -> Self {
        Self {
            timeout_seconds: 30.0,
            cols: 100,
            rows: 30,
            video_fps: 60,
            out_dir: ".termproof/runs".to_string(),
        }
    }
}
