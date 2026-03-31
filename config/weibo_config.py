# 微博平台配置

# 搜索类型，具体枚举值参见 media_platform/weibo/field.py
WEIBO_SEARCH_TYPE = "default"

# 指定微博帖子 ID 列表
WEIBO_SPECIFIED_ID_LIST = [
    "4982041758140155",
    # ........................
]

# 指定微博创作者用户 ID 列表
WEIBO_CREATOR_ID_LIST = [
    "5756404150",
    # ........................
]

# 是否启用微博全文爬取功能，默认开启
# 开启后会增加被风控的概率，相当于每次关键词搜索请求都会遍历所有帖子并再次请求帖子详情
ENABLE_WEIBO_FULL_TEXT = True
