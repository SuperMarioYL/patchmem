[English](./README.en.md) · [Website](https://patchmem.lei6393.com) · [GitHub](https://github.com/SuperMarioYL/patchmem)

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/hero-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/hero-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/hero-dark.svg">
  <img src="./assets/presentation/hero-light.svg" width="960" alt="Hero diagram">
</picture>

# patchmem

**比较记忆补丁前后的工具决策。**

PatchMem 读取结构化 Agent 轨迹，帮助编写带锚点的文本补丁，并按 ID、名称和参数比较提供的工具决策。

## 为什么需要它

计划修正需要可检查的插入位置与明确差异报告。PatchMem 提供本地数据结构，通过结构比较展示差异，不依赖模型事后解释。

- **带锚点编辑** — 补丁明确消息锚点与插入文本。
- **结构证据** — 变化保留实际前后工具输入。
- **本地检查** — view 与 diff 可使用保存数据，无需模型。

## 架构

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/architecture-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/architecture-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/architecture-dark.svg">
  <img src="./assets/presentation/architecture-light.svg" width="960" alt="Architecture diagram">
</picture>

轨迹解析器读取 parentUuid 关系，提取工作记忆文本与 tool_use 决策。Patch 保存锚点和插入文本；compute_diff 按工具 ID 建索引，报告新增、删除或修改。当前 resume 运行器会抛出 RunnerStub。

| 组件 | 职责 |
| --- | --- |
| `Transcript parser` | patchmem/transcript.py |
| `Anchored patch` | patchmem/patch.py |
| `Decision diff` | patchmem/influence_diff.py |
| `Tree / report` | patchmem/wm_view.py |

## 安装与快速上手

使用仓库清单指定的运行时版本构建，并在仓库根目录运行示例。

```bash
git clone https://github.com/SuperMarioYL/patchmem.git
cd patchmem
uv venv .venv
uv pip install --python .venv/bin/python -e .
source .venv/bin/activate
```

将 examples/presentation-demo.py 中明确给出的合成前后决策列表交给生产 compute_diff 函数。

```bash
.venv/bin/python examples/presentation-demo.py
```

## 实际运行示例

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/process-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/process-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/process-dark.svg">
  <img src="./assets/presentation/process-light.svg" width="960" alt="Process diagram">
</picture>

The demo reports one altered Read decision and one added Read decision without executing either tool.

```text
[
  {
    "kind": "altered",
    "id": "tool-1",
    "before": {
      "id": "tool-1",
      "name": "Read",
      "input": {
        "path": "old.yaml"
      }
    },
    "after": {
      "id": "tool-1",
      "name": "Read",
      "input": {
        "path": "new.yaml"
      }
    }
  },
  {
    "kind": "added",
    "id": "tool-2",
    "after": {
      "id": "tool-2",
      "name": "Read",
      "input": {
        "path": "policy.yaml"
      }
    }
  }
]
```

完整命令与输出保存在 [docs/demo-results.json](./docs/demo-results.json). 输入和复现代码均随仓提供。

![已有终端录制](./assets/demo.gif)

保留已有录制供参考；上方文字示例给出当前可复现的操作。

## 用法

CLI 提供以下操作。示例之外的命令需要替换成你的文件路径或标识。

```bash
patchmem view tests/fixtures/sample_session.jsonl
# Interactive authoring opens your editor:
patchmem edit tests/fixtures/sample_session.jsonl --anchor msg-0006 --out patch.md
```

## 配置

PATCHMEM_PROJECTS_DIR 指定轨迹查找目录，PATCHMEM_RUNS_DIR 指定已有比较结果目录，$EDITOR 控制交互式补丁编辑。runtime 与 hosted 设置描述未来回放适配器，不代表已有回放服务。

## 集成与职责分工

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/integrations-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/integrations-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/integrations-dark.svg">
  <img src="./assets/presentation/integrations-light.svg" width="960" alt="Integrations diagram">
</picture>

以下路径已有源码实现。按任务选择输入，并把生成的结果与项目一起保存。

| 路径 | 已实现职责 |
| --- | --- |
| Claude JSONL | Recorded messages and tool_use blocks |
| patch.md | Anchor, rationale and text |
| Decision lists | Explicit control/patched inputs |
| InfluenceDiff | Added / removed / altered records |

## 限制与后续方向

- resume 与托管回放仍是占位；当前工具不执行带补丁和对照的 Agent 运行。
- 离线示例比较合成列表；结构差异本身不证明补丁导致了决策变化。
- 决策按 tool_use ID 匹配，因此有效比较需要标识之间具备适当对应关系。

下一功能里程碑是在轨迹副本应用补丁并生成两条回放输出，再计算结构差异。

## 许可与贡献

许可见 [LICENSE](./LICENSE). 反馈问题时请提供最小输入、执行命令和实际输出。
