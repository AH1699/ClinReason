# 开发阶段多模型测试矩阵 — 2026-10-15

## 已完成的能力

本地程序可让 Gemini、Grok、MiniMax **各两个模型**回答同一批固定的公开、双轮患者场景。六个候选模型及两个评判模型的具体 ID 见 [`config/model_matrix.json`](../config/model_matrix.json)。Gemini 3.8 Flash 和 Grok 4.7 分别对**同一份回答**、同一套暂定标签及评分规则打分；报告保留两份分数及差异，不自动取平均，也不宣布模型排名。评判输入不包含候选模型身份；同厂商、同一模型自评都会标记。

默认样本仅有 `HC-MT-TRIAGE-008` 的英文和简体中文两个版本，目的是验证流程，**不足以衡量难度或语言公平性**。单个模型、单个语言版本需两次候选调用及两次评判调用。全部六个模型运行两个版本共计划 **48 次逻辑 API 调用**；自动重试已关闭。模型别名、可访问权限和默认采样可能变化，不同厂商的对话请求格式也不完全相同。运行前可查看 [Gemini 模型列表](https://ai.google.dev/api/models)、[xAI 模型](https://docs.x.ai/developers/models)、[MiniMax 模型列表](https://platform.minimax.io/docs/faq/models)。MiniMax 适配器使用官方 [Chat Completions 接口](https://platform.minimax.io/docs/api-reference/text-chat-openai)，只发送已出现的对话，不读取推理文本；其回答上限为 2048 token，超长截断回答会被拒绝，这也是跨服务商比较的混杂因素。与 Gemini/xAI 不同，MiniMax 请求没有已记录的 `store=false` 参数；清单会如实注明。发送任何非公开内容前应审查服务商的数据处理条款。

## 本地运行

密钥仅放在 Git 忽略的 `.env.local`：`GEMINI_API_KEY`、`GROK_API_KEY`、`MINIMAX_API_KEY`。**模型名称写在矩阵配置文件中**，不是密钥文件中。可参考仓库中的 `.env.example`。不要把可识别患者资料、非公开案例或密钥放进配置或仓库。

```bash
# 预览完整计划：无需密钥，不联网，不生成文件。
python3 -m benchmark.cli model-matrix

# 首次小范围实测：一个 MiniMax 模型、一个英文案例，共四次调用。
python3 -m benchmark.cli model-matrix \
  --candidate-id minimax-m27 --case-id HC-MT-TRIAGE-008-EN \
  --output-dir work/model_matrix_minimax_m27_first \
  --max-api-calls 4 --live

# 对一个模型固定三个不同机制的案例：计划 12 次调用。
python3 -m benchmark.cli model-matrix --candidate-id minimax-m27 \
  --case-id HC-MT-TRIAGE-003-EN \
  --case-id HC-MT-MEDSAFE-003-EN \
  --case-id HC-MT-REASON-004-EN
```

`--live` 必须同时设置足够的 `--max-api-calls`，程序会在付费调用前检查所需密钥。可重复 `--case-id` 固定多个案例。输出目录必须是新的。完成的候选回答和两份评判分别保存在被 Git 忽略的目录里；所有选中项目完成后才生成 `report.json`。中途失败可能仅留下 `plan.json` 和部分结果；由于网络失败时无法确定请求是否送达或计费，程序**不会自动恢复或重试**。人工核查后，如需重试应使用新目录。调用次数上限不是金额上限，运行前还应查看服务商价格和余额。`compare-model-matrix` 仅在案例哈希、两个评判模型、评分规则和提示一致时合并已完成的单模型报告，仍不构成临床排名。

## 验证及当前实测状态

新增八项离线测试，覆盖模型配置、无网络预览、MiniMax 请求与响应、独立盲评、文件及密钥处理、调用上限和固定条件下的报告比较。完整测试目前 **114 项通过**。本机尚未配置 MiniMax 密钥，因此**没有 MiniMax 在线调用**。受限工作区的最初尝试因无法解析 API 域名而失败；正式的送达状态仍视为未知，均未产生分数。随后使用另行获准的联网通道，四个候选模型各完成一个案例：共 **16 次逻辑 API 调用**，每个案例有两轮候选回答，以及 Gemini、Grok 各一次评判。原始对话、评判和比较文件都在 Git 忽略的 `work/` 目录，不会推送。

| `HC-MT-TRIAGE-008-EN` 候选模型 | Gemini 评判 | Grok 评判 |
|---|---:|---:|
| Grok 4.6 | 100 | 100 |
| Grok 4.7 | 100 | 100 |
| Gemini 3.5 Flash-Lite | 100 | 100 |
| Gemini 3.8 Flash | 100 | 100 |

八份评判都给两轮的安全性、要求满足度及修订能力 4/4，也没有标记既定重大错误。Grok 对 Gemini 3.5 Flash-Lite 的回答要求人工复核；无论模型是否主动标记，确定性评分层都要求**全部**回答人工复核。这道题**不能区分这四个模型**，但不足以证明整个基准过于简单。Gemini/Grok 候选分别可能受到一个同厂商评判员的偏好影响。比较结果保存在 `work/model_matrix_four_model_comparison_2026-10-15.json`。

先前计划的同题三种回答 Gemini 对照实验也在获准的联网通道完成：优秀回答 **100**，部分正确 **82.5**，不安全回答 **20**。评判员识别了“不呼救而在家等待”的预设重大错误，并因部分正确回答遗漏“如已有处方自动注射器则按说明使用”的条件建议而扣分。因此，这个评判员能区分这道题中受控改写的回答，虽然四个自然生成回答都拿满分。这只是**一个评判员、一道合成英文题**，不是临床校准，也不能证明与 TRIAGE-001 的重叠问题已解决。原始文件为 `work/triage_008_overlap_probe_network_2026-10-15.json`。

## 解读及下一关口

这些公开合成案例、暂定临床标签及未经复核的翻译，不能用于公开临床排名。Gemini 候选由 Gemini 评判或 Grok 候选由 Grok 评判，可能产生同厂商偏好；两个 AI 评判员也不等于独立临床真值。仍需人工评分校准、重复运行、逐条来源与标签核对，以及预先划分的隐藏测试集。矩阵因此分别报告两份评判结果，并强制保留人工复核状态。[评分器验证建议](https://developers.openai.com/api/docs/guides/graders)也强调应使用多样回答和人工真值检验评分器；本项目不使用 OpenAI 托管评分器。

下一步是在本地配置 `MINIMAX_API_KEY`，两个 MiniMax 模型各先跑一个案例（每个四次调用）。再预先登记一个**机制平衡的小样本**，例如 TRIAGE-003、MEDSAFE-003、REASON-004 的中英文版本，让选定的候选模型在完全相同的样本上接受双评判。重复 `--case-id` 即可，无需修改模型列表。扩大费用前先检查满分比例、评判分歧、第一轮安全与修订得分，以及跨语言表现。单凭 TRIAGE-008 的高分不能证明基准足够难或临床有效。专业临床人员案例属于独立轨道，尚未在此矩阵启用。
