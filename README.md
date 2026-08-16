[English](./README.en.md) | **简体中文**

<div align="right"><sub><a href="./README.en.md">EN</a>&nbsp;&nbsp;⇄&nbsp;&nbsp;<b>中文</b></sub></div>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/hero-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/hero-light.svg">
  <img src="./assets/hero-light.svg" width="880" alt="PatchMem — patch working memory mid-run, see the decision diff">
</picture>

<p align="center"><sub>给跑偏的 coding agent 打一个 working-memory 补丁，继续跑，再看哪些下游决策因此改变。</sub></p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="license"></a>
  <a href="https://github.com/SuperMarioYL/patchmem/releases"><img src="https://img.shields.io/github/v/release/SuperMarioYL/patchmem" alt="latest release"></a>
  <img src="https://img.shields.io/github/actions/workflow/status/SuperMarioYL/patchmem/ci.yml?branch=main&label=ci" alt="ci">
  <img src="https://img.shields.io/badge/python-3.12+-blue" alt="python">
  <img src="https://img.shields.io/badge/Agent-ready-8985FF" alt="Agent">
</p>

**一句话**：长跑的 coding agent 跑偏时，别再"硬跑完"或"从零重启"——给它打个 working-memory 补丁，resume，再看 patch 改了哪些 `tool_use` 决策。

<h2><img src="https://api.iconify.design/tabler:topology-star-3.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 架构</h2>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/atlas-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/atlas-light.svg">
  <img src="./assets/atlas-light.svg" width="880" alt="架构：Session JSONL → Parse+Patch → Resume 2 arms → Influence Diff">
</picture>

PatchMem 读 `~/.claude/projects/*/<session>.jsonl`，把 parentUuid 链接的决策树和当前 working memory 渲染成 rich TUI；操作员在某个 anchor 点插入一段补丁（plan/scratchpad），resume 时把**补丁过的**和**未补丁的 control** 两条臂都重放，再结构化 diff 两条臂的 `tool_use` 决策，得到机器可核验的 patch-influence-diff。一份 transcript 被复制并写入，两条臂各自 resume，决策按 `id` diff——不是模型归因。

<h2><img src="https://api.iconify.design/tabler:rocket.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 为什么是现在</h2>

coding agent 的单次运行时长从"一轮重构"变成"数小时长跑"，跑偏的概率随长度上升。最近半年三件事同时发生：长程 agentic run 成为常态（[headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) 这类 coding agent 的注意力仍在涨）；runtime 开始持久化结构化、可重放的状态——Claude Code 的 session JSONL 里 `parentUuid` 链接的 `tool_use` 块带着稳定 `id`，正是可 diff 的 working-memory 表面；token/缓存经济学让重启变贵——一个跑偏的长跑现在扔掉的是真金白银和 cache 状态。两年前 WM 是不透明的 prompt 上下文，今天它是一份按 `id` 可寻址、可 replay-ablation 的 JSONL。PatchMem 的 owned 原语——replay-ablation decision-diff——只在"决策日志机器可寻址"的今天才解得出。

<h2><img src="https://api.iconify.design/tabler:rocket.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 安装</h2>

```bash
# 方式一：uv tool（推荐，<60s，零配置）
uv tool install patchmem
# 方式二：pipx
pipx install patchmem
# 方式三：从源码
git clone https://github.com/SuperMarioYL/patchmem && cd patchmem && pip install -e .
```

<h2><img src="https://api.iconify.design/tabler:rocket.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 快速开始</h2>

```bash
# 1. 用任意会话 id 前缀查看 working memory 与决策树（读你自己的 ~/.claude/projects）
patchmem view <session-id-prefix>

# 2. 打开 $EDITOR 写一段 working-memory 补丁，生成 patch.md（anchor 已核验）
patchmem edit <session-id-prefix>

# 3. （m2）补丁过的 + 未补丁的两条臂 resume；（m3）看 influence diff
patchmem resume <session-id-prefix> --patch patch.md   # m2 — v0.1 为 stub
patchmem diff  <session-id-prefix>                     # m3 — 原语已实现，待 m2 重放输出
```

<details><summary>样例输出（<code>patchmem view</code> on fixture）</summary>

```
patchmem v0.1.0  session: sample_session

╭──────────────────────────────────────────────────────────────────────────────╮
│ session  10 messages  4 tool_use decisions                                   │
╰──────────────────────────────────────────────────────────────────────────────╯
session
└── user      msg-0001  2026-08-17T09:00:01  (text only)
    └── assistant msg-0002  2026-08-17T09:00:05  tool_use [Bash]  id=toolu_aaaa0001
        └── user      msg-0003  ... tool_result
            └── assistant msg-0006  tool_use [Write]  id=toolu_aaaa0003
                └── ...
                    └── assistant msg-0010  Done. The auth middleware now validates HS256 JWTs ...

╭─────────────────────── working memory / plan ────────────────────────────────╮
│ [3] anchor=msg-0006  Now I will write a real JWT-backed auth middleware ...   │
│ [5] anchor=msg-0010  Done. The auth middleware now validates HS256 JWTs ...   │
╰──────────────────────────────────────────────────────────────────────────────╯

                              valid patch anchors
┏━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ #    ┃ anchor uuid ┃ type      ┃ preview                                     ┃
┡━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 6    │ msg-0006    │ assistant │ Now I will write a real JWT-backed auth ... │
└──────┴─────────────┴───────────┴─────────────────────────────────────────────┘
```

</details>

<h2><img src="https://api.iconify.design/tabler:terminal-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 用法</h2>

```bash
# 查看某个会话的决策树 + working memory（只读，无副作用）
patchmem view 5368eb59

# 指定插入锚点打开编辑器，输出到自定义路径
patchmem edit 5368eb59 --anchor 5368eb59-878c-4fc9 --out my-patch.md

# resume 时切换 runtime adapter（见 配置）；--hosted 指向 v0.3 托管 replay-farm
PATCHMEM_RUNTIME=claude-code patchmem resume 5368eb59 --patch my-patch.md
patchmem diff 5368eb59 --hosted     # v0.3 stub
```

补丁文件 `patch.md` 的格式（`patchmem edit` 自动生成，也可手写）：

```
anchor_uuid: 5368eb59-878c-4fc9-ab9f-94079e0a6b58
rationale: 强制校验 HS256 而非 HS384
block_type: text
---
plan: auth check MUST verify HS256 and reject HS384 before issuing a session
```

更多示例见 `examples/`。

<h2><img src="https://api.iconify.design/tabler:photo.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 演示</h2>

![demo](assets/demo.gif)

`view` → `edit`（插入一段修正的 plan）→ `diff` 打印 before/after `tool_use` 决策树。10 分钟内从 `git clone` 到第一个可见结果。完整 tape 见 `docs/demo.tape`，CI 在打 tag 时用 vhs 渲染 `assets/demo.gif`。

<h2><img src="https://api.iconify.design/tabler:adjustments.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 配置</h2>

配置通过环境变量或 `~/.patchmem/config.toml` 加载（环境变量优先）：

| key | 类型 | 默认 | 含义 |
|---|---|---|---|
| `runtime` | `claude-code` \| `claude` \| `herdr` | `claude-code` | resume 适配器（m2 用；herdr 为 v0.2+ 占位） |
| `projects_dir` | path | `~/.claude/projects` | session JSONL 根目录 |
| `runs_dir` | path | `~/.patchmem/runs` | 两条臂重放输出目录（`<runs>/<session>/{control,patched}.jsonl`） |
| `hosted` | bool | `false` | 走 v0.3 托管 replay-farm（`--hosted` 也开） |

对应环境变量：`PATCHMEM_RUNTIME` / `PATCHMEM_PROJECTS_DIR` / `PATCHMEM_RUNS_DIR` / `PATCHMEM_HOSTED`。

<h2><img src="https://api.iconify.design/tabler:map-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 路线图</h2>

- [x] **m1 — parse + render WM**：解析 Claude Code session JSONL 成 parentUuid 决策树，rich TUI 渲染 working memory，`patchmem edit` 开 `$EDITOR` 写补丁并核验 `anchor_uuid`
- [ ] **m2 — resume + replay**：补丁应用到 transcript 副本，经 `config.py` 适配器跑 patched + control 两条臂，存到 `~/.patchmem/runs/<session>/`
- [ ] **m3 — influence diff**：`patchmem diff` 结构化 diff 两条臂的 `tool_use`（按 `id`/`name`/`input`），渲染 before/after 影响树（原语已实现，单元测试守门 gate-3 诚实性）
- [ ] v0.2：多 runtime（herdr / waku）适配器
- [ ] v0.3：托管 replay-farm 付费层（`--hosted` 并行重放，秒级返回 diff）

<h2><img src="https://api.iconify.design/tabler:star.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 诚实性边界</h2>

influence-diff **必须**是 replay-ablation，绝不退化成模型的事后归因。`InfluenceDiff.changed` 是两条重放 transcript 的机械结构 diff（按 `tool_use.id` 键，再比 `name`/`input` 相等），不存储也不传输任何"因为这个补丁所以改变了"的模型叙事。`tests/test_influence_diff.py` 守这条 gate-3 底线：schema 不含 model-attribution 字段，`compute_diff` 源码不引用任何 LLM/网络库。若未来某次提交让 diff 退化成黑箱归因，测试会红。

<h2><img src="https://api.iconify.design/tabler:currency.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 付费与商用</h2>

| 层级 | 价格 | 说明 |
|---|---|---|
| **本地自托管（OSS）** | 免费 | 在你自己的 `~/.claude/projects/*.jsonl` 上跑 replay-ablation，原语 + 营销楔子 + star 引擎 |
| **团队托管 replay-farm** | $19/seat/月（按 replay-minutes 计量） | 托管层在 PatchMem 基础设施上并行跑 patched + control ablation，秒级返回 diff，而不是本地分钟级重放 |
| **企业版** | ~$5k–15k/年 | 私有部署 replay-farm + 每条 WM 补丁的审计日志（谁在哪次 run 上打了什么补丁），面向受监管工程团队 |

最小"掏钱"路径：tech lead 已经在本地用免费 `patchmem diff` 撞到"我笔记本重放要 8 分钟"的墙，加 `--hosted`，同样一条 diff 20 秒回来，走团队套餐 checkout。同一条命令、同一个 diff，计算从本机挪到云上。replay-ablation 是算力密集型（每个 diff 两次完整 agent 重放），正是托管层该变现的——本地 OSS 工具做不到。

<sup>云/计费栈规划：单 VM replay-farm，CN 友好区域（阿里云/腾讯云）；Stripe（国际）+ 微信支付/支付宝（CN SMB）；按 replay-minutes 的 per-seat 计量。v0.3 只发单 VM + checkout，不做多区域/SSO。</sup>

## Share this

```
PatchMem — 给 coding agent 打 working-memory 补丁的 Agent 原语：pause/edit-WM/resume，再看 patch 改了哪些 tool_use 决策。本地免费，托管层秒级。https://github.com/SuperMarioYL/patchmem
```

<h2><img src="https://api.iconify.design/tabler:license.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> License</h2>

MIT — 见 [LICENSE](./LICENSE)。提 issue 或 PR 直接发到 [Issues](https://github.com/SuperMarioYL/patchmem/issues)。

<p align="center"><sub><a href="./LICENSE">MIT</a> © 2026 SuperMarioYL</sub></p>
