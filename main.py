# -*- coding: utf-8 -*-
"""
多平台涓流爬取服务

以低速、持续的方式每日自动爬取数据。
每天在配置的时间范围内随机选一个时间执行，模拟人类行为，降低风控风险。
每个关键词爬取指定数量的数据，并打上关键词 tag。

支持平台：xhs | dy | ks | bili
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
from media_platform.xhs import XiaoHongShuCrawler
from tools import utils


class CrawlerFactory:
    """多平台爬虫工厂"""
    CRAWLERS = {
        "xhs": XiaoHongShuCrawler,
        "dy": DouYinCrawler,
        "ks": KuaishouCrawler,
        "bili": BilibiliCrawler,
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
    涓流服务主循环，支持两种运行模式：

    1. 持续模式（ENABLE_CONTINUOUS_MODE=True）：
       - 直接启动爬虫，爬虫内部自行循环爬取
       - 每轮爬完后在爬虫内部休眠 30~60 分钟再继续
       - 后台持续保活 Cookie，模拟真实用户行为

    2. 定时模式（ENABLE_CONTINUOUS_MODE=False）：
       - 首次启动立即执行一次
       - 之后每天在配置的时间范围内随机选一个时间执行
    """
    continuous_mode = getattr(config, "ENABLE_CONTINUOUS_MODE", False)

    utils.logger.info(
        f"[TrickleService] 涓流服务启动 | "
        f"运行模式: {'持续爬取' if continuous_mode else '每日定时'} | "
        f"平台: {config.PLATFORM} (共 {len(config.PLATFORM)} 个) | "
        f"关键词: {config.KEYWORDS} | "
        f"每关键词目标: {config.TRICKLE_MAX_NOTES_PER_KEYWORD} 条"
    )

    if continuous_mode:
        # 持续模式：直接启动爬虫，爬虫内部自行无限循环
        schedule_mode = getattr(config, "ENABLE_SCHEDULE_MODE", False)
        schedule_info = ""
        if schedule_mode:
            active_hours = getattr(config, "ACTIVE_HOURS", [])
            hours_str = ", ".join([f"{s}~{e}" for s, e in active_hours])
            schedule_info = (
                f" | 作息模拟: 已启用 | 活跃时段: {hours_str} | "
                f"休眠期保活降频: 微操作x{config.SLEEP_KEEP_ALIVE_MULTIPLIER}, 刷新x{config.SLEEP_PAGE_REFRESH_MULTIPLIER}"
            )
        else:
            schedule_info = " | 作息模拟: 未启用（全天爬取）"

        utils.logger.info(
            f"[TrickleService] 持续模式启动 | "
            f"轮次间休眠: {config.CONTINUOUS_REST_MIN_MINUTES}~{config.CONTINUOUS_REST_MAX_MINUTES} 分钟 | "
            f"Cookie刷新间隔: {config.COOKIE_REFRESH_INTERVAL}s | "
            f"页面保活间隔: {config.PAGE_KEEP_ALIVE_INTERVAL}s"
            f"{schedule_info}"
        )
        await run_trickle_once()
    else:
        # 定时模式：首次启动立即执行，之后每天随机定时
        time_start = config.TRICKLE_DAILY_TIME_RANGE_START
        time_end = config.TRICKLE_DAILY_TIME_RANGE_END
        utils.logger.info(
            f"[TrickleService] 定时模式 | 每日随机执行时间范围: {time_start} ~ {time_end}"
        )

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

    # 检查并自动更新 stealth.min.js（反检测脚本）
    if getattr(config, "ENABLE_STEALTH_AUTO_UPDATE", False):
        from tools.stealth_updater import check_and_update
        max_age = getattr(config, "STEALTH_MAX_AGE_DAYS", 30)
        check_and_update(max_age_days=max_age)

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

    continuous_mode = getattr(config, "ENABLE_CONTINUOUS_MODE", False)
    mode_str = "持续爬取（7x24）" if continuous_mode else "每日定时"

    print("=" * 60)
    print(f"  涓流爬取服务 | 平台: {platforms} (共 {len(platforms)} 个)")
    print(f"  支持的平台: {supported_platforms}")
    print(f"  运行模式: {mode_str}")
    print(f"  关键词: {config.KEYWORDS}")
    print(f"  每关键词目标: {config.TRICKLE_MAX_NOTES_PER_KEYWORD} 条/轮")
    if continuous_mode:
        print(f"  轮次间休眠: {config.CONTINUOUS_REST_MIN_MINUTES}~{config.CONTINUOUS_REST_MAX_MINUTES} 分钟")
        print(f"  用户阅读延迟: {config.USER_READ_DELAY_MIN}~{config.USER_READ_DELAY_MAX}s")
        print(f"  翻页延迟: {config.USER_PAGE_SCROLL_DELAY_MIN}~{config.USER_PAGE_SCROLL_DELAY_MAX}s")
        print(f"  Cookie刷新间隔: {config.COOKIE_REFRESH_INTERVAL}s")
        print(f"  页面保活间隔: {config.PAGE_KEEP_ALIVE_INTERVAL}s")
        schedule_mode = getattr(config, "ENABLE_SCHEDULE_MODE", False)
        if schedule_mode:
            active_hours = getattr(config, "ACTIVE_HOURS", [])
            hours_str = ", ".join([f"{s}~{e}" for s, e in active_hours])
            print(f"  作息模拟: 已启用")
            print(f"  活跃时段: {hours_str}")
            print(f"  休眠期保活降频: 微操作 x{config.SLEEP_KEEP_ALIVE_MULTIPLIER}, 刷新 x{config.SLEEP_PAGE_REFRESH_MULTIPLIER}")
        else:
            print(f"  作息模拟: 未启用（7x24全天爬取）")
    else:
        print(f"  每日随机执行时间: {config.TRICKLE_DAILY_TIME_RANGE_START} ~ {config.TRICKLE_DAILY_TIME_RANGE_END}")

    # 显示 stealth.min.js 自动更新状态
    stealth_auto_update = getattr(config, "ENABLE_STEALTH_AUTO_UPDATE", False)
    if stealth_auto_update:
        stealth_max_age = getattr(config, "STEALTH_MAX_AGE_DAYS", 30)
        print(f"  Stealth.js 自动更新: 已启用 (超过 {stealth_max_age} 天自动更新)")
    else:
        print(f"  Stealth.js 自动更新: 未启用")

    print("=" * 60)

    run(main, async_cleanup, cleanup_timeout_seconds=15.0, on_first_interrupt=_force_stop)