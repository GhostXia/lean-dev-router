# Codex profile

This is the Codex adapter for Lean Dev Router. The routing theory remains runtime-agnostic; this profile supplies Codex-compatible Agent TOML files, Skill paths, the native-subagent default, and the independent-session fallback.

The profile is generated from the single source in `runtime/source/`:

```bash
python scripts/build_runtime.py --language en --output-dir profiles/codex/en
python scripts/build_runtime.py --language zh-CN --output-dir profiles/codex/zh-CN
```

Install one generated language profile as follows:

- `profiles/codex/<language>/.agents/skills/lean-dev-router/` → `~/.codex/skills/lean-dev-router/`
- `profiles/codex/<language>/agents/*.toml` → `~/.codex/agents/`

English is the default profile. Do not edit generated files directly; change the canonical source and regenerate both profiles. The generated Agent TOML files remain the source of truth for model and reasoning settings.

Codex native subagents are preferred. If native nested spawning is unavailable, use independent Codex sessions with the same `DISPATCH` manifest and evidence protocol.

## Codex profile / Codex profile

这是 Lean Dev Router 的 Codex adapter。路由理论仍然与运行时无关；本 profile 提供 Codex 兼容的 Agent TOML、Skill 路径、原生 subagent 默认方式以及独立 session fallback。

profile 从 `runtime/source/` 这一份源文件生成：

```bash
python scripts/build_runtime.py --language en --output-dir profiles/codex/en
python scripts/build_runtime.py --language zh-CN --output-dir profiles/codex/zh-CN
```

安装时按以下映射复制所选语言 profile：

- `profiles/codex/<language>/.agents/skills/lean-dev-router/` → `~/.codex/skills/lean-dev-router/`
- `profiles/codex/<language>/agents/*.toml` → `~/.codex/agents/`

默认使用英文 profile。不要直接编辑生成文件；请修改规范源后重新生成两套 profile。生成的 Agent TOML 文件仍是模型与思考强度设置的事实来源。
