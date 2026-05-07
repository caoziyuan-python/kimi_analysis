from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
BASELINE_DIR = DATA_DIR / "baseline"
MONITORING_DIR = DATA_DIR / "monitoring"
INTERPRETATIONS_DIR = DATA_DIR / "interpretations"
MANUAL_DIR = DATA_DIR / "manual"

BASELINE_PATH = BASELINE_DIR / "labeled_baseline.csv"
MONITORING_PATH = MONITORING_DIR / "labeled_monitoring.csv"
INTERPRETATIONS_PATH = INTERPRETATIONS_DIR / "interpretations.json"
WEEKLY_BRIEF_PATH = INTERPRETATIONS_DIR / "weekly_brief.json"
MANUAL_SAMPLE_PATH = MANUAL_DIR / "manual_sample_100.csv"

MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1/chat/completions"
MOONSHOT_MODEL = "moonshot-v1-8k"

DEFAULT_COLLECT_LIMIT = 100
DEFAULT_LOOKBACK_DAYS = 7
MAX_RETRIES = 3
REQUEST_TIMEOUT_SECONDS = 30
MAX_CONTENT_LENGTH = 500
PROGRESS_INTERVAL = 50
BASELINE_FUNNEL_F1 = 0.78
MANUAL_SAMPLE_SIZE = 100
GITHUB_URL = "https://github.com/<placeholder>/kimi_analysis"

REDDIT_RSS_URLS = [
    "https://www.reddit.com/r/LocalLLaMA/.rss?limit=100",
    "https://www.reddit.com/r/MachineLearning/.rss?limit=100",
    "https://www.reddit.com/r/artificial/.rss?limit=100",
    "https://www.reddit.com/r/ChatGPT/.rss?limit=100",
    "https://www.reddit.com/r/kimi/.rss?limit=100",
    "https://www.reddit.com/r/vibecoding/.rss?limit=100",
    "https://www.reddit.com/r/ClaudeCode/.rss?limit=100",
    "https://www.reddit.com/r/opencodeCLI/.rss?limit=100",
    "https://www.reddit.com/r/LocalLLM/.rss?limit=100",
    "https://www.reddit.com/r/ollama/.rss?limit=100",
    "https://www.reddit.com/r/singularity/.rss?limit=100",
    "https://www.reddit.com/r/LLMDevs/.rss?limit=100",
    "https://www.reddit.com/r/AI_Agents/.rss?limit=100",
    "https://www.reddit.com/r/ArtificialInteligence/.rss?limit=100",
    "https://www.reddit.com/r/ChatGPTCoding/.rss?limit=100",
    "https://www.reddit.com/r/learnmachinelearning/.rss?limit=100",
    "https://www.reddit.com/r/PromptEngineering/.rss?limit=100",
    "https://www.reddit.com/r/SillyTavernAI/.rss?limit=100",
    "https://www.reddit.com/r/google_antigravity/.rss?limit=100",
]

MONITORING_PLATFORMS = {"reddit", "hackernews", "github"}
BASELINE_ONLY_PLATFORMS = {"zhihu", "xiaohongshu", "weibo"}
