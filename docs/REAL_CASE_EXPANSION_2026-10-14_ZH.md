# 已发表病例扩展——开发批次，2026-10-14

面向临床人员的草稿从四族、八题扩展到 **10 个双语案例族、20 条题目**。新增六族分别借鉴六篇不同的已发表真实病例报告，但题目是重新编写的合成情境，不是原患者病历。每族的来源、署名、文章许可、改写内容和局限均记录在 [`data/evidence/clinical_case_adaptations.json`](../data/evidence/clinical_case_adaptations.json)。没有导入原始患者资料、文章段落、图片或付费数据。全部仍只供开发；中文表述、临床参考要点及关键错误严重程度均未经人工审核，专业轨道评分尚未启用。

| 案例族 | 用真实病例模式构造的进阶考点 | 已发表来源 |
|---|---|---|
| `HC-PRO-DIABETES-001` | 使用 SGLT2 抑制剂后，血糖未达到传统 DKA 阈值，但存在酮体及酸中毒；区分紧迫性与诊断确定性。 | [Mahfooz 等](https://pmc.ncbi.nlm.nih.gov/articles/PMC9313009/) |
| `HC-PRO-TOX-001` | 利奈唑胺与 5-羟色胺能药物合用，乳酸升高且出现神经症状；同时考虑感染与药物毒性。 | [Ferreira 等](https://pmc.ncbi.nlm.nih.gov/articles/PMC10996881/) |
| `HC-PRO-LAB-001` | 不同采集/运输条件下血钾不一致；调查标本伪差，同时不忽略真正危险。 | [Castillo Pérez 等](https://pmc.ncbi.nlm.nih.gov/articles/PMC10197407/) |
| `HC-PRO-POSTPARTUM-001` | 血栓栓塞后仍有症状及双侧肾上腺异常，尽管血钠正常；避免单一诊断锚定。 | [Jiang 等](https://pmc.ncbi.nlm.nih.gov/articles/PMC11515325/) |
| `HC-PRO-CARDIOONC-001` | 免疫检查点治疗期间新发肌钙蛋白升高，但首次心电图/超声不明显；保持鉴别与升级评估。 | [Delombaerde 等](https://pmc.ncbi.nlm.nih.gov/articles/PMC9281161/) |
| `HC-PRO-ENDOONC-001` | 早期检查令人放心，后来肾上腺轴异常进展且 ACTH/皮质醇不匹配；避免过度依赖旧结果。 | [Bi 等](https://pmc.ncbi.nlm.nih.gov/articles/PMC10259291/) |

文章页面或出版商 PDF 标有 CC BY 4.0。我们链接并署名原文，同时记录改写。**可免费阅读不等于可任意再利用**：[PMC 版权说明](https://pmc.ncbi.nlm.nih.gov/about/copyright/)及[开放获取子集说明](https://pmc.ncbi.nlm.nih.gov/tools/openftlist/)要求逐篇核对许可，并为系统性获取使用指定渠道。这一批是逐篇研究，没有批量下载。以后若大规模检索，应使用 PMC 官方 API/云服务及许可过滤，再逐篇审查。单篇病例报告也不能代表总体人群，更不是已验证的标准答案。

除临床审核外，下一项工作是建立可重复的来源引入关卡：检索多样且许可明确的病例，去重临床机制及文章，记录署名、许可、改写，编写中英文草稿标签，并检查语义一致性和基准泄漏。随后用多个被测模型与评审模型在开发集上审计难度和校准，分别报告语言及失败模式，依据证据选择下一批覆盖缺口。这六族加强了专业推理，但**没有**填平面向患者的纵向资料或多轮覆盖缺口。专业轨道不与患者轨道混算；已公开来源和标签的题目也不能再当作隐藏测试集。

对外评分前，合格临床人员与双语审核者仍须批准精确版本的题目与标签，包括可接受的其他答案和错误严重度。已发表病例及 AI 审核不能取代这一关卡。[官方评测指南](https://developers.openai.com/api/docs/guides/evaluation-best-practices)同样强调有代表性的示例、边缘情况和基于人工的校准，而非仅追求数量。
