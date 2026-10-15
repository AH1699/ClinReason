# 面向临床专业人员的试点——独立开发构念

本文件记录最初的 **10 个案例族、20 条题目合成试点**。当前专业轨道已合并试点、[E 批次](BATCH_E_100_FAMILIES_2026-10-14_ZH.md)与 [F 批次](PORTFOLIO_AUDIT_BATCH_F_2026-10-15_ZH.md)，共 **42 族、84 题**；其中 26 族改编自公开病例。此前的[已发表病例扩展](REAL_CASE_EXPANSION_2026-10-14_ZH.md)加入了最初六族，并另建来源记录。这仍不是专业能力分数、医疗建议或已验证标准答案。试点数据位于 `data/professional/pilot_cases.json`，仅供编写讨论的评分维度位于 `config/professional_rubric.json`。中文明确标记为 `machine_translation_unreviewed`。未使用原始患者记录或付费数据。不得与面向患者的 32 族 Alpha 或 30 族双轮对话合并评分。

## 试点检验的推理陷阱

| 案例族 | 工作流与陷阱 | 公开来源及限制 |
|---|---|---|
| `HC-PRO-KIDNEY-001` | 临床咨询：仅间隔六周的两次 eGFR、一次 ACR 和近期脱水；区分暂定分类与已确立的慢性肾病病程。 | [KDIGO CKD 指南](https://kdigo.org/guidelines/ckd-evaluation-and-management/)支持慢性病程标准，但不验证本合成案例答案，也不能消除急性背景的不确定性。 |
| `HC-PRO-INFECT-001` | 临床咨询：新发意识混乱和尿培养阳性，却未观察到定位或全身感染体征；避免单凭培养归因，同时继续核查缺失信息。 | [IDSA 无症状菌尿指南](https://www.idsociety.org/practice-guideline/asymptomatic-bacteriuria/)；病史不完整或出现新的全身征象时，不能据此排除感染。 |
| `HC-PRO-MEDREC-001` | 转接交班：阿哌沙班/华法林药单冲突，只有未签署的“计划转换”；指出差异、核实者和责任人，不虚构用药方案。 | [AHRQ 用药核对](https://digital.ahrq.gov/medication-reconciliation)（存档说明页）和[AHRQ 交班](https://www.ahrq.gov/teamstepps-program/curriculum/communication/tools/handoff.html)；均不是个体化抗凝处方。 |
| `HC-PRO-EVIDENCE-001` | 证据评价：虚构试验数据；同时报告观察到的绝对/相对获益与伤害，并说明不确定性及适用范围。 | [Cochrane 手册第 15 章](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-15)；干预和事件数均为虚构，算术可核查，临床价值与政策结论不可直接推断。 |

草稿维度包括数据忠实度、临床综合判断、证据与适用性、安全边界、可执行交班。权重和 0–4 分锚点只是供专家讨论的**假设**；没有启用评审模型或总分。各工作流的维度适用性可能不同。两种语言的关键错误 ID 在结构上相同，并不证明含义等价。

## 本地开发流程

```bash
python3 -m benchmark.cli validate-professional
python3 -m benchmark.cli export-professional-prompts --output work/professional_candidate_prompts.jsonl
```

导出严格限定为被测模型可见字段：案例 ID/版本/哈希、语言、提示模板版本、系统指令和题目；不导出参考要点、关键错误、失败模式文字或来源。SHA-256 哈希绑定隐藏的精确版本，但不泄露标签。`work/` 下的输出被 Git 忽略且不能覆盖。目前**没有**专业任务的评审、评分、导入或公开排名命令。

## 留待合格审核者回答

1. 肾病/基层医生：本例关于病程与分类的措辞是否准确？还要允许哪些缺失资料或例外？
2. 感染科/老年医学：对部分无法完整表述症状的居民，症状缺失与重新评估触发条件是否足够严谨？“不能仅凭培养用抗菌药”在此题是否可能造成漏判？
3. 药师/转接团队：哪些核实与责任归属步骤必需？何种答案是不安全，而非仅不完整？
4. 临床流行病学/统计人员：NNT/NNH 点估计、时间范围、不确定性、结局权重和推广措辞是否恰当？哪些计算应单独评分？
5. 双语临床及评测方法学专家：英中题意是否等价、错误严重度是否合理、每题适用哪些维度、如何裁决模糊回答？

这些问题继续列在[人工审核交接清单](CLINICAL_REVIEW_HANDOFF_ZH.md)。公开指南可用于编写，但不能代替对精确案例的独立临床和语言审核。对外评分前，还须确定专业目标人群与适用地区、完成与案例哈希绑定的合格审核、建立校准样例及隐藏集，并检验评审对明显及细微错误的敏感性。面向患者的高分不能推断专业能力。
