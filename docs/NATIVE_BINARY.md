# 下载 meris-rs 预编译二进制（无 tag）

> Phase F3-M1 · 不打 tag 也可手动构建

## 方式 A — GitHub Actions（推荐）

1. 打开仓库 **Actions** → workflow **release**
2. **Run workflow**（`workflow_dispatch`）
3. 等待 `build-rust` / `build-python` 完成
4. 在 run 页面下载 artifacts：
   - `meris-rs-x86_64-unknown-linux-gnu`
   - `meris-rs-x86_64-pc-windows-msvc.exe`
   - `meris-rs-x86_64-apple-darwin` / `aarch64-apple-darwin`
5. 将二进制加入 PATH，或放到 `meris-rs/target/release/meris-rs`（开发 tree）

**Windows 一键（需 `gh auth login`）：**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_meris_rs_from_ci.ps1
powershell -ExecutionPolicy Bypass -File scripts\install_meris_rs_from_ci.ps1 -CleanDebug
```

日常 dogfood：跑真实小任务 + `meris ratchet scan`，见 [RATCHET_DESIGN.md](RATCHET_DESIGN.md)。

验证：

```bash
meris-rs version
meris native status
```

## 方式 B — 本地编译

```bash
meris native build
# 或
cd meris-rs && cargo build --release
```

Windows 若被 App Control 拦截，请用 Linux CI artifact 或 WSL。

## 方式 C — pip wheel（Linux 含 bundled 二进制）

Release / `workflow_dispatch` 构建的 **manylinux wheel** 会在 `meris/_bundled/meris-rs` 内附带 Linux 二进制。
安装后无需单独下载：

```bash
pip install meris-agent
meris native status   # binarySource: bundled
```

本地打 wheel 前先 stage：

```bash
meris native build
python scripts/stage_bundled_binary.py --clean
python -m build --wheel
python -m build --sdist   # sdist 不含平台二进制
```

Windows / macOS 的 PyPI wheel 仍建议用方式 A 下载对应 artifact，或本地 `meris native build`（F3-M2 后续可扩展多平台 wheel matrix）。

## 启用 native loop

```bash
set MERIS_NATIVE_LOOP=auto
meris-rs run ask "List top-level files"
```

见 [USER_SETUP.md](USER_SETUP.md) · [harness/testing.md](harness/testing.md)
