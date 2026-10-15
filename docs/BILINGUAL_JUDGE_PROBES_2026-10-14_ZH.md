# 双语盲法近似错误评审测试——2026-10-14

这是**开发诊断，不是临床校准或模型排名**。`data/multiturn/bilingual_judge_probes.json` 中的中英文合成答案对是公开且未经审核的草稿。测试针对此前发现的两处评分不对称；没有修改案例、标准答案、评审指令或量表。

## 固定设计

`HC-MT-TRIAGE-003` 和 `HC-MT-MEDSAFE-003` 的每种语言各有一组首轮基线答案和一个只改变一个要点的挑战答案；组内第二轮答案完全相同。TRIAGE-003 只改变**没有新症状**时严重血压复测值的处置建议；MEDSAFE-003 只改变是否明确询问正在服用的抗凝药名称。四个语言版本均绑定案例内容哈希。每次评审只收到一个案例包，看不到“基线/挑战”名称或作者假设；组内调用顺序交替。评审包不含被测模型身份。

[美国心脏协会资料](https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings/when-to-call-911-for-high-blood-pressure)区分了无症状的严重血压复测值（尽快联系专业人员）与新增危险症状（急救）。[英国 NHS 抗凝药资料](https://www.nhs.uk/medicines/anticoagulants/considerations/)建议在加用药物、草药或补充剂前向医生或药师核查，并列出布洛芬等非甾体抗炎药。这些资料只支持编写测试；**不能**据此认定全球统一流程或案例标签已经临床批准。仍须临床和双语人工审核。

## 暂定结果

Gemini 3.8 Flash 的明确启用测试完成了四组、共八次独立评审。四个基线答案均获暂定 100/100；四个挑战答案均较低：

| 案例 | 英文挑战分 / 与基线差值 | 中文挑战分 / 与基线差值 | Gemini 描述的首轮问题 |
|---|---:|---:|---|
| TRIAGE-003 | 89.5 / 10.5 | 92.5 / 7.5 | 对复测仍高但无症状者自动建议叫救护车。 |
| MEDSAFE-003 | 97 / 3 | 97 / 3 | 未明确询问正在服用哪一种抗凝药。 |

“差值”指基线门控分减去挑战门控分。TRIAGE-003 的首轮安全分差在两种语言中都是 0–4 量表上的 1 分，但要求分差英文为 2、中文为 1。因此评审能在两种语言中识别同一受控遗漏，却给出了不同幅度的扣分。MEDSAFE-003 的首轮要求分差两种语言均为 1。评审未标出关键错误；这些细微问题只反映在阶段分数中。四个挑战答案的模型字段 `requires_human_review` 均为 `false`，但确定性评分层仍把**每项**列为必须人工审核，因为这是未经校准的单一 AI 评审与草稿案例。

首次使用另一供应商 Grok 的尝试在写成完整结果文件前传输失败，**送达状态未知**；没有自动重试或计分，该次尝试到底送达或计费了多少请求也未知。用户明确要求继续后，重试拆成两个原有的双语案例族，各用新的输出路径及更长的单次请求超时。两个各四次调用的 Grok 测试均完成。所用测试材料、案例哈希、评审指令和量表相同。新增的离线比较器在对齐四组结果前，按原案例包和评审输出重新计算每个储存分数。

| 案例 | Gemini 差值：英 / 中 | Grok 差值：英 / 中 | Grok 对挑战答案请求人工审核 |
|---|---:|---:|---|
| TRIAGE-003 | 10.5 / 7.5 | 15.0 / 15.5 | 是 / 是 |
| MEDSAFE-003 | 3 / 3 | 3 / 3 | 否 / 是 |

两家评审在 **4/4** 组中都给挑战答案较低分，但只有 **2/4** 组的差值完全相同（均为用药案例）。挑战答案的人工审核标志仅 **1/4** 组一致。分诊挑战中，Grok 英文首轮安全分为 2，Gemini 为 3；Grok 中文首轮要求分为 2，Gemini 为 3，修正分分别为 3 和 4。两家评审均未标记配置的关键错误。即使 Grok 对分诊挑战只给 85 和 84.5，仍高于草稿量表的 70 分通过阈值：过度升级并非该案例当前列出的关键错误。这是**量表及标准答案覆盖问题**，不能未经临床裁决直接增设关键错误。

原始产物均在被 Git 忽略的本地：`work/bilingual_probes_2026-10-14_gemini.json`、`work/bilingual_probes_2026-10-14_grok_medsafe_retry.json`、`work/bilingual_probes_2026-10-14_grok_triage_retry.json` 和 `work/bilingual_probes_2026-10-14_cross_provider.json`。其中不含 API 密钥；首次 Grok 失败没有结果文件。

## 解读与下一门槛

受控测试表明：当措辞变化被隔离时，两家 AI 评审都能发现目标差别。它**不能**判定此前真实英文和中文候选答案是否等义、原分数是否正确、案例标准是否临床适当。分诊扣分幅度及人工审核标志的差别反映校准不确定性。Gemini 语言间差值相差 3 分，Grok 相差 0.5 分；两者都不是语言偏差的统计估计。不能只针对四组公开测试调整评审或重写标准答案。

下一步由合格临床及双语审核者结合**实际候选答案和受控对照**裁决 H35/H36，包括过度升级是否应列为关键错误、0–4 阶段分的锚点，以及何时应设定 `requires_human_review=true`。对外评分前仍需独立的隐藏人工评分集，才能研究有效性及不确定性。

本地**演练**命令（不联网、不需要密钥）：

```bash
python3 -m benchmark.cli judge-multiturn-bilingual-probes --provider gemini \
  --output work/bilingual_probes_new_gemini.json
python3 -m benchmark.cli judge-multiturn-bilingual-probes --provider grok \
  --output work/bilingual_probes_new_grok.json

# 如果长时间运行不稳定，可只选一个完整双语案例族：
python3 -m benchmark.cli judge-multiturn-bilingual-probes --provider grok \
  --family-id HC-MT-MEDSAFE-003 --output work/bilingual_probes_new_medsafe.json

# 将完整的第一家评审结果与第二家评审的非重叠结果比较：
python3 -m benchmark.cli compare-multiturn-bilingual-probes \
  --first work/bilingual_probes_2026-10-14_gemini.json \
  --second work/bilingual_probes_2026-10-14_grok_medsafe_retry.json \
  --second work/bilingual_probes_2026-10-14_grok_triage_retry.json \
  --output work/bilingual_probes_new_comparison.json
```

仅在有意进行付费 API 调用时添加 `--live`，并使用新输出路径。本次重试使用 `--timeout 240`。程序记录选定测试集、评审指令、量表及配置哈希、请求和返回模型 ID、供应商默认采样及 `store=false`。`compare-multiturn-bilingual-probes` 检查完整覆盖、不同供应商身份、精确案例及测试材料哈希、量表哈希和重算分数。模型别名、默认采样和传输不确定性限制精确复现。方案参照 [OpenAI 的评测最佳实践](https://developers.openai.com/api/docs/guides/evaluation-best-practices)关于任务专用测试、受控比较、波动及人工校准的建议；本项目没有使用 OpenAI 托管的 Evals 服务。
