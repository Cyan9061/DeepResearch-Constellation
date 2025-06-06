# 配置文件
API_KEYS = [#yours API_KEYS 建议用免费的（recommend free API_KEYS）

]

# 专用于研究总结的高级API密钥 (更强大的DeepSeek模型)（recommend advanced API_KEYS for research summary）
API_KEYS_2 = [

]

API_ENDPOINT = "https://api.siliconflow.cn/v1/chat/completions" #默认硅基流动，你可以替换成你喜欢的API_ENDPOINT平台
MODEL_NAME = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"# 用于单篇论文分析的模型，建议用免费或者便宜的模型，这里使用的是DeepSeek-R1-0528-Qwen3-8B蒸馏模型（recommend free or cheap model for single paper analysis）

# 用于总结和深度分析的高级模型 (可以是更强大的模型)（recommend advanced model for summary and deep analysis）
SUMMARY_MODEL_NAME = "deepseek-ai/DeepSeek-R1"  # 可以使用更强的模型
SUMMARY_API_ENDPOINT = "https://api.siliconflow.cn/v1/chat/completions"  # 可以使用不同的endpoint，这里使用的是默认的硅基流动（recommend different endpoint）

# 下载目录
DOWNLOAD_DIR = "./downloads"
OUTPUT_DIR = "./output"

# 研究配置
NUM_SEARCH_QUERIES = 3  # 生成的搜索查询数量
PAPERS_PER_QUERY = 20    # 每个查询最多返回的论文数
USE_RETRY_ON_FAILURE = True  # 是否在失败时重试

# 搜索深度配置
SEARCH_DEPTH = 5  # 搜索深度，1为单轮搜索，>1为多轮搜索
MAX_PAPERS_PER_DEPTH = 48  # 每一轮搜索的最大处理论文数
MIN_PAPERS_FOR_NEXT_DEPTH = 3  # 进入下一轮搜索所需的最少论文数
DEPTH_SEARCH_QUERIES = 3  # 每轮深度搜索生成的查询数量
PAPERS_PER_DEPTH_QUERY = 15  # 每个深度搜索查询的论文数
MIN_PAPERS_FOR_CONTINUE = 3  # 低于3篇则继续深度搜索


# API调用配置
MODEL_CONTEXT_SIZE = 96 * 1000  # 128K tokens 上下文
MAX_TOKENS_PER_REQUEST = 8192  # 每次API调用允许的最大token数量
MAX_INPUT_TOKENS = int((MODEL_CONTEXT_SIZE - MAX_TOKENS_PER_REQUEST) * 0.95)  # 输入token上限(128K-5%缓冲)
MAX_CONTENT_LENGTH = int(MAX_INPUT_TOKENS * 3.5)     # 最大内容长度（字符）
API_TIMEOUT = 120              # API调用超时时间（秒）
API_RETRY_COUNT = 3            # API调用重试次数

# 总结API配置 (使用更强大的模型)
SUMMARY_MAX_TOKENS_PER_REQUEST = 16384  # 总结API每次调用的最大token数
SUMMARY_API_TIMEOUT = 180  # 总结API超时时间（更长）
SUMMARY_API_RETRY_COUNT = 3  # 总结API重试次数
SUMMARY_TEMPERATURE = 0.1  # 总结时使用更低的温度以获得更一致的结果

# PDF处理配置
EXTRACT_FULL_PDF = True  # 是否提取完整PDF内容
MAX_PAGES_TO_EXTRACT = None  # None表示提取所有页面，数字表示最大页数
MAX_TEXT_LENGTH = None  # None表示不限制文本长度，数字表示最大字符数
PDF_CHUNK_SIZE = MAX_INPUT_TOKENS  # 如果文本太长，分块处理时每块的大小

# 并发分析配置
MAX_ANALYSIS_PAPERS = 80   # 最大分析论文总数
ENABLE_CONCURRENT_ANALYSIS = True  # 是否启用并发分析
MAX_CONCURRENT_ANALYSIS = len(API_KEYS)        # 最大并发分析数量（确保有足够的API_KEYS） 
CONCURRENT_BATCH_SIZE = len(API_KEYS)          # 每批并发处理的论文数量                  
ANALYSIS_RATE_LIMIT_DELAY = 0.5    # 并发分析之间的延迟（秒）

# 单篇论文分析配置
CONTEXT_ANAYLISE_LENTH = int(MAX_INPUT_TOKENS * 3.5)  # 单篇论文分析的最大输入内容长度

# 多篇分析总结配置
SINGLE_ANAYLISE_LENTH = int(MAX_INPUT_TOKENS * 3.5)  # 单篇论文分析的最大长度
MAX_ANAYLISE_PAPERS = 48  # 最大分析论文数
MAX_ANAYLISE_OUTPUT_LENGTH = 32000*2  # 最大分析输出长度

# 深度搜索评估配置
ADEQUACY_EVALUATION_THRESHOLD = 0.90  # 资料充分性评估阈值 (0-1, 1表示完全充分)
MIN_DEPTH_SEARCH_SCORE = 0.3  # 进行深度搜索的最低分数阈值
MAX_NEW_KEYWORDS_PER_DEPTH = 5  # 每轮深度搜索生成的最大新关键词数量