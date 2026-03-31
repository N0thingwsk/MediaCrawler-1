import os


##root:MW_1234!*@tcp(21.6.80.225:3306)/mw_publish?charset=utf8mb4&parseTime=True&loc=Local
# ==================== MySQL 配置 ====================
MYSQL_DB_PWD = os.getenv("MYSQL_DB_PWD", "qwe123456")
MYSQL_DB_USER = os.getenv("MYSQL_DB_USER", "root")
MYSQL_DB_HOST = os.getenv("MYSQL_DB_HOST", "localhost")
MYSQL_DB_PORT = os.getenv("MYSQL_DB_PORT", 3306)
MYSQL_DB_NAME = os.getenv("MYSQL_DB_NAME", "media_crawler")

mysql_db_config = {
    "user": MYSQL_DB_USER,
    "password": MYSQL_DB_PWD,
    "host": MYSQL_DB_HOST,
    "port": MYSQL_DB_PORT,
    "db_name": MYSQL_DB_NAME,
}


# ==================== Redis 配置 ====================
REDIS_DB_HOST = os.getenv("REDIS_DB_HOST", "127.0.0.1")  # Redis 主机地址
REDIS_DB_PWD = os.getenv("REDIS_DB_PWD", "123456")  # Redis 密码
REDIS_DB_PORT = os.getenv("REDIS_DB_PORT", 6379)  # Redis 端口
REDIS_DB_NUM = os.getenv("REDIS_DB_NUM", 0)  # Redis 数据库编号

# 缓存类型
CACHE_TYPE_REDIS = "redis"
CACHE_TYPE_MEMORY = "memory"

# ==================== SQLite 配置 ====================
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "sqlite_tables.db")

sqlite_db_config = {
    "db_path": SQLITE_DB_PATH
}

# ==================== MongoDB 配置 ====================
MONGODB_HOST = os.getenv("MONGODB_HOST", "localhost")
MONGODB_PORT = os.getenv("MONGODB_PORT", 27017)
MONGODB_USER = os.getenv("MONGODB_USER", "")
MONGODB_PWD = os.getenv("MONGODB_PWD", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "media_crawler")

mongodb_config = {
    "host": MONGODB_HOST,
    "port": int(MONGODB_PORT),
    "user": MONGODB_USER,
    "password": MONGODB_PWD,
    "db_name": MONGODB_DB_NAME,
}

# ==================== PostgreSQL 配置 ====================
POSTGRES_DB_PWD = os.getenv("POSTGRES_DB_PWD", "123456")
POSTGRES_DB_USER = os.getenv("POSTGRES_DB_USER", "postgres")
POSTGRES_DB_HOST = os.getenv("POSTGRES_DB_HOST", "localhost")
POSTGRES_DB_PORT = os.getenv("POSTGRES_DB_PORT", 5432)
POSTGRES_DB_NAME = os.getenv("POSTGRES_DB_NAME", "media_crawler")

postgres_db_config = {
    "user": POSTGRES_DB_USER,
    "password": POSTGRES_DB_PWD,
    "host": POSTGRES_DB_HOST,
    "port": POSTGRES_DB_PORT,
    "db_name": POSTGRES_DB_NAME,
}
