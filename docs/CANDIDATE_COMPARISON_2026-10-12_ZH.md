# 固定双语样本的第二模型检查——已尝试，暂无新分数

此前 Grok 4.7 → Gemini 3.8 Flash 试点的六个双语、面向患者的双轮案例族，得到 **12/12 个暂定 100 分**。本轮预先固定相同的 12 个案例 ID：`HC-MT-TRIAGE-003/005`、`HC-MT-MEDSAFE-003/005`、`HC-MT-REASON-003/004`，每族英中各一条。三类各两族，但样本很小、合成、未经审核，也不是隐藏测试集。目标是观察另一被测模型是否打破满分天花板，**不是**给模型排名。

第二被测模型选用 Google `gemini-3.5-flash-lite`，不同于评审 `gemini-3.8-flash`。[Google 模型文档](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)列有该准确 ID。新适配器使用 [Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview)，设置 `store=false`，每轮仅重发之前可见的用户和助手内容。与 Grok 原生角色消息不同，Gemini 收到的是带角色分隔符的文本记录；这种**提示序列化差异是混杂因素**。Google 被测模型由 Google 评审模型评分，还可能有同厂商偏好。模型 ID 和请求格式均写入本地清单；采样仍采用服务商默认值，未固定。

## 截至 2026-10-12 的结果

干运行规划 **12 段对话 / 24 次被测模型调用**，未连接网络。首次选择 `--live` 后，第一轮报错 `Provider transport failed; delivery state is unknown`。未写入答案或清单、未请求 Gemini 评审，因此**没有第二模型分数或比较结果**。因请求可能已到达服务端，不能自动重试以免重复计费。旧 Grok 结果已按历史 pilot + C 批次数据版本重新审核，保存在 `work/difficulty_audit_2026-10-12_grok_report_v2.json`；仍为 12/12 个暂定 100 分，单独重审不会提升其临床效度。

## 传输恢复后的继续步骤

决定重试未知状态的请求后，须使用**新的输出文件名**，不可覆盖或暗中合并尝试。`.env.local` 和 `work/` 原始文件保持本地并被 Git 忽略。固定样本命令：

```bash
python3 -m benchmark.cli generate-gemini-multiturn \
  --model gemini-3.5-flash-lite --limit 12 \
  --family-ids HC-MT-TRIAGE-003,HC-MT-TRIAGE-005,HC-MT-MEDSAFE-003,HC-MT-MEDSAFE-005,HC-MT-REASON-003,HC-MT-REASON-004 \
  --output work/difficulty_audit_gemini35lite_attempt2_answers.jsonl --live
```

仅当 12 段被测对话全部完成，再用配置的 `gemini-3.8-flash` 执行 `judge-multiturn-gemini --answers ... --limit 12 --output ... --live`，评价全部 **12 个对话评审包（共 24 个分阶段回答）**。随后用当前三个批次数据和答案/评审文件执行 `difficulty-audit-multiturn`，最后以 `compare-multiturn-candidates --first-report work/difficulty_audit_2026-10-12_grok_report_v2.json --second-report ... --output ...` 比较。比较器会拒绝案例集合、哈希、rubric、评审模型身份或指令哈希不一致的报告；输出逐案分差与满分数量，而非公开排名。完整运行后仍需重复被测模型采样、独立评审校准和合格临床/双语人工评级，才可讨论区分效度。

本地测量设计参考 [OpenAI 评测指南](https://developers.openai.com/api/docs/guides/evaluation-best-practices)关于代表性样本、人工校准和波动检查的建议；本项目不依赖其托管 Evals 平台。
