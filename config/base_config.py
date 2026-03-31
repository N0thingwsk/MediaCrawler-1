# -*- coding: utf-8 -*-
# 涓流爬取服务配置文件

# ==================== 基础配置 ====================
# 平台列表：支持同时配置多个平台，依次爬取
# 可选值：xhs | dy | ks | bili | wb | tieba | zhihu
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
# 每个关键词每日爬取的最大条数
TRICKLE_MAX_NOTES_PER_KEYWORD = 100

# 每页爬取后的休眠时间（秒），控制爬取速率，避免触发风控
# 实际休眠时间 = 基础值 * (0.5~1.5) 的随机系数，模拟人类行为
TRICKLE_SLEEP_BETWEEN_PAGES = 20

# 关键词之间的休眠时间（秒），实际会加上 0~30 秒的随机偏移
TRICKLE_SLEEP_BETWEEN_KEYWORDS = 90

# 每日执行的随机时间范围（24小时制）
# 每天会在此范围内随机选一个时间执行，模拟人类行为，降低风控风险
TRICKLE_DAILY_TIME_RANGE_START = "01:00"
TRICKLE_DAILY_TIME_RANGE_END = "05:00"

# 遇到错误后的重试等待时间（秒）
TRICKLE_ERROR_RETRY_INTERVAL = 120

# ==================== 各平台子配置导入 ====================
from .dy_config import *
from .xhs_config import *
from .bilibili_config import *
from .ks_config import *
from .weibo_config import *
from .tieba_config import *
from .zhihu_config import *