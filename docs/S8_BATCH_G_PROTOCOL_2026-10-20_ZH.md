# S8：G 批次评分与双语协议检查点 — 2026-10-20

G 批次仍是**四个公开合成患者案例族／八个英中版本**；开发集总量不变，仍为**112 族／224 版本**。本次**没有修改案例、历史回答、数值权重、临床得分、校准／隐藏集分组或默认候选提示**，也没有调用模型。已批准校准集与隐藏 Gold 均为 **0**。所有锚点、译文及人工编写的回答示例仍是未经专家审核的开发假设。

## 已可离线核验的内容

- [G 批次逐条件暂定锚点](../config/multiturn_criterion_anchors_batch_g_v1.json)覆盖四族 × 两轮 × 三项，即 **24 项行为要求**；为每项描述满足、部分满足、未满足和可接受的等价回答。每族绑定英中案例准确哈希、一个公开主要来源、重大错误边界及日后专家问题。英文写成的锚点暂用于双语；结构对应不等于语义等价。
- [八个英中对照](../data/multiturn/batch_g_contrasts_v1.json)各含一轮初始回答及优秀、部分正确、故意不安全的后续回答，共 **24 个受控后续回答**。不安全回答分别测试仅凭红眼外观／局部皮疹过度升级、仅凭黄色鼻涕使用抗生素、仅凭培养异常标记使用抗生素或急诊。[离线核验程序](../benchmark/batch_g_contrasts.py)会拒绝旧案例哈希、未知错误 ID、语言版本缺漏及空白／重复示例；它**不能**证明临床正确，也不能证明 AI 评审能正确排序。
- [G 批次试验名单](../config/model_matrix_batch_g_v1.json)只选这八个版本，候选与双评审模型 ID 与 F 批次预先登记的名单相同。全量预览为 **48 次候选 + 48 次评审 = 96 次 API 调用**；次数上限不等于费用上限，更不是对外排名许可。
- [候选双语提示 v2](../config/candidate_prompt_bilingual_v2.txt)明确要求每轮使用用户语言作答，容许惯用医学术语。[旧默认提示](../config/candidate_prompt.txt)不变。矩阵运行、已存回答恢复评审和离线组装都可指定 `--candidate-prompt`；清单／报告会绑定提示哈希，指定新提示的预览也显示哈希。恢复或组装必须指定与原始记录相同的版本，不能把 F 和 G 的得分当作相同提示协议比较。
- [独立回答语言审计](../benchmark/answer_language_audit.py)现可用 `--candidate-prompt` 核对每份回答侧车清单的提示哈希与准确案例版本，然后仅标记明显的文字系统不符。它**不产生语言得分，也不改临床得分**。未被标记不代表通过；中英混写、表达能力、译文含义及临床等价仍需双语专家审核。历史 F 回答没有使用 v2 提示，不能追溯宣称符合 v2。

起草时重新核查了 [NHS 红眼资料](https://www.nhs.uk/symptoms/red-eye/)、[Moorfields 患者资料](https://www.moorfields.nhs.uk/ae/patient-guides/subconjunctival-haemorrhage)、[AAAAI 乳胶反应资料](https://www.aaaai.org/tools-for-the-public/conditions-library/allergies/latex-allergy)、[CDC 成人门诊抗生素资料](https://www.cdc.gov/antibiotic-use/hcp/clinical-care/adult-outpatient.html)及 [IDSA 无症状菌尿指南](https://www.idsociety.org/practice-guideline/asymptomatic-bacteriuria)。这些英美来源只为合成题提供依据，不能证明特定患者处置或全球通用流程。[OpenAI 评测指导](https://developers.openai.com/api/docs/guides/evaluation-best-practices)提示我们使用针对任务的对照、记录准确协议，并保留人工校准关口；本项目使用自有本地评测器，而不是托管 Evals 平台。

## 下一个关口

先用 `python3 -m benchmark.batch_g_contrasts` 和 G 名单、锚点、新提示的 `model-matrix` 预览确认准确绑定；`judge-anchored-contrast --probe-set data/multiturn/batch_g_contrasts_v1.json --case-id HC-MT-TRIAGE-018-EN --anchors config/multiturn_criterion_anchors_batch_g_v1.json --output-dir work/batch_g_contrast_018_en_preview` 在不加 `--live` 时不会调用模型。将来检查已存回答时，可用 `python3 -m benchmark.answer_language_audit --candidate-prompt config/candidate_prompt_bilingual_v2.txt --answer-file <准确回答文件>`；回答旁必须有 `.manifest.json`。本地密钥与原始回答仍须留在 Git 忽略区。本检查点 **153 项本地测试通过**，G 对照绑定、双轮数据、组合及缺口审计也通过；这些只是工程检查，不等于临床／语言人工批准。

**下一技术步骤：**对一至两个降级案例的英中优秀／部分／不安全对照，开展小规模、明确调用次数上限的双评审敏感性试验，分别观察排序和预设错误检出；如可解释，再在完全相同且已版本化的协议下做有限候选比较，并分开报告临床分、提示版本和语言标记。若排序或过度／不足分诊锚点有问题，回到待审问题清单，不能为了分段目标调分。与潜在伙伴讨论期间，可推迟合格临床、逐条件来源与双语审核，但正式校准或对外声称前仍必须完成。低档约 60–70、中档约 80、高档约 90 仍是不强制拟合的诊断期望。
