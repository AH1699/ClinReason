# 外部模型试运行交换格式 — 中文

这是一个**本地、实验性的集成流程**，不是临床评测结果。当前配置的 60 条 Alpha 题目都是合成草稿；评审模型与临床医生的校准尚未完成。基于文件的试运行不需要 API 密钥；可选的 Gemini 运行器仅在指定 `--live` 时发起可能计费的请求。

## 1. 导出模型可见输入

```bash
python3 -m benchmark.cli --config config/benchmark.json export-prompts \
  --output work/candidate_prompts.jsonl
```

每行 JSONL 包含 `case_id`、`case_version`、SHA-256 `case_content_hash`、`language`、`prompt_template_version`、`instruction` 和 `prompt`。导出器使用明确的字段白名单：**不会向被测模型发送参考答案、关键要求、关键错误标签、类别或审核意见**。哈希将后续回答绑定到精确案例版本，不是答案。已有文件不会被覆盖。

进程内的 `CandidateProvider.generate()` 路径也仅获得案例 ID、版本、语言及题目。直接适配器应自行添加获准的候选指令，不得从数据集读取隐藏参考答案。

## 可选：在本地运行 Gemini

在项目根目录将 `.env.example` 复制为 `.env.local`，并在其中填写 `GEMINI_API_KEY`；也可自行设置同名环境变量。不要把密钥发到聊天、放进命令行或受版本控制的配置文件，更不能让未来的网页前端直接持有密钥。`.env.local` 已加入 git 忽略规则；提交前仍需确认它没有被跟踪。运行器只按文本读取该文件，不会执行其中的命令。建议仅允许本人读取，例如执行 `chmod 600 .env.local`。Google 的[密钥指南](https://ai.google.dev/gemini-api/docs/api-key)也建议应用在服务端保管密钥；未来仪表板应通过后端调用模型。

先做无网络、无密钥的预检：

```bash
python3 -m benchmark.cli --config config/benchmark.json generate-gemini \
  --model YOUR_EXACT_GEMINI_MODEL_ID --limit 1 \
  --output work/candidate_gemini_smoke.jsonl
```

从[可用模型列表](https://ai.google.dev/gemini-api/docs/models)选择模型 ID 后，运行一个真实案例：

```bash
python3 -m benchmark.cli --config config/benchmark.json generate-gemini \
  --model YOUR_EXACT_GEMINI_MODEL_ID --limit 1 --live \
  --output work/candidate_gemini_smoke.jsonl
```

检查该回答后，再用新路径显式运行全部 60 条题目：

```bash
python3 -m benchmark.cli --config config/benchmark.json generate-gemini \
  --model YOUR_EXACT_GEMINI_MODEL_ID --limit 60 --live \
  --output work/candidate_gemini_answers.jsonl
```

默认上限是一个案例，真实调用始终需要 `--live`。运行器使用与导出器相同的白名单，只把指令和题目发送给 [Gemini Interactions API](https://ai.google.dev/api/interactions-api-v1)，并设置 `store: false`；不会请求 Google 搜索或其他工具。回答文件记录文本、耗时及可获得的 token 计数；本地清单记录请求及返回的模型 ID 和精确案例版本。两份文件都不含密钥，并已被 git 忽略。返回的模型 ID 不一定代表不可变的模型快照，如需更严格复现，应另行记录提供商的版本信息。HTTP 429/5xx 最多重试两次；传输故障可能已送达并计费，因此不会自动重试。失败或未完成的交互不生成回答文件，也不会覆盖现有文件。单例预检文件不足以导入要求 60 条题目完整回答的运行。

## 2. 运行模型并准备回答

对导出的每行，只向模型发送 `instruction` 和 `prompt`。把每个回答写成新 JSONL 文件的一行，并从导出文件准确复制三个身份字段：

```json
{"case_id":"HC-GC-TRIAGE-001-EN","case_version":"0.1.0","case_content_hash":"<从导出文件复制完整的 64 字符哈希>","text":"<模型回答>"}
```

可选字段：`finish_reason`（字符串或 null）、`latency_ms`（非负整数或 null）和 `token_usage`（非负整数计数器组成的对象或 null）。回答文件不要包含题目、参考答案、密钥或患者信息。导入器要求**每个已配置案例恰好有一个非空回答**，拒绝重复、未知 ID、过期哈希/版本及未知字段。若模型拒答，应保存真实输出，不能编造回答；传输故障或未完成的交互不属于候选回答。

## 3. 导入并检查运行

```bash
python3 -m benchmark.cli --config config/benchmark.json import-responses \
  --input work/candidate_answers.jsonl \
  --provider my-provider --model-id my-model --model-version my-snapshot
```

命令返回 `run_id`，并把模型回答存入 `work/benchmark.sqlite3`。模型身份在运行时提供，不能仅凭宣传名称推断。导入前会检查案例数据；已有 ID/版本的内容变更不能被静默覆盖。

导入 Gemini 回答时，`--provider` 使用 `google-gemini`，`--model-id` 使用实际请求的模型 ID，`--model-version` 使用生成清单中的 `returned_model`。返回 ID 仍可能是别名；未经提供商保证，不应声称具有不可变快照级别的可复现性。

## 4. 仅测试评分管线

```bash
python3 -m benchmark.cli --config config/benchmark.json score-imported-demo RUN_ID
python3 -m benchmark.cli --config config/benchmark.json report RUN_ID
```

`score-imported-demo` 使用两个**模拟**评审模型。它们只是确定性的词汇匹配测试组件，不是临床专家；分数没有临床解释。命令要求每个快照案例有一个尚未评分的回答，也不会重新评分同一运行。报告明确标为 `experimental_unvalidated`，包含逐案例维度分数、关键错误/人工复核标记、按模型的类别和语言分组、案例微平均、类别宏平均及覆盖率。每类仅五个案例族，因此即便评审者合格，类别均值仍会非常不稳定。

## 尚需完成

- 扩展其他候选模型适配器，并加强提供商版本追踪、成本控制、断点续跑和可用时的不可变模型快照记录。Gemini 适配器只是首个本地试运行组件，不是通用生产连接器。
- 构建独立的真实评审模型适配器，验证输出结构并处理失败；用人工标注回答校准。
- 在解释模型表现之前完成合格的临床与双语案例审核；分离开发、校准和隐藏 Gold 数据。
- 对外比较前报告样本量、不确定性区间及关键错误率。不得把此次试运行的模拟分数解释为排名。
