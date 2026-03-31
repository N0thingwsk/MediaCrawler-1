# B站平台配置

# 每日爬取的视频/帖子数量上限
MAX_NOTES_PER_DAY = 1

# 指定B站视频 URL 列表（支持完整 URL 或 BV 号）
# 示例：
# - 完整 URL："https://www.bilibili.com/video/BV1dwuKzmE26/?spm_id_from=333.1387.homepage.video_card.click"
# - BV 号："BV1d54y1g7db"
BILI_SPECIFIED_ID_LIST = [
    "https://www.bilibili.com/video/BV1dwuKzmE26/?spm_id_from=333.1387.homepage.video_card.click",
    "BV1Sz4y1U77N",
    "BV14Q4y1n7jz",
    # ........................
]

# 指定B站创作者 URL 列表（支持完整 URL 或 UID）
# 示例：
# - 完整 URL："https://space.bilibili.com/434377496?spm_id_from=333.1007.0.0"
# - UID："20813884"
BILI_CREATOR_ID_LIST = [
    "https://space.bilibili.com/434377496?spm_id_from=333.1007.0.0",
    "20813884",
    # ........................
]

# 指定时间范围
START_DAY = "2024-01-01"
END_DAY = "2024-01-01"

# 搜索模式
BILI_SEARCH_MODE = "normal"

# 视频清晰度（qn）配置，常用值：
# 16=360p, 32=480p, 64=720p, 80=1080p, 112=1080p高码率, 116=1080p60帧, 120=4K
# 注意：高清晰度需要账号/视频支持
BILI_QN = 80

# 是否爬取用户信息
CREATOR_MODE = True

# 开始爬取用户信息的起始页码
START_CONTACTS_PAGE = 1

# 单个视频/帖子最大爬取评论数
CRAWLER_MAX_CONTACTS_COUNT_SINGLENOTES = 100

# 单个UP主最大爬取动态数
CRAWLER_MAX_DYNAMICS_COUNT_SINGLENOTES = 50
