LABELING_SYSTEM_PROMPT = """你是一个产品分析助手，对AI产品用户反馈进行分类标注。
严格按JSON格式输出，不输出任何其他内容。"""

LABELING_PROMPT = """请对以下用户反馈进行分类标注：

内容：{content}

输出格式（只输出JSON，不要有其他文字）：
{{
  "sentiment": "positive或negative或neutral",
  "funnel_stage": "activation或success或conversion或retention或other",
  "scenario": "vibe_coding或agent或pricing或general_chat或other",
  "feedback_type": "bug或cognition或comparison或other",
  "confidence": "high或low"
}}

维度定义：
sentiment:
- positive: 整体积极，明确表示好用/推荐/超预期
- negative: 明确表达差评/失望/不如预期/要退订
- neutral: 其他所有情况，包括：客观测评/有好有坏、功能介绍性文章、质疑但没有明确结论、竞品对比但没有明确倾向、技术讨论

注意：大多数内容应该是neutral，不要过度判断为positive

funnel_stage:
- activation: 不知道怎么用/找不到功能/新手问题
- success: 用了但失败/卡死/报错/效果差/降智/跑不完
- conversion: 价格/要不要付费/额度/套餐选择
- retention: 要不要继续用/换了其他产品/退订
- other: 综合测评/纯功能介绍/无明确问题

scenario:
- vibe_coding: 写代码/建网站/前端/全栈
- agent: Agent/集群/Claw/自动化/swarm
- pricing: 价格/套餐/会员/额度/token
- general_chat: 日常对话/写作/翻译
- other: 无法归类

feedback_type:
- bug: 明确提到报错/崩溃/卡死/循环/无法使用
- cognition: 明确表示不知道怎么用/找不到功能
- comparison: 明确和Claude/GPT/GLM等其他产品做对比
- other: 其他所有情况（包括纯功能介绍/综合评价）

注意：comparison只在明确提到竞品名称时才标，不要泛化"""

INTERPRETATION_PROMPT = """You are an internal data analyst at an AI company, looking at external user feedback about your product. You are NOT writing for executives. You are writing rough notes for yourself to follow up on later.

Given a group of user comments sharing the same (funnel_stage, scenario, feedback_type), produce a JSON object with these fields:

- "how_i_interpret_this": 2-4 sentences. First-person hedged language: "I think this might relate to...", "Possibly users are running into...", "This could be about...". NEVER "users are", "the product needs to", "you should". You are guessing from outside; you do not have internal data.

- "possible_internal_checks": 2-5 specific internal metric names you would want to look at if you had access. Be precise: "second-turn modification rate" not "engagement metrics"; "long-context reset frequency" not "user behavior". Wrap with: "if I had access to internal data, I would check..."

- "boundary_note": one sentence stating what this signal CANNOT tell you. Examples: "External signals cannot distinguish whether friction comes from model capability, prompt patterns, or specific use cases." "Reddit/HN sample skews technical early adopters; may not reflect general user base."

Output strict JSON only. No prose outside the JSON.

Forbidden words: "should", "must", "obviously", "clearly", "the issue is", "users want". If tempted to use these, rephrase."""

WEEKLY_BRIEF_PROMPT = """你是一个产品分析师助手。以下是本周从外部平台采集到的用户反馈信号。

{signals}

请生成一份简洁的中文周报，格式如下：

第一段：整体概括，2-3句，说明本周外部反馈可能呈现出的情况。

然后用分点列出每个值得关注的信号：
- 【信号名】谨慎解读 + 如果要验证，我会看哪些内部指标。

要求：
- 使用谨慎语气，例如“可能”“也许”“可以先看”“我会检查”。
- 不要下确定结论。
- 不要写“应该”“必须”“显然”“用户就是因为”。
- 不超过300字。
- 只关注有本周 monitoring 数据的信号。
- 如果样本很少，要明确提醒样本量有限。
- 结尾加一句：以上内容只用于提示关注方向，所有判断都需要内部数据验证。
"""
