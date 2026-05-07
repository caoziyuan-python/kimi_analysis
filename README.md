```markdown
# K2.6 External Feedback Monitor

轻量的内部分析工具，用来观察外部用户对 Kimi / K2.6 的反馈信号。

核心目标：把 Reddit、Hacker News、GitHub 和已有中文平台样本里的原始用户声音，按 funnel stage 分组，生成每周简报和信号明细，供分析师直接使用。

## 当前功能

- 浏览 v0 baseline 数据，当前 1542 条
- 本地采集 Reddit / Hacker News / GitHub 新反馈
- 调用 Moonshot API 给新数据打标签
- 合并到 `data/monitoring/labeled_monitoring.csv`
- 在 Streamlit UI 里查看三个视图：
  - **Weekly Brief**：中文周报，直接列出本周值得关注的信号和建议验证的内部指标
  - **Signal Explorer**：按 funnel stage 浏览信号，查看原始评论、LLM 解读、边界说明
  - **Full baseline**：浏览完整历史数据

## 数据来源

- Baseline：知乎 / 小红书 / 微博 / Reddit / Hacker News 的 v0 静态样本
- Monitoring：Reddit / Hacker News / GitHub，本地或定时采集

中文平台只作为 baseline 使用，不进入自动采集。原因是反爬和页面变化会让云端自动化不稳定。

## 数据契约

核心 CSV schema：

```text
id
platform
url
author
content
created_at
collected_at
sentiment
funnel_stage
scenario
feedback_type
confidence
source_dataset
```

原始评论 `content` 是主内容，不做摘要替代。

## 快速运行

安装依赖：

```powershell
pip install -r requirements.txt
```

配置环境变量：

```powershell
copy .env.example .env
```

然后在 `.env` 里填：

```text
MOONSHOT_API_KEY=你的 key
```

启动 UI：

```powershell
streamlit run src/ui/app.py
```

## 手动采集新数据

小批量采集并标注：

```powershell
python scripts/refresh_now.py --days 30 --limit 50 --max-label 50
```

如果采集很多数据，建议分批 labeling：

```powershell
python scripts/label_pending_monitoring.py --batch-size 10 --sleep-seconds 30 --max-rows 100
```

重新生成 interpretation：

```powershell
python scripts/regenerate_interpretations.py
```

生成周报：

```powershell
python scripts/generate_weekly_brief.py
```

## 设计思路

```text
外部原始评论
→ 清洗
→ LLM 标签
→ 按 funnel_stage / scenario / feedback_type 分组
→ 生成每个 signal 的谨慎解读
→ 汇总为中文周报
→ 提醒需要内部数据验证
```

LLM 只做辅助解释，不输出结论。UI 不调用任何 LLM，所有解读结果均从缓存读取。

## 已知边界

- 外部反馈不能代表全部用户
- Reddit / HN / GitHub 样本偏技术用户
- 中文平台数据是静态 baseline
- Annotation F1 = 0.78，测试集为中文 baseline 数据，英文 monitoring 数据未单独评估
- Weekly Brief 反映的是采集窗口内观察到的信号，不等同于真实趋势
- 所有业务判断都需要内部数据交叉验证

## 目录结构

```text
config/                 配置和 prompts
data/baseline/          v0 baseline
data/monitoring/        weekly / manual refresh 数据
data/interpretations/   cached LLM interpretation 和 weekly brief
src/collectors/         Reddit / HN / GitHub 采集
src/pipeline/           clean / label / merge / evaluate
src/interpretation/     signal grouping 和 interpretation
src/ui/                 Streamlit UI
scripts/                本地刷新和批处理脚本
```

## 部署

Streamlit Community Cloud URL：

```text
TODO
```