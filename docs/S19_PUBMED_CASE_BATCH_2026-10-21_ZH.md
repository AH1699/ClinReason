# S19 PubMed 启发的合成案例批次 — 2026-10-21

新增[两族双语双轮公开开发案例](../data/multiturn/batch_h_cases.json)后，配置中的公开集为 **114 族／228 个语言版本**：Alpha 32、患者双轮 40、专业题 42。这只是作者覆盖数量，不代表实测专家级难度、临床批准或校准／隐藏 Gold（仍为 **0／0**）。本批次没有候选模型或裁判调用。

`HC-MT-TRIAGE-021` 以[眼科病例报告 PMID 41562822](https://pubmed.ncbi.nlm.nih.gov/41562822/)启发“不要被药物副作用解释锚定”的机制；准确答案要求另由[NHS 眼痛](https://www.nhs.uk/symptoms/eye-pain/)及[青光眼](https://www.nhs.uk/conditions/glaucoma/)资料支持。案例改为未指定药物、单侧症状，没有照搬手术、年龄、眼压或结局。与 `TRIAGE-012` 和待校准 `TRIAGE-016` 可能重复，已列为待审。

`HC-MT-REASON-016` 以[肺栓塞病例报告 PMID 39193021](https://pubmed.ncbi.nlm.nih.gov/39193021/)启发“新信息出现后重新考虑呼吸道解释”的机制；紧急症状与评估路径另查[NHS 肺栓塞](https://www.nhs.uk/conditions/pulmonary-embolism/)及[NICE NG158](https://www.nice.org.uk/guidance/ng158/chapter/Recommendations)。虚构了家用血氧读数和卧床干扰信息，没有复制原报告年龄、病原体、咯血、D-二聚体、影像和结局。与 `TRIAGE-011`、`PRO-PE-001` 的交叠已登记。单次正常血氧不能据此排除肺栓塞，是基于指南完整评估路径的推论，而非直接验证的单项规则。

[H 批次来源及逐项要求映射](../data/multiturn/batch_h_provenance.json)记录报告引用、先前逐篇查得的 CC BY／发表同意声明，并把 **12 条英文草稿要求**分别关联到独立公开指导资料。[离线检查](../benchmark/pubmed_derived_case_audit.py)核对案例、来源、逐项要求，并拒绝用病例报告给自身答案背书。中文要求仍未经合格双语审查。未复制患者叙事、图片或可识别细节，这是审慎的隐私动作，**并非已证明不可重新识别**。正式发布前还要复核授权、勘误／撤稿、来源时效、泄露风险及临床准确性。本日标题／DOI 搜索未见勘误或撤稿信号，但未完成权威登记核查。第三篇药物报告因同意及罕见组合风险继续仅作引文；CC BY-NC-ND 报告继续排除。

可运行 `python3 -m benchmark.pubmed_derived_case_audit`、`python3 -m benchmark.cli validate-multiturn`、`python3 -m benchmark.portfolio_audit`。下一步是未来请独立人员审查准确规则与重复风险；其间继续从权利合适的公开报告及独立指南挑选不同机制，不改写成易识别的原患者故事。H 批次不能充当隐藏 Gold，也不能把严重错误标签称为临床已验证。
