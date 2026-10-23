# 已购资料快速盘点及数据团队交付要求 — 2026-10-22

这是**目录与代表页面快速检查**，不是逐文件版权、隐私、临床、OCR 或标签审核。原始 `purchasedAssets/` 已加入 Git 忽略。没有将已购题目、患者原文／图片或临床事实导入案例、来源库或模型请求；现有分数也未变动。

## 三个目录的结论

| 目录 | 实际内容 | 用途与优先级 | 启用前条件 |
|---|---|---|---|
| `2.Usmle world step2` | 68 份 PDF，约 57,687 页／16 GB。抽样 `Cardiovascular.pdf` 可提取病例题及答案文本；`Cardiovascular System - 8 Blocks.pdf` 以截图为主；`UW - Objectives - System - ALL.pdf` 是可提取的主题索引。 | 在权利核实之后，病例题型材料**可能**用于开发；主题索引可帮助查覆盖缺口，但不是临床答案来源。Step 2 比 Step 1 更贴近病例推理。 | 目录没有授权文件。部分文件名或页面出现 `Z-Library`、Telegram 等二次传播迹象。须有实际权利人明确书面许可，涵盖商业衍生题、翻译、保存、模型 API 处理及预期发布。 |
| `4.Usmle world step1` | 283 份 PDF、8 份 RAR，约 51,166 PDF 页／14 GB。抽样 2024 心血管题集为截图／OCR 式文本；另有 First Aid 教材、旧笔记和压缩包。 | **低优先级。** 权利清楚时可用主题／基础机制清单检查覆盖，不直接复制题目，也不能把考试解析视为临床 Gold。 | 同样须核实版权、版本、重复率和 OCR；日常接收不必解开旧压缩包。 |
| `ClinicalDataXiAn` | 50 份 PDF、90 页／25 MB，抽样均为图像页，基本无法直接提取文字。入院、出院、病程、手术、病理、化验和其他报告**看起来属于同一神经外科住院经过**，入院页至少有重复副本；50 份文件不等于 50 个独立案例。 | **最适合做一个复杂真实病历衍生案例的试点。** 优先整理 `入院记录.pdf`、`病程记录.pdf`、`其他报告单*.pdf`、`常规化验报告单*.pdf`、`手术记录单*.pdf`、`病理报告.pdf`、`出院记录_死亡记录.pdf` 的同一时间线；同意书和风险评估表对题目编写较次要。 | 姓名／ID 空白不等于匿名。精确日期、罕见病情组合及图片内信息仍需正式去标识化与重识别风险审核；核实医院／数据控制者授权、合法处理依据、外部 AI 处理和跨境传输。原始扫描件不得传给候选／裁判 API 或提交 Git。 |

这不是认定采购无效，而是说**本目录未附可核实的权利证明**。第三方卖方的“可商用”声明必须能追溯到真实权利人；改写成新措辞也不能自动消除版权或基准泄漏风险。同一患者／同一事件的全部文件及衍生题须在同一个分组，不能跨开发、校准和隐藏测试集。

## 可直接转给数据团队的采购／整理指令

> 首批采购并交付 **30 个不同患者、可完整关联的临床事件**，不是 30 份 PDF：动态分诊 10 个、用药安全 10 个、诊断推理 10 个。至少 20 个事件有两个或以上具有决策意义的时间点；同时包含良性／阴性与严重结局，避免只选罕见重症。优先选择证据冲突或演变、合并症／多药、鉴别不确定、随访决策明确、结局可核查的事件。成人、老年、孕产及儿科的比例以合法授权和审核能力为前提；罕见组合须特别评估可识别性。
>
> 每个来源提供实际版权人或医疗数据控制者签署的许可／处理证明：商业基准用途、衍生／改写案例、英中翻译、内部保存、交临床审核、向指定外部模型服务商传输（或明确禁止）、公开提示词／标签／汇总、地域、期限、署名、撤回与删除限制。考试题须证实原权利人授权，转售发票或普通订阅不够。临床病历另附隐私、去标识化、处理和传输审批；请法务／隐私负责人确认适用中国及其他法律要求。
>
> 交付 UTF-8 结构化数据，勿只给扫描 PDF。每个去标识化事件须有 `episode_id`、权利来源 ID、就医场景及法域、仅在必要时提供的年龄段／性别、相对时间线、症状及重要阴性、生命体征、合并症、过敏、药品名称／剂量／途径／频次／变化、检查数值及原单位／参考范围／相对采样时间、影像／病理解读、干预、结局／随访、缺失或不确定性。保留原单位，并另存标准化单位；身份对照表及精确患者日期／时间留在数据控制者受限环境。OCR 文本须回链到文档和页码；用于标签的事实逐项人工核对，嵌入图片单独检查标识。
>
> 每个拟入库的**决策点**分别交付：当时模型可见事实 `prompt_facts`、后续才披露事实 `later_facts`、目标角色与任务、核心临床能力、可接受的安全答案范围、可观察的 `critical_requirements`、禁止的 `critical_errors` 及拟议严重度、合理替代方案、证据不足和法域界限，并把每一项答案要求对应到独立且现行的指南／药品说明书。后来的诊断、病理和真实结局不能提前泄漏在提示词中；现实中采取的医疗措施**不自动等于正确答案**。标签先记为 `draft`，经合格临床、双语、方法学审核后才可能升级；英中版本须作意义等价审核，不得把机器翻译直接当 Gold。

## 推荐交付格式

```text
delivery/
  rights_manifest.csv          # 每个版权／数据来源一行，含许可范围及凭证
  episodes.jsonl               # 每个已去标识化事件一行
  observations.csv             # 每个生命体征、化验或其他测量一行
  medications.csv              # 每次用药／变更一行
  document_index.csv           # 事件、文件、类型、相对时间、页数、OCR 质检
  decision_points.jsonl        # 每个候选基准决策点一行
  answer_labels.jsonl          # 参考行为、要求、禁错和可接受替代答案
  evidence_sources.csv         # 独立指南／药品说明书、版本、适用人群及许可
  source_to_label.csv          # 决策点、要求、证据位置及其适用限制
  review_status.csv            # 版权、隐私、OCR、临床、语言、方法学关口
  deidentification_report.pdf  # 方法、剩余风险、批准人及限制；不含身份对照表
  restricted_source_docs/      # 只通过批准的安全渠道传送；不进 Git／普通模型 API
```

`rights_manifest.csv` 至少包括 `asset_id,source_title,version,original_rightsholder,grantor,contract_id,proof_location,commercial_use,derivative_cases,translation,model_api_processing,prompt_publication,label_publication,geography,expiry,attribution,restrictions,approval_status`；每项使用明确的 `yes/no/unknown`，`unknown` 即暂缓。`episodes.jsonl` 至少包括 `episode_id,source_asset_id,linkage_group_id,jurisdiction,setting,age_band,sex_if_relevant,timeline,outcome_summary,privacy_status`。`decision_points.jsonl` 至少包括 `decision_point_id,episode_id,relative_time,role,language,category,prompt_facts,later_facts,status`。`answer_labels.jsonl` 至少包括 `decision_point_id,language,reference_behavior,critical_requirements,critical_errors,acceptable_alternatives,uncertainties,jurisdiction_limits,source_ids,review_status`，须与模型可见的决策点分开。`evidence_sources.csv` 至少包括 `source_id,publisher,title,version,publication_date,access_date,stable_url_or_doi,jurisdiction,license_or_access_terms,applicable_population,limitations`。使用稳定 ID、UTF-8、明确空值和数据字典；患者时间改用相对小时／天。CSV 按 RFC 4180 格式，无合并单元格或 Excel 公式。FHIR R4 `Observation`／`DiagnosticReport` 可作为额外源格式，但仍须交决策点及标签包。

**验收：**一个试点事件须先完成权利与隐私审批、关联去重、OCR 质检、决策时点泄漏检查及逐条来源—标签映射，才能进入内部写题；此时仍只是 `draft`。西安原始扫描件不得进入 `data/alpha/`。下游结构参见 `schemas/case.schema.json` 与 `schemas/multiturn-pilot.schema.json`。

核对资料（2026-10-22）：[UWorld 条款](https://www.uworld.com/terms_conditions.aspx)、[中国个人信息保护法](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm)、[美国 HHS 去标识化指南](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html)（仅参考，不能代替中国法审核）、[HL7 FHIR R4 DiagnosticReport](https://hl7.org/fhir/R4/diagnosticreport.html)。本文件是操作性接收要求，不构成法律或临床批准。

## 与评分工作的衔接

[S23 离线评分边界审核](S23_OFFLINE_SCORING_BOUNDARIES_2026-10-22_ZH.md)仍是当前决定记录；这些采购文件无法裁定三项临床／双语争议。旧分数和比较暂缓不变。下一工程步骤是另立前瞻版本，规定“要求／独立安全后果／新信息修订”各自的证据格式与测试样例，等合格人员裁决后才可能强制执行或校准。本次盘点不支持新增模型调用或调分。
