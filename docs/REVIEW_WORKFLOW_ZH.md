# 案例审核流程 v0.2 — 中文

本流程把专家审核转化为可审计的发布证据。它支持临床与双语质量控制，但不会自动完成临床判断，也不能单独证明评测基准已经获得认证。

## 1. 审核门槛

当前 Alpha 政策要求每个案例至少获得一项有效、独立的临床批准；每个翻译版本还至少需要一项有效的语言等价性批准。这只是开发阶段的最低门槛，不是最终 Gold Set 标准。Gold Set 应在另行批准的方案下采用双人独立审核和裁决。

只有同时满足以下条件，批准才计入门槛：

- 指向现有案例 ID 和精确语义版本；
- 包含未更改、可审核案例内容的规范 SHA-256 哈希；
- 审核者角色获准执行相应审核类型；
- 审核者独立于案例中记录的作者；
- 完成该审核类型要求的检查；
- `decision=approve`，且没有未解决的必改项；
- 通过 `validate-reviews`，没有错误。

仅有审核文件、审核者姓名，或 `approve_with_changes` 决定，都不能关闭门槛。

## 2. 角色与允许的审核类型

| 审核类型 | 允许角色 | 批准所需的最低检查 |
|---|---|---|
| 临床 | 临床医生、药师、领域专家 | 题目、参考行为、关键要求、关键错误、来源和范围 |
| 语言等价性 | 语言审核者、领域专家 | 语言等价性和范围 |
| 方法学 | 领域专家、裁决者 | 关键要求、关键错误和范围 |
| 裁决 | 裁决者 | 范围以及书面解决说明 |

项目必须在仓库之外核实真实资质。角色标签只是审计元数据，不等于完成资质认证。

## 3. 创建与内容绑定的记录

应从已配置的数据集生成记录，而不是复制静态示例：

```bash
python -m benchmark.cli --config config/benchmark.json review-template \
  HC-GC-TRIAGE-001-ZH-HANS \
  --review-type language_equivalence \
  --reviewer-id reviewer_language_01 \
  --role language_reviewer \
  --qualification-scope "与本案例相关的已核实双语审核范围" \
  --jurisdiction-scope global_core \
  --output data/reviews/development/HC-GC-TRIAGE-001-ZH-HANS.language.json
```

生成的文件刻意保持为未批准状态。审核者需要评估案例、完成检查、记录利益冲突和说明，并选择决定。如果可审核内容发生变化，即使版本号未变，已保存的哈希也会失效，该审核不能关闭门槛。改变含义的修改还必须提升案例版本。仅在批准后更新的生命周期字段——状态、验证标志、审核者 ID、翻译审核状态和变更理由——不计入哈希，因此受控升级不会使其自身的证据失效。

## 4. 决定类型

- `approve`：所有必要检查通过，且没有未解决的必改项。
- `approve_with_changes`：列出的修改必须完成；门槛保持开放。
- `revise`：重新审核前需要实质修改。
- `reject`：当前构念下案例不应继续推进。
- `needs_specialist`：当前审核者无法在自身资质范围内安全解决问题。

必改项应具体并可验证。记录中不得包含敏感的审核者身份或患者信息。

## 5. 仅追加式纠错

不得编辑已完成的记录。应创建具有新 ID 的记录，并用 `supersedes_review_id` 指向旧记录。对于同一审核者、同一案例版本和同一审核类型，按时间排序的最新有效记录决定该审核者当前的结论；旧记录继续保留在审计链中。

审核者意见不一致时，应保留所有独立记录，并新增裁决记录。裁决必须说明如何解决分歧，不能抹去分歧历史。

## 6. 验证与监控

```bash
python -m benchmark.cli --config config/benchmark.json validate-reviews
python -m benchmark.cli --config config/benchmark.json review-status
```

`validate-reviews` 检查结构、时间戳、重复 ID、替代引用、案例身份/哈希、独立性、角色权限和决定一致性。`review-status` 计算当前有效批准，并列出临床和语言审核队列。自动化时可使用 `--format json`。

审核验证与数据集验证相互独立：

```bash
python -m benchmark.cli --config config/benchmark.json validate-data
python -m benchmark.cli --config config/benchmark.json validate-data --release-ready
```

通过审核门槛只表示案例可以进入受控升级流程；工具不会自动修改案例元数据或状态。负责人仍需确认必改项已经解决，更新审核者 ID 和翻译元数据，按需提升状态/版本，并重新运行两套验证。

## 7. 升级检查清单

- [ ] 已在仓库之外核实审核者资质与利益冲突。
- [ ] 每个精确案例修订版都有临床批准。
- [ ] 每个翻译变体都有语言等价性批准。
- [ ] 所有必改项已解决，并在需要时创建新的案例版本。
- [ ] 所有分歧都有仅追加式裁决记录。
- [ ] `validate-reviews` 和开发模式 `validate-data` 均通过。
- [ ] 案例元数据准确记录审核者和翻译方式。
- [ ] 纳入发布清单前，发布模式验证已通过。
