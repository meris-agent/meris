# macOS Seatbelt

SBPL is **generated at runtime** by `meris-rs` (`seatbelt_policy.rs`), not copied from Codex.

```bash
meris-rs sandbox policy --workspace .
```

Python calls the same via `build_seatbelt_policy()` → subprocess to meris-rs.

Design: [docs/harness/SEATBELT_DESIGN.md](../../docs/harness/SEATBELT_DESIGN.md)
