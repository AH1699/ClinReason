# 外部模型试运行交换格式 — 中文

这是一个**本地、实验性的集成流程**，不是临床评测结果。当前配置的 24 个 Alpha 案例都是合成草稿；真实评审模型适配器及评审模型与临床医生的校准尚未完成。基于文件的试运行不需要 API 密钥或专有模型端点。

## 1. 导出模型可见输入

```bash
python3 -m benchmark.cli --config config/benchmark.json export-prompts \
  --output work/candidate_prompts.jsonl
```

每行 JSONL 包含 `case_id`、`case_version`、SHA-256 `case_content_hash`、`language`、`prompt_template_version`、`instruction` 和 `prompt`。导出器使用明确的字段白名单：**不会向被测模型发送参考答案、关键要求、关键错误标签、类别或审核意见**。哈希将后续回答绑定到精确案例版本，不是答案。已有文件不会被覆盖。

进程内的 `CandidateProvider.generate()` 路径也仅获得案例 ID、版本、语言及题目。直接适配器应自行添加获准的候选指令，不得从数据集读取隐藏参考答案。

## 2. 运行模型并准备回答

对导出的每行，只向模型发送 `instruction` 和 `prompt`。把每个回答写成新 JSONL 文件的一行，并从导出文件准确复制三个身份字段：

```json
{"case_id":"HC-GC-TRIAGE-001-EN","case_version":"0.1.0","case_content_hash":"<从导出文件复制完整的 64 字符哈希>","text":"<模型回答>"}
```

可选字段：`finish_reason`（字符串或 null）、`latency_ms`（非负整数或 null）和 `token_usage`（非负整数计数器组成的对象或 null）。回答文件不要包含题目、参考答案、密钥或患者信息。导入器要求**每个已配置案例恰好有一个非空回答**，拒绝重复、未知 ID、过期哈希/版本及未知字段。若模型拒答或报错，应保存真实输出，不能编造回答；未来自动运行器还应单独记录传输故障。

## 3. 导入并检查运行

```bash
python3 -m benchmark.cli --config config/benchmark.json import-responses \
  --input work/candidate_answers.jsonl \
  --provider my-provider --model-id my-model --model-version my-snapshot
```

命令返回 `run_id`，并把模型回答存入 `work/benchmark.sqlite3`。模型身份在运行时提供，不能仅凭宣传名称推断。导入前会检查案例数据；已有 ID/版本的内容变更不能被静默覆盖。

## 4. 仅测试评分管线

```bash
python3 -m benchmark.cli --config config/benchmark.json score-imported-demo RUN_ID
python3 -m benchmark.cli --config config/benchmark.json report RUN_ID
```

`score-imported-demo` 使用两个**模拟**评审模型。它们只是确定性的词汇匹配测试组件，不是临床专家；分数没有临床解释。命令要求每个快照案例有一个尚未评分的回答，也不会重新评分同一运行。报告明确标为 `experimental_unvalidated`，包含逐案例维度分数、关键错误/人工复核标记、按模型的类别和语言分组、案例微平均、类别宏平均及覆盖率。每类仅两个案例族，因此即便评审者合格，类别均值也会非常不稳定。

## 尚需完成

- 为具体模型端点构建直接 API 适配器，安全管理密钥、超时、重试、错误记录及精确模型版本。
- 构建独立的真实评审模型适配器，验证输出结构并处理失败；用人工标注回答校准。
- 在解释模型表现之前完成合格的临床与双语案例审核；分离开发、校准和隐藏 Gold 数据。
- 对外比较前报告样本量、不确定性区间及关键错误率。不得把此次试运行的模拟分数解释为排名。
