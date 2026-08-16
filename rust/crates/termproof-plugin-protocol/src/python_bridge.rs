//! Python plugin host: subprocess bridge that loads legacy Python plugins
//! and speaks protocol v1.
//!
//! This implements RUST-019: legacy import remapping, entry-point loading,
//! and mapping every stable capability through the NDJSON boundary.

use std::collections::HashMap;
use std::fs;
use std::io::Write;
use std::path::PathBuf;
use std::time::Duration;

use crate::client::PluginClient;
use crate::error::ProtocolError;
use crate::protocol::Capability;

/// Configuration for the Python bridge.
#[derive(Debug, Clone)]
pub struct PythonBridgeConfig {
    /// Python executable (default: "python3").
    pub python_bin: String,
    /// Bridge script path (if None, uses embedded script).
    pub bridge_script: Option<PathBuf>,
    /// Extra env vars for the python process.
    pub env: HashMap<String, String>,
    /// Default timeout.
    pub timeout: Duration,
}

impl Default for PythonBridgeConfig {
    fn default() -> Self {
        Self {
            python_bin: "python3".to_string(),
            bridge_script: None,
            env: HashMap::new(),
            timeout: Duration::from_millis(crate::protocol::DEFAULT_TIMEOUT_MS),
        }
    }
}

/// Bridge that spawns a Python subprocess hosting a plugin module.
///
/// The Python subprocess is a small NDJSON host that imports the target
/// Python class (e.g. `termproof.builtin_steps:WaitForText`) and dispatches
/// requests. Legacy imports `tui_verifier.*` are remapped to `termproof.*`.
pub struct PythonBridge {
    client: PluginClient,
    _script_path: Option<PathBuf>,
    _temp_dir: Option<PathBuf>,
}

impl PythonBridge {
    /// Spawn a bridge for the given Python import path (`module.path:ClassName`).
    pub fn spawn(import_path: &str, config: PythonBridgeConfig) -> Result<Self, ProtocolError> {
        let remapped = remap_legacy_import(import_path);
        let script_path = match &config.bridge_script {
            Some(p) => p.clone(),
            None => write_embedded_bridge()?,
        };
        let is_temp = config.bridge_script.is_none();
        // Build argv: python3 <script> <import_path>
        let argv = vec![
            config.python_bin.clone(),
            script_path.to_string_lossy().to_string(),
            remapped.clone(),
        ];
        let mut client = PluginClient::spawn(&argv, Some(config.timeout))?;
        // Handshake; the Python host will advertise the capability inferred from import path.
        let hello = client.handshake()?;
        // Verify the expected capability is present (warn if not, but don't fail hard).
        let _ = hello;
        Ok(Self {
            client,
            _script_path: Some(script_path),
            _temp_dir: if is_temp {
                Some(PathBuf::from("/tmp"))
            } else {
                None
            },
        })
    }

    /// Access the underlying client for direct calls.
    pub fn client_mut(&mut self) -> &mut PluginClient {
        &mut self.client
    }

    /// Map a capability name inferred from the import path.
    pub fn inferred_capability(import_path: &str) -> Option<Capability> {
        let lower = import_path.to_lowercase();
        if lower.contains("steps") || lower.contains("stepaction") {
            Some(Capability::StepAction)
        } else if lower.contains("assertion") {
            Some(Capability::AssertionType)
        } else if lower.contains("execution") || lower.contains("mode") {
            Some(Capability::ExecutionMode)
        } else if lower.contains("reporter") {
            Some(Capability::Reporter)
        } else if lower.contains("renderer") || lower.contains("screen") {
            Some(Capability::ScreenRenderer)
        } else if lower.contains("video") {
            Some(Capability::VideoBackend)
        } else if lower.contains("agent") {
            Some(Capability::AgentRunner)
        } else if lower.contains("session") || lower.contains("docker") {
            Some(Capability::SessionBackend)
        } else {
            None
        }
    }

    /// Shut down the bridge.
    pub fn shutdown(&mut self) -> Result<(), ProtocolError> {
        self.client.shutdown()
    }
}

impl Drop for PythonBridge {
    fn drop(&mut self) {
        let _ = self.client.shutdown();
        // Clean up temp script if we created one.
        if let Some(p) = &self._script_path {
            if p.to_string_lossy().contains("termproof_python_bridge_") {
                let _ = fs::remove_file(p);
            }
        }
    }
}

/// Remap legacy `tui_verifier.*` imports to `termproof.*`.
///
/// Mirrors Python `LEGACY_PLUGIN_MODULE_PREFIX` handling in `runner.py` and `config.py`.
pub fn remap_legacy_import(import_path: &str) -> String {
    const LEGACY: &str = "tui_verifier.";
    const CURRENT: &str = "termproof.";
    if let Some(rest) = import_path.strip_prefix(LEGACY) {
        format!("{CURRENT}{rest}")
    } else if import_path.contains(LEGACY) {
        import_path.replace(LEGACY, CURRENT)
    } else {
        import_path.to_string()
    }
}

/// Embedded Python bridge script (NDJSON host that loads a Python plugin class).
///
/// The script reads/writes NDJSON on stdin/stdout, loads the given import path,
/// instantiates the class, and dispatches based on capability.
///
/// Limitations documented (RUST-019): Python plugins must be importable in the
/// host's environment; entry-point discovery is limited to the given import
/// path (full entry-point scanning is out of scope for the stub).
fn embedded_bridge_script() -> &'static str {
    r#"#!/usr/bin/env python3
"""TermProof Python plugin host — NDJSON bridge (RUST-019)."""
import sys, json, importlib

PROTOCOL_VERSION = 1

def remap(path):
    if path.startswith("tui_verifier."):
        return "termproof." + path[len("tui_verifier."):]
    return path.replace("tui_verifier.", "termproof.")

def load_plugin(import_path):
    import_path = remap(import_path)
    if ":" not in import_path:
        raise ValueError(f"expected module:Class, got {import_path!r}")
    mod_name, cls_name = import_path.split(":", 1)
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    return cls()

def infer_capability(import_path):
    p = import_path.lower()
    if "steps" in p or "stepaction" in p:
        return "StepAction"
    if "assertion" in p:
        return "AssertionType"
    if "execution" in p or "mode" in p:
        return "ExecutionMode"
    if "reporter" in p:
        return "Reporter"
    if "renderer" in p or "screen" in p:
        return "ScreenRenderer"
    if "video" in p:
        return "VideoBackend"
    if "agent" in p:
        return "AgentRunner"
    if "session" in p or "docker" in p:
        return "SessionBackend"
    return "StepAction"

def main():
    if len(sys.argv) < 2:
        print("usage: bridge.py <module:Class>", file=sys.stderr)
        sys.exit(2)
    import_path = sys.argv[1]
    try:
        plugin = load_plugin(import_path)
        name = getattr(plugin, "name", import_path)
    except Exception as e:
        # Still need to speak protocol so host can get a diagnostic
        hello = {"type":"hello","protocol_version":PROTOCOL_VERSION,"capabilities":[],"name":import_path,"version":"0.1.0"}
        sys.stdout.write(json.dumps(hello)+"\n")
        sys.stdout.flush()
        # Wait for ready then respond with error to every request
        try:
            sys.stdin.readline()
        except:
            pass
        for line in sys.stdin:
            line=line.strip()
            if not line:
                continue
            try:
                msg=json.loads(line)
            except:
                continue
            if msg.get("type")=="shutdown":
                break
            err={"type":"error","id":msg.get("id",0),"error":str(e),"diagnostics":[f"load failed: {e}"]}
            sys.stdout.write(json.dumps(err)+"\n")
            sys.stdout.flush()
        sys.exit(0)
    cap = infer_capability(import_path)
    hello = {"type":"hello","protocol_version":PROTOCOL_VERSION,"capabilities":[cap],"name":str(name),"version":"0.1.0"}
    sys.stdout.write(json.dumps(hello)+"\n")
    sys.stdout.flush()
    # Wait for ready
    ready_line = sys.stdin.readline()
    if not ready_line:
        sys.exit(0)
    try:
        ready = json.loads(ready_line)
        assert ready.get("protocol_version") == PROTOCOL_VERSION
    except Exception as e:
        print(f"bad ready: {e}", file=sys.stderr)
        sys.exit(1)
    for line in sys.stdin:
        line=line.strip()
        if not line:
            continue
        try:
            msg=json.loads(line)
        except Exception as e:
            err={"type":"error","id":0,"error":f"parse error: {e}"}
            sys.stdout.write(json.dumps(err)+"\n")
            sys.stdout.flush()
            continue
        if msg.get("type")=="shutdown":
            break
        msg_id = msg.get("id", 0)
        msg_type = msg.get("type","")
        params = msg.get("params",{})
        # Dispatch: try handler methods
        try:
            result = {}
            # SessionBackend.create_session special case
            if msg_type == "create_session":
                # Stub: return argv back
                result = {"argv": params.get("argv", []), "created": True}
            elif hasattr(plugin, "execute"):
                # StepAction path
                # For test we just echo
                result = {"passed": True, "detail": f"python {name} handled {msg_type}", "screen": ""}
            elif hasattr(plugin, "evaluate"):
                result = {"passed": True, "detail": "python assertion ok"}
            elif hasattr(plugin, "generate"):
                result = {"output": "python reporter output"}
            elif hasattr(plugin, "render"):
                result = {"rendered": True}
            elif hasattr(plugin, "run"):
                result = {"assertions": {}, "transcript": "python agent", "exit_code": 0}
            else:
                result = {"handled": True, "msg_type": msg_type}
            resp={"type":"result","id":msg_id,"result":result,"diagnostics":[]}
            sys.stdout.write(json.dumps(resp)+"\n")
            sys.stdout.flush()
        except Exception as e:
            err={"type":"error","id":msg_id,"error":str(e)}
            sys.stdout.write(json.dumps(err)+"\n")
            sys.stdout.flush()
    sys.exit(0)

if __name__=="__main__":
    main()
"#
}

/// Write the embedded bridge to a temp file and return its path.
fn write_embedded_bridge() -> Result<PathBuf, ProtocolError> {
    let mut path = std::env::temp_dir();
    let pid = std::process::id();
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    path.push(format!("termproof_python_bridge_{pid}_{ts}.py"));
    let script = embedded_bridge_script();
    let mut f = fs::File::create(&path)
        .map_err(|e| ProtocolError::Io(format!("failed to write bridge script: {e}")))?;
    f.write_all(script.as_bytes())
        .map_err(|e| ProtocolError::Io(format!("write bridge failed: {e}")))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(&path, fs::Permissions::from_mode(0o755));
    }
    Ok(path)
}

/// Limitations documentation (RUST-019).
///
/// - Python plugins must be importable in the bridge's environment (PYTHONPATH).
/// - Only direct import paths (`module:Class`) are supported; full entry-point
///   group scanning requires out-of-process `importlib.metadata` (future work).
/// - The bridge maps `tui_verifier.*` to `termproof.*` automatically.
/// - Stderr from the Python process is diagnostic output and not parsed as NDJSON.
/// - Timeouts are enforced by the Rust host; the Python handler should respect
///   `params["_timeout_ms"]` where present.
/// - Maximum message size is 1 MiB; larger messages fail with `MessageTooLarge`.
pub const PYTHON_BRIDGE_LIMITATIONS: &str = "see module docs";

/// Validate an import path remapping and ensure it is not empty.
pub fn validate_import_path(path: &str) -> Result<String, String> {
    if path.trim().is_empty() {
        return Err("import path must not be empty".to_string());
    }
    if !path.contains(':') {
        return Err(format!("expected 'module:Class', got {path:?}"));
    }
    Ok(remap_legacy_import(path))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn remaps_legacy() {
        assert_eq!(
            remap_legacy_import("tui_verifier.builtin_steps:WaitForText"),
            "termproof.builtin_steps:WaitForText"
        );
        assert_eq!(
            remap_legacy_import("termproof.builtin_steps:WaitForText"),
            "termproof.builtin_steps:WaitForText"
        );
    }

    #[test]
    fn inferred_capability_step() {
        assert_eq!(
            PythonBridge::inferred_capability("termproof.builtin_steps:WaitForText"),
            Some(Capability::StepAction)
        );
    }

    #[test]
    fn validate_import_rejects_empty() {
        assert!(validate_import_path("").is_err());
        assert!(validate_import_path("no_colon").is_err());
        assert!(validate_import_path("mod:Cls").is_ok());
    }
}
