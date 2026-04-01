# -*- coding: utf-8 -*-
# 涓流爬取服务配置文件

# ==================== 基础配置 ====================
# 平台列表：支持同时配置多个平台，依次爬取
# 可选值：xhs | dy | ks | bili
PLATFORM = ["dy"]

# 爬取关键词列表
KEYWORDS = [
    "ai短剧",
    "ai漫剧"
]

# 登录方式：qrcode（二维码） 或 phone（手机号） 或 cookie
LOGIN_TYPE = "cookie"

# Cookie 值（cookie 登录方式使用）
COOKIES = ""

# 爬取类型，服务模式下固定为 trickle（抖音走 trickle_search，其他平台走 search）
CRAWLER_TYPE = "trickle"

# ==================== 浏览器配置 ====================
# 是否启用无头浏览器模式（不打开浏览器窗口）
HEADLESS = False

# 是否保存登录状态
SAVE_LOGIN_STATE = True

# 是否启用 CDP 模式 - 使用用户现有的 Chrome/Edge 浏览器进行爬取
ENABLE_CDP_MODE = True

# CDP 调试端口
CDP_DEBUG_PORT = 9222

# 自定义浏览器路径（可选，为空自动检测）
CUSTOM_BROWSER_PATH = ""

# CDP 模式下是否启用无头模式
CDP_HEADLESS = False

# 浏览器启动超时时间（秒）
BROWSER_LAUNCH_TIMEOUT = 60

# 程序结束时是否自动关闭浏览器
AUTO_CLOSE_BROWSER = True

# 用户浏览器缓存目录
USER_DATA_DIR = "%s_user_data_dir"

# ==================== IP 代理配置 ====================
# 是否启用 IP 代理
ENABLE_IP_PROXY = False

# 代理 IP 池数量
IP_PROXY_POOL_COUNT = 2

# 代理 IP 提供商名称
IP_PROXY_PROVIDER_NAME = "kuaidaili"

# ==================== 多账号配置 ====================
# 是否启用多账号轮换模式
ENABLE_MULTI_ACCOUNT = False

# 多账号 Cookie 列表（启用多账号模式时使用）
# 每个元素为一个完整的 Cookie 字符串
COOKIES_LIST: list = []

# ==================== 数据库初始化配置 ====================
# 启动时是否自动初始化数据库表结构
# 设为 True 则每次启动自动执行建表，适合首次部署
# 设为 False 则跳过建表，适合日常运行
INIT_DB_ON_STARTUP = True

# ==================== 数据存储配置 ====================
# 数据保存类型：仅支持 db（MySQL）
SAVE_DATA_OPTION = "db"

# ==================== 爬取行为配置 ====================
# 控制并发爬取的数量
MAX_CONCURRENCY_NUM = 1

# 是否启用媒体爬取（图片/视频资源），默认不启用
ENABLE_GET_MEIDAS = False

# 是否启用评论爬取
ENABLE_GET_COMMENTS = False

# 每个视频/帖子爬取的一级评论数量
CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = 10

# 爬取间隔（秒）
CRAWLER_MAX_SLEEP_SEC = 2

# 起始页码（非涓流模式下使用，涓流模式从第 0 页开始）
START_PAGE = 1

# 最大爬取数量（非涓流模式下使用）
CRAWLER_MAX_NOTES_COUNT = 100

# ==================== 涓流服务配置 (Trickle Service) ====================
# 每个关键词每轮爬取的最大条数（一轮爬完后会休眠再开始下一轮）
TRICKLE_MAX_NOTES_PER_KEYWORD = 100

# 每页爬取后的休眠时间（秒），控制爬取速率，避免触发风控
# 实际休眠时间 = 基础值 * (0.5~1.5) 的随机系数，模拟人类行为
TRICKLE_SLEEP_BETWEEN_PAGES = 20

# 关键词之间的休眠时间（秒），实际会加上 0~30 秒的随机偏移
TRICKLE_SLEEP_BETWEEN_KEYWORDS = 90

# 错误重试指数退避配置
# 基础等待时间（秒），实际等待 = base * 2^(连续错误次数-1)，并加随机抖动
TRICKLE_ERROR_RETRY_BASE = 30
# 指数退避最大等待时间上限（秒），防止等待过久
TRICKLE_ERROR_RETRY_MAX = 600
# 连续错误最大容忍次数，超过后跳过当前关键词
TRICKLE_MAX_CONSECUTIVE_ERRORS = 5

# ==================== 持续爬取模式配置 ====================
# 是否启用持续爬取模式（True=7x24持续运行，False=每日定时执行一次）
ENABLE_CONTINUOUS_MODE = True

# 每轮爬取完成后的休眠时间范围（分钟），在此范围内随机选择
# 模拟用户"刷一会儿休息一下"的行为
CONTINUOUS_REST_MIN_MINUTES = 30
CONTINUOUS_REST_MAX_MINUTES = 60

# 每日定时模式的时间范围（仅 ENABLE_CONTINUOUS_MODE=False 时生效）
TRICKLE_DAILY_TIME_RANGE_START = "01:00"
TRICKLE_DAILY_TIME_RANGE_END = "05:00"

# ==================== 模拟用户行为配置 ====================
# 每条数据处理后的停顿时间范围（秒），模拟用户阅读/浏览内容
# 真实用户看一条内容通常需要 3~8 秒
USER_READ_DELAY_MIN = 3.0
USER_READ_DELAY_MAX = 8.0

# 每页数据处理后的翻页间隔范围（秒），模拟用户滑动翻页
# 真实用户翻页通常需要 5~15 秒
USER_PAGE_SCROLL_DELAY_MIN = 5.0
USER_PAGE_SCROLL_DELAY_MAX = 15.0

# 关键词切换间隔范围（秒），模拟用户换一个搜索词
USER_KEYWORD_SWITCH_DELAY_MIN = 30.0
USER_KEYWORD_SWITCH_DELAY_MAX = 90.0

# 模拟用户随机行为概率（0~1）
# 在翻页间隙中，有一定概率执行"随机浏览"动作（滚动页面、停留等）
USER_RANDOM_ACTION_PROBABILITY = 0.3

# 模拟用户"走神"概率：偶尔长时间停顿（30~120秒），模拟用户去做别的事
USER_IDLE_PROBABILITY = 0.1
USER_IDLE_DELAY_MIN = 30.0
USER_IDLE_DELAY_MAX = 120.0

# ==================== 作息时间模拟配置 ====================
# 是否启用作息时间模拟（True=只在活跃时段爬取，休眠时段暂停爬取但保持Cookie保活）
ENABLE_SCHEDULE_MODE = True

# 活跃时段列表（24小时制），在这些时段内正常爬取
# 格式：[(开始时间, 结束时间), ...]
# 默认模拟真实用户作息：早上8点~12点、下午14点~18点、晚上20点~23点
ACTIVE_HOURS = [
    ("08:00", "12:00"),
    ("14:00", "18:00"),
    ("20:00", "23:00"),
]

# 休眠时段检查间隔（秒）：在休眠时段中，每隔多久检查一次是否进入活跃时段
SLEEP_CHECK_INTERVAL = 300

# ==================== Cookie 续约增强配置 ====================
# Cookie 自动刷新间隔（秒），定期从浏览器同步最新 Cookie
COOKIE_REFRESH_INTERVAL = 90

# 页面活跃保持间隔（秒），定期在浏览器中执行轻量操作保持会话活跃
# 防止长时间无操作导致 Cookie/Session 过期
PAGE_KEEP_ALIVE_INTERVAL = 60

# 页面完整刷新间隔（秒），定期刷新页面以续约 Cookie
# 模拟用户偶尔刷新页面的行为
PAGE_FULL_REFRESH_INTERVAL = 600

# ==================== 休眠期降频保活配置 ====================
# 休眠时段的保活间隔倍率（相对于活跃时段的倍数）
# 例如：活跃时段微操作间隔60s，休眠时段 = 60 * 5 = 300s
SLEEP_KEEP_ALIVE_MULTIPLIER = 5

# 休眠时段的页面刷新间隔倍率
# 例如：活跃时段刷新间隔600s，休眠时段 = 600 * 3 = 1800s（30分钟）
SLEEP_PAGE_REFRESH_MULTIPLIER = 3

# ==================== Stealth.js 自动更新配置 ====================
# 是否启用 stealth.min.js 自动更新（启动时检查版本并自动更新）
ENABLE_STEALTH_AUTO_UPDATE = True

# stealth.min.js 最大允许年龄（天），超过此天数自动触发更新
# 建议 30~90 天，太频繁可能下载失败，太久可能被新检测手段绕过
STEALTH_MAX_AGE_DAYS = 30

# ==================== 各平台子配置导入 ====================
from .dy_config import *
from .xhs_config import *
from .bilibili_config import *
from .ks_config import *