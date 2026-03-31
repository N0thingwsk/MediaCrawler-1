# -*- coding: utf-8 -*-
"""
多平台涓流爬取服务

以低速、持续的方式每日自动爬取数据。
每天在配置的时间范围内随机选一个时间执行，模拟人类行为，降低风控风险。
每个关键词爬取指定数量的数据，并打上关键词 tag。

支持平台：xhs | dy | ks | bili | wb | tieba | zhihu
平台通过 config/base_config.py 中的 PLATFORM 配置项指定。

使用方式：
    python main.py

可通过 config/base_config.py 中的配置项调整行为。
"""

import sys
import io

# 强制 UTF-8 编码输出
if sys.stdout and hasattr(sys.stdout, "buffer"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "buffer"):
    if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Optional

import config
from base.base_crawler import AbstractCrawler
from media_platform.bilibili import BilibiliCrawler
from media_platform.douyin import DouYinCrawler
from media_platform.kuaishou import KuaishouCrawler
from media_platform.tieba import TieBaCrawler
from media_platform.weibo import WeiboCrawler
from media_platform.xhs import XiaoHongShuCrawler
from media_platform.zhihu import ZhihuCrawler
from tools import utils


class CrawlerFactory:
    """多平台爬虫工厂"""
    CRAWLERS = {
        "xhs": XiaoHongShuCrawler,
        "dy": DouYinCrawler,
        "ks": KuaishouCrawler,
        "bili": BilibiliCrawler,
        "wb": WeiboCrawler,
        "tieba": TieBaCrawler,
        "zhihu": ZhihuCrawler,
    }

    @staticmethod
    def create_crawler(platform: str) -> AbstractCrawler:
        crawler_cls = CrawlerFactory.CRAWLERS.get(platform)
        if not crawler_cls:
            supported = ", ".join(CrawlerFactory.CRAWLERS.keys())
            raise ValueError(f"不支持的平台: '{platform}'，支持的平台: {supported}")
        return crawler_cls()


crawler: Optional[AbstractCrawler] = None


# ---------------------------------------------------------------------------
# 随机定时调度工具函数
# ---------------------------------------------------------------------------

def _generate_random_run_time(range_start: str, range_end: str) -> datetime:
    """
    在指定时间范围内随机生成明天的执行时间。
    支持跨午夜范围（如 22:00 ~ 06:00）。

    Args:
        range_start: 起始时间 "HH:MM" 格式
        range_end: 结束时间 "HH:MM" 格式
    Returns:
        随机生成的明天执行时间 (datetime)
    """
    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    start_h, start_m = map(int, range_start.split(":"))
    end_h, end_m = map(int, range_end.split(":"))

    start_dt = tomorrow.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end_dt = tomorrow.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    delta_seconds = int((end_dt - start_dt).total_seconds())
    random_offset = random.randint(0, max(delta_seconds, 0))
    return start_dt + timedelta(seconds=random_offset)


def _seconds_until(target: datetime) -> float:
    """计算从现在到目标时间的秒数"""
    return max((target - datetime.now()).total_seconds(), 0)


# ---------------------------------------------------------------------------
# 单次爬取 & 服务主循环
# ---------------------------------------------------------------------------

async def _cleanup_crawler() -> None:
    """清理当前 crawler 的浏览器资源"""
    global crawler
    if not crawler:
        return
    try:
        if getattr(crawler, "cdp_manager", None):
            await crawler.cdp_manager.cleanup(force=True)
        elif getattr(crawler, "browser_context", None):
            await crawler.browser_context.close()
    except Exception as e:
        error_msg = str(e).lower()
        if "closed" not in error_msg and "disconnected" not in error_msg:
            utils.logger.error(f"[TrickleService] 清理浏览器资源出错: {e}")
    finally:
        crawler = None


async def run_trickle_once() -> None:
    """执行一次涓流爬取任务：遍历所有配置的平台，逐个爬取"""
    global crawler

    platforms: List[str] = config.PLATFORM
    today_str = datetime.now().strftime("%Y-%m-%d")
    utils.logger.info(
        f"[TrickleService] ========== 开始每日涓流爬取 | 平台: {platforms} | {today_str} =========="
    )

    for idx, platform in enumerate(platforms):
        utils.logger.info(
            f"[TrickleService] [{idx+1}/{len(platforms)}] 开始爬取平台: {platform}"
        )
        try:
            crawler = CrawlerFactory.create_crawler(platform)
            await crawler.start()
            utils.logger.info(
                f"[TrickleService] [{idx+1}/{len(platforms)}] 平台 {platform} 爬取完成"
            )
        except Exception as e:
            utils.logger.error(
                f"[TrickleService] [{idx+1}/{len(platforms)}] 平台 {platform} 爬取出错: {e}"
            )
        finally:
            await _cleanup_crawler()

        # 平台之间休眠一段时间，避免风控
        if idx < len(platforms) - 1:
            sleep_sec = random.randint(30, 120)
            utils.logger.info(
                f"[TrickleService] 平台间休眠 {sleep_sec}s 后继续下一个平台..."
            )
            await asyncio.sleep(sleep_sec)

    utils.logger.info(
        f"[TrickleService] ========== 每日涓流爬取全部完成 | 平台: {platforms} | {today_str} =========="
    )


async def trickle_service_loop() -> None:
    """
    涓流服务主循环：
    1. 首次启动立即执行一次
    2. 之后每天在随机时间执行，时间范围由配置决定
    """
    time_start = config.TRICKLE_DAILY_TIME_RANGE_START
    time_end = config.TRICKLE_DAILY_TIME_RANGE_END
    utils.logger.info(
        f"[TrickleService] 涓流服务启动 | "
        f"平台: {config.PLATFORM} (共 {len(config.PLATFORM)} 个) | "
        f"每日随机执行时间范围: {time_start} ~ {time_end} | "
        f"关键词: {config.KEYWORDS} | "
        f"每关键词目标: {config.TRICKLE_MAX_NOTES_PER_KEYWORD} 条"
    )

    # 首次启动直接执行一次
    utils.logger.info("[TrickleService] 首次启动，立即执行一轮涓流爬取...")
    await run_trickle_once()

    # 之后进入随机定时循环
    while True:
        next_run_dt = _generate_random_run_time(time_start, time_end)
        wait_seconds = _seconds_until(next_run_dt)
        wait_hours = wait_seconds / 3600
        utils.logger.info(
            f"[TrickleService] 下次执行时间: {next_run_dt.strftime('%Y-%m-%d %H:%M:%S')} "
            f"(随机生成，范围 {time_start}~{time_end}) | "
            f"等待 {wait_hours:.1f} 小时"
        )
        await asyncio.sleep(wait_seconds)
        await run_trickle_once()


async def main() -> None:
    """服务主入口"""
    # 如果配置了启动时初始化数据库，则先建表
    if getattr(config, "INIT_DB_ON_STARTUP", False):
        from database.db import init_db
        utils.logger.info("[Main] INIT_DB_ON_STARTUP=True，正在初始化数据库表结构...")
        await init_db("mysql")
        utils.logger.info("[Main] 数据库表结构初始化完成")

    await trickle_service_loop()


async def async_cleanup() -> None:
    """清理资源"""
    await _cleanup_crawler()


if __name__ == "__main__":
    from tools.app_runner import run

    def _force_stop() -> None:
        c = crawler
        if not c:
            return
        cdp_manager = getattr(c, "cdp_manager", None)
        launcher = getattr(cdp_manager, "launcher", None)
        if not launcher:
            return
        try:
            launcher.cleanup()
        except Exception:
            pass

    platforms = config.PLATFORM
    supported_platforms = ", ".join(CrawlerFactory.CRAWLERS.keys())

    print("=" * 60)
    print(f"  涓流爬取服务 | 平台: {platforms} (共 {len(platforms)} 个)")
    print(f"  支持的平台: {supported_platforms}")
    print(f"  关键词: {config.KEYWORDS}")
    print(f"  每关键词目标: {config.TRICKLE_MAX_NOTES_PER_KEYWORD} 条/天")
    print(f"  每日随机执行时间: {config.TRICKLE_DAILY_TIME_RANGE_START} ~ {config.TRICKLE_DAILY_TIME_RANGE_END}")
    print(f"  页间休眠: {config.TRICKLE_SLEEP_BETWEEN_PAGES}s")
    print(f"  关键词间休眠: {config.TRICKLE_SLEEP_BETWEEN_KEYWORDS}s")
    print("=" * 60)

    run(main, async_cleanup, cleanup_timeout_seconds=15.0, on_first_interrupt=_force_stop)