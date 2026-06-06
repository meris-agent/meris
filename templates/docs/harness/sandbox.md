# Bash 沙箱（Phase E3）

```yaml
sandbox:
  mode: warn
  osSandbox: auto      # Linux bwrap
  network: shared      # shared | isolated
  maskSecrets: true     # hide .env from bash
```

Linux/WSL：`sudo apt install bubblewrap` · Windows 原生请用 WSL（`meris doctor` 会检测）。

详见 [docs/harness/sandbox.md](../../docs/harness/sandbox.md)。
