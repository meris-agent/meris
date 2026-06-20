# PyPI 发布就绪说明

> **当前策略：暂缓实际上传**（需 `TWINE_PASSWORD` / `PYPI_API_TOKEN` + 发版 tag）。  
> 本仓库已具备构建与本地验证流程。

## 包信息

| 项 | 值 |
|----|-----|
| PyPI 名 | `meris-agent` |
| 版本 | 见 `pyproject.toml`（当前 `0.0.2`） |
| 构建 | hatchling (`pyproject.toml`) |

## 本地验证（不上传）

```powershell
cd meris
powershell -ExecutionPolicy Bypass -File scripts\publish-pypi.ps1 -SkipUpload
```

等价步骤：

1. `pytest tests/ -m "not integration" -q`
2. `python -m build`
3. `twine check dist/*`（脚本内执行）

## 正式发布（需凭证）

```powershell
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = "<pypi-token>"
powershell -ExecutionPolicy Bypass -File scripts\publish-pypi.ps1
```

TestPyPI：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\publish-pypi.ps1 -TestPyPI
```

## 发版前检查

```bash
meris release check
meris harness check
```

详见 [E0_RELEASE_CHECKLIST.md](E0_RELEASE_CHECKLIST.md) · [RELEASE_v0.0.2.md](RELEASE_v0.0.2.md)。

## 暂缓原因

- Route B dogfood 进行中
- `meris-rs` 二进制通过 GitHub Release 分发，PyPI 包为 Python Harness + CLI
- 避免无 token 的 CI 误上传
