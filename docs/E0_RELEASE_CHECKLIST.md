# E0 发布 Checklist（不打 tag 也可逐项核对）

> Phase F 收尾 · 正式 tag/PyPI 见 [RELEASE_v0.0.1.md](RELEASE_v0.0.1.md)

## 本地自检

```bash
meris release check                    # pytest + mock 8/8 + harness + cargo
python scripts/run_benchmark_mock.py --native-only
meris doctor
meris native status
```

期望：`release check` 全绿；`native status` 在 dev 树为 `binarySource: dev` 或 `path`；staging 后为 `bundled`。

## CI

- [ ] `test` workflow green（push main）
- [ ] 可选：`release` workflow_dispatch → 下载 `meris-rs-*` + `python-dist` artifacts

## 打包（仍不打 tag 时可试跑）

```bash
meris native build
python scripts/stage_bundled_binary.py --clean
python -m build
# 检查 wheel: meris/_bundled/meris-rs 存在（Linux 构建）
```

## 正式发布（需你明确说「打 tag」后再做）

```bash
git tag v0.0.1 && git push origin v0.0.1
# release workflow 自动：GitHub Release + 可选 PyPI
```

PyPI 凭证：`TWINE_*` + `scripts/publish-pypi.ps1`

## Phase F 状态

| 项 | 状态 |
|----|------|
| F1–F4 | ✅ |
| F3-M2 bundled binary | ✅ Linux wheel |
| F5 E0 tag + PyPI | 暂缓 |
