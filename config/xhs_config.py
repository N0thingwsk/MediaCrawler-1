# 小红书平台配置

# 搜索排序方式，具体枚举值见 media_platform/xhs/field.py
SORT_TYPE = "popularity_descending"

# 指定笔记 URL 列表，URL 必须携带 xsec_token 参数
XHS_SPECIFIED_NOTE_URL_LIST = [
    "https://www.xiaohongshu.com/explore/64b95d01000000000c034587?xsec_token=AB0EFqJvINCkj6xOCKCQgfNNh8GdnBC_6XecG4QOddo3Q=&xsec_source=pc_cfeed"
    # ........................
]

# 指定创作者 URL 列表，URL 需要携带 xsec_token 和 xsec_source 参数

XHS_CREATOR_ID_LIST = [
    "https://www.xiaohongshu.com/user/profile/5f58bd990000000001003753?xsec_token=ABYVg1evluJZZzpMX-VWzchxQ1qSNVW3r-jOEnKqMcgZw=&xsec_source=pc_search"
    # ........................
]
