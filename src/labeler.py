import csv
import json
import os
import random
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = PROJECT_ROOT / "data" / "cleaned"
LABELED_DIR = PROJECT_ROOT / "data" / "labeled"

BASE_URL = "https://api.moonshot.cn/v1/chat/completions"
MODEL = "moonshot-v1-8k"
MAX_RETRIES = 3
PROGRESS_INTERVAL = 50
MAX_CONTENT_LENGTH = 500

LABEL_FIELDS = [
    "sentiment",
    "funnel_stage",
    "scenario",
    "feedback_type",
    "confidence",
]

PLATFORM_FILES = [
    {
        "name": "zhihu",
        "input_path": CLEANED_DIR / "zhihu_cleaned.csv",
        "output_path": LABELED_DIR / "zhihu_labeled.csv",
    },
    {
        "name": "reddit",
        "input_path": CLEANED_DIR / "reddit_cleaned.csv",
        "output_path": LABELED_DIR / "reddit_labeled.csv",
    },
    {
        "name": "weibo",
        "input_path": CLEANED_DIR / "weibo_cleaned.csv",
        "output_path": LABELED_DIR / "weibo_labeled.csv",
    },
    {
        "name": "xhs",
        "input_path": CLEANED_DIR / "xhs_cleaned.csv",
        "output_path": LABELED_DIR / "xhs_labeled.csv",
    },
]

SYSTEM_PROMPT = """你是一个产品分析助手，对AI产品用户反馈进行分类标注。
严格按JSON格式输出，不输出任何其他内容。"""

USER_PROMPT_TEMPLATE = """请对以下用户反馈进行分类标注：

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


def ensure_output_dir() -> None:
    LABELED_DIR.mkdir(parents=True, exist_ok=True)


def load_api_key() -> str:
    load_dotenv()
    key = os.getenv("MOONSHOT_API_KEY", "").strip()
    if not key:
        raise RuntimeError("缺少 MOONSHOT_API_KEY 环境变量")
    return key


def read_csv_rows(path: Path) -> tuple[list[dict], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    return rows, fieldnames


def write_csv_rows(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
        writer.writerows(rows)


def extract_json_text(text: str) -> str:
    content = (text or "").strip()
    if content.startswith("```"):
        content = content.strip("`").strip()
        if content.lower().startswith("json"):
            content = content[4:].strip()

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end >= start:
        return content[start : end + 1]
    return content


def error_labels() -> dict[str, str]:
    return {field: "error" for field in LABEL_FIELDS}


def normalize_labels(parsed: dict) -> dict[str, str]:
    labels: dict[str, str] = {}
    for field in LABEL_FIELDS:
        value = parsed.get(field, "error")
        labels[field] = str(value).strip() if value is not None else "error"
    return labels


def truncate_content(content: str, max_length: int = MAX_CONTENT_LENGTH) -> str:
    normalized = str(content or "").strip()
    return normalized[:max_length]


def call_label_api(session: requests.Session, api_key: str, content: str) -> dict[str, str]:
    truncated_content = truncate_content(content)
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(content=truncated_content),
            },
        ],
        "temperature": 0.1,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.post(BASE_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            message = data["choices"][0]["message"]["content"]
            parsed = json.loads(extract_json_text(message))
            return normalize_labels(parsed)
        except (requests.RequestException, KeyError, IndexError, ValueError, json.JSONDecodeError):
            if attempt == MAX_RETRIES:
                return error_labels()
            time.sleep(1)

    return error_labels()


def label_rows(rows: list[dict], api_key: str, platform_name: str) -> list[dict]:
    session = requests.Session()
    labeled_rows: list[dict] = []
    processed = 0

    for row in rows:
        content = str(row.get("content") or "").strip()
        labels = call_label_api(session, api_key, content)
        labeled_row = dict(row)
        labeled_row.update(labels)
        labeled_rows.append(labeled_row)

        processed += 1
        if processed % PROGRESS_INTERVAL == 0:
            print(f"[{platform_name}] 已处理 {processed} 条")

        time.sleep(random.uniform(0.5, 1.0))

    return labeled_rows


def label_platform(api_key: str, config: dict, test_mode: bool = False) -> None:
    input_path: Path = config["input_path"]
    output_path: Path = config["output_path"]
    platform_name: str = config["name"]

    if not input_path.exists():
        print(f"[{platform_name}] 清洗文件不存在: {input_path}")
        return

    rows, fieldnames = read_csv_rows(input_path)
    if not rows:
        print(f"[{platform_name}] 无可标注数据")
        write_csv_rows(output_path, [], fieldnames + LABEL_FIELDS)
        return

    if test_mode:
        rows = rows[:10]

    labeled_rows = label_rows(rows, api_key, platform_name)
    output_fieldnames = list(fieldnames)
    for field in LABEL_FIELDS:
        if field not in output_fieldnames:
            output_fieldnames.append(field)

    write_csv_rows(output_path, labeled_rows, output_fieldnames)
    print(f"[{platform_name}] 标注完成: {output_path}")


def label_all(test_mode: bool = False) -> None:
    ensure_output_dir()
    api_key = load_api_key()

    for config in PLATFORM_FILES:
        label_platform(api_key, config, test_mode=test_mode)


if __name__ == '__main__':
    label_all(test_mode=False)  # 关掉test_mode
