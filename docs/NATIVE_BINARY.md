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

## 启用 native loop

```bash
set MERIS_NATIVE_LOOP=auto
meris-rs run ask "List top-level files"
```

见 [USER_SETUP.md](USER_SETUP.md) · [PLAN_PHASE_F.md](PLAN_PHASE_F.md)
