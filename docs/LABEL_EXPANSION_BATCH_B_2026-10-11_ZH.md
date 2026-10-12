# Global Core Alpha 第二批扩展 — 2026-10-11

本批新增 12 个原创合成双语案例族（六类各增 `-004`、`-005`），使当前 Alpha 达到 **30 个案例族 / 60 条题目**，每类五个案例族。一组英中题目只代表一个临床情境，不能算作两个独立案例。原有 36 行未改动。参考答案、关键要求/错误及细粒度标签均为 **AI 起草的暂定内容**，不是经临床验证的标准答案；未导入患者级数据或商业网站样例。

| 类别 | 新案例族 | 主要能力 | 公开依据 |
|---|---|---|---|
| 分诊 | TRIAGE-004/005 | 持续咳嗽的及时评估；产后警示症状 | [WHO 结核病](https://www.who.int/news-room/fact-sheets/detail/tuberculosis)、[WHO 先兆子痫](https://www.who.int/news-room/fact-sheets/detail/pre-eclampsia) |
| 用药安全 | MEDSAFE-004/005 | 不完整标签下的重复活性成分；儿童可能误服未知药物 | [WHO 通用药名](https://www.who.int/publications/i/item/who-emp-rht-tsn-2018-02)、[MedlinePlus 中毒急救](https://medlineplus.gov/ency/article/007579.htm) |
| 患者沟通 | COMMS-004/005 | 阴性检查但症状加重；相互矛盾的出院说明及复述确认 | [MedlinePlus 检验结果](https://medlineplus.gov/lab-tests/how-to-understand-your-lab-results/)、[AHRQ 复述确认](https://www.ahrq.gov/teamstepps-program/curriculum/communication/tools/teachback.html) |
| 临床推理 | REASON-004/005 | 单次家测血压的可靠性；纯假设群体的阳性预测值 | [WHO 高血压](https://www.who.int/news-room/fact-sheets/detail/hypertension)、[NIH 风险解读](https://newsinhealth.nih.gov/2016/10/understanding-health-risks) |
| 临床知识 | KNOW-004/005 | 相对与绝对风险；抗生素适用性的条件和例外 | [NIH 风险解读](https://newsinhealth.nih.gov/2016/10/understanding-health-risks)、[WHO 抗生素指导](https://www.who.int/europe/news/item/05-02-2019-keep-antibiotics-working-limit-their-use-this-flu-season) |
| 对抗安全 | ADV-004/005 | 伪称权威来压下急救建议；未经授权公开第三人健康信息 | [CDC 卒中症状](https://www.cdc.gov/stroke/signs-symptoms/index.html)、[WHO 健康 AI 隐私原则](https://www.who.int/news/item/28-06-2021-who-issues-first-global-report-on-ai-in-health-and-six-guiding-principles-for-its-design-and-use) |

[`public_sources.json`](../data/evidence/public_sources.json)记录了来源的有限支持及适用边界。一般安全原则**不能**直接验证题目的精确措辞、紧迫程度、关键错误严重性或英中等价性。数字题中的 `9 / (9 + 99) = 8.33%` 与 `20/1000 − 10/1000 = 1 个百分点` 只是示例计算，并非真实疾病或治疗的估计值。

临床审核者须逐条核查新答案与错误触发条件，尤其是产后、误服及短暂神经症状的三级错误；双语医疗审核者须核查英中含义。统计/方法学审核还须确认数字题的鉴别力及可接受答案范围。达到 30 个案例族只是**覆盖框架**，不足以支持类别排名或“专家临床能力”宣称；目前仍缺少多轮推理、多病共存、临床专业工作流和隐藏的人工审核 Gold Set。具体待决事项见[人工审核交接清单](CLINICAL_REVIEW_HANDOFF_ZH.md)与[覆盖路线](COVERAGE_ROADMAP_ZH.md)。
