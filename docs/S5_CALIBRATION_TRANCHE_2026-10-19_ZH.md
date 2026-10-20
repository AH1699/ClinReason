# S5 前瞻性患者校准首批 — 2026-10-19

## 当前边界

现有 **10 个双语、双轮的患者校准作者草案（20 个语言版本）**，达到 `data/audit/prospective_split_plan.json` 中首批的*草案数量*目标。它们**不是已批准校准题或隐藏 Gold**。默认公开开发集仍为 104 个家族；已批准校准与隐藏 Gold 仍为 **0／0**。另有 1 个未审核、被 Git 忽略的本地隐藏候选草案。本批没有调用模型或评判，没有产生新分数或改变权重。低／中／高档约 60–70／80／90 分仍是诊断期望，不能人为凑出。

C 批次新增 4 个有公开来源的合成案例族，见[案例文件](../data/calibration/multiturn_candidates_batch_c.json)及[来源与改写限制记录](../data/calibration/provenance_batch_c.json)：

| 家族 | 测试机制 | 已发表病例与辅助依据 | 未决界限 |
|---|---|---|---|
| `HC-MT-TRIAGE-015` | 幼儿腹痛发作间看似正常、无便血时仍可能有腹部急症 | [已发表病例](https://pmc.ncbi.nlm.nih.gov/articles/PMC5685448/)；[RCH 肠套叠指南](https://www.rch.org.au/clinicalguide/guideline_index/intussusception_guideline/) | 首轮低急迫度对照与后续立即转诊的界限、年龄及非典型表现须由儿科审核。 |
| `HC-MT-TRIAGE-016` | 有偏头痛史且头部 CT 正常，仍出现眼红疼痛和视力变化 | [误诊病例](https://pmc.ncbi.nlm.nih.gov/articles/PMC1676140/)；[Moorfields 症状及急迫度资料](https://www.moorfields.nhs.uk/for-patients/information-hub/narrow-angles) | 头部 CT 不能评估眼压；审核者须裁定急迫度及其他病因，不应强制给出确定的青光眼诊断。 |
| `HC-MT-MEDSAFE-012` | 硫唑嘌呤与别嘌醇相互作用，随后可能出现骨髓抑制 | [相互作用病例](https://pmc.ncbi.nlm.nih.gov/articles/PMC7793128/)；[DailyMed 药品说明](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=2f994aed-f8e7-4967-a167-b22b783b4192) | 在严密监督下有时可以联用，不能误扣正确的限定性建议；当天评估、急诊界限及临时用药措辞仍待审核。 |
| `HC-MT-REASON-013` | 梅毒检测不一致及少见的前带现象 | [已发表病例](https://pmc.ncbi.nlm.nih.gov/articles/PMC3139290/)；[CDC 实验室建议](https://www.cdc.gov/mmwr/volumes/73/rr/rr7301a1.htm) | 前带现象少见；特异性检测反应性而 RPR 无反应性还有既往治疗等解释，不能凭来源确诊合成患者。 |

草案类别现为 **分诊 4／用药安全 3／临床推理 3**。四个分诊草案中有两个从低急迫度阴性对照发展为需急诊处理，另一个首轮需及时联系临床团队。这是*题型变化*，并非已证明的难度或统计平衡。已发表病例只用于启发事实机制；未复制患者身份特征、数值、治疗或结局。来源许可尚未完成再分发审核。中文版本在结构中标为 `machine_translation_unreviewed`；临床标签及英中等值性均未独立审核。

## 锚点与评分关口

原有[暂定锚点和回答对照包](S5_CALIBRATION_ANCHORS_2026-10-19_ZH.md)覆盖前 6 题；后续[C 批次包](S5_CALIBRATION_PACKET_C_2026-10-19_ZH.md)为剩余 4 题增加暂定锚点及受控回答对照。分组审计核验各批案例和评分包哈希、来源记录、英中结构、与默认开发题及本地隐藏草案的 ID／来源网址隔离，并报告 **10 题有锚点／0 题无锚点**。这不等于核实医学真值、来源与每条评分条件的对应关系、实际回答排序、真实难度或模型未记忆案例。H49–H54 记录人工审核事项。

**下一批次决策：**请独立临床与双语审核者检查全部 10 题的准确案例版本、来源、逐项标签、暂定锚点及回答对照。合格审核者接受或修订后，才预先注册参考模型，并在另一个冻结样本上检查评判排序、安全错误漏判及满分率。现在不能用这些草案调校评判或发布排名。本地隐藏草案的安全治理也尚未解决。
