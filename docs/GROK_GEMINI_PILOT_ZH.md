# 本地 Grok → Gemini 试运行

这是**实验性集成测试**，不是经过验证的医疗基准。Grok 是被测模型；Gemini 是唯一的临时 AI 评审。24 个双语 Alpha 案例及参考答案仍是草稿。这个流程不能完成临床或语言审核门槛。

## 本地配置

已被 Git 忽略的 `.env.local` 包含四个字段：

```text
GROK_API_KEY=replace-with-your-key
GROK_MODEL=grok-4.7
GEMINI_API_KEY=replace-with-your-key
GEMINI_JUDGE_MODEL=gemini-3.8-flash
```

请只在自己的电脑上替换两个密钥占位符；不要在聊天中发送密钥，也不要提交密钥。模型 ID 不是秘密，但放在配置中可明确记录每次请求。命令行的 `--model` 可覆盖配置。程序只按纯文本读取文件，不执行其中的内容。提供的本地文件已被 Git 忽略，且权限仅允许本人读取。单独的 `.env` 也已忽略；若选用它，可指定 `--env-file .env`。请在 [xAI 模型列表](https://docs.x.ai/developers/rest-api-reference/inference/models)及 [Gemini 模型列表](https://ai.google.dev/gemini-api/docs/models)确认账号可用型号。模型别名可能变化；返回的模型 ID 不一定是不可变快照。

## 1. Grok 生成候选回答

无密钥、无网络预检：

```bash
python3 -m benchmark.cli generate-grok --limit 1 --output work/candidate_grok_smoke.jsonl
```

真实运行一个案例，并在本地检查回答及清单：

```bash
python3 -m benchmark.cli generate-grok --limit 1 --live --output work/candidate_grok_smoke.jsonl
```

用新路径运行全部案例：

```bash
python3 -m benchmark.cli generate-grok --limit 24 --live --output work/candidate_grok_answers.jsonl
```

运行器调用 [xAI Responses API](https://docs.x.ai/developers/rest-api-reference/inference/responses) 并设置 `store: false`。只发送获准的候选指令和案例题目，不发送参考答案、评分量表或关键错误标签。结果记录回答、耗时、可获得的 token 计数、请求及返回的模型 ID，以及精确案例版本。失败或未完成的响应不会生成回答文件；传输故障可能已送达，因此不自动重试。HTTP 429/5xx 最多重试两次。单例文件不能作为完整运行导入。候选模型的完整运行目前不能断点续跑，重试可能增加费用。

## 2. 导入精确版本的回答

从 `work/candidate_grok_answers.manifest.json` 读取 `returned_model`，填入 `--model-version`：

```bash
python3 -m benchmark.cli import-responses \
  --input work/candidate_grok_answers.jsonl \
  --provider xai-grok --model-id grok-4.7 --model-version RETURNED_MODEL_ID
```

记下返回的 `run_id`。如果覆盖了 `GROK_MODEL`，`--model-id` 也要改为实际请求的 ID。导入器会拒绝缺失、重复或案例哈希过期的回答。

## 3. Gemini 临时评审

评审可见候选回答，以及**草稿**参考答案、关键要求、关键错误和量表；不会看到 Grok 的身份。Gemini 的[结构化输出](https://ai.google.dev/gemini-api/docs/structured-output)要求 JSON；本地校验会拒绝未知维度、不适用维度的分数、编造的关键错误 ID、被修改的严重程度及格式错误。

```bash
python3 -m benchmark.cli judge-imported-gemini RUN_ID --limit 1
python3 -m benchmark.cli judge-imported-gemini RUN_ID --limit 1 --live
python3 -m benchmark.cli judge-imported-gemini RUN_ID --limit 24 --live
python3 -m benchmark.cli report RUN_ID
```

第一条命令仅预检，不访问网络。第一次真实调用评审一例；下一次评审余下 23 例，仅在 24 例均有有效评审后评分。与候选模型运行不同，成功的评审会逐条保存，失败后可继续。每次请求都设置 `store: false`，不启用搜索工具，并记录所选 Gemini 模型。报告仍标为 `experimental_unvalidated`。一个未校准的 AI 评审、每类仅两个草稿案例族，不足以支持临床结论、模型排名或安全认证。仍需合格临床和双语审核者、独立评审及人工校准。
