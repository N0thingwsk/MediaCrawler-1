import asyncio
import os
import random
from asyncio import Task
from typing import Dict, List, Optional

from playwright.async_api import (
    BrowserContext,
    BrowserType,
    Page,
    Playwright,
    async_playwright,
)

import config
from base.base_crawler import AbstractCrawler
from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
from store import douyin as douyin_store
from tools import utils
from tools.cdp_browser import CDPBrowserManager
from var import crawler_type_var, source_keyword_var

from .client import DouYinClient
from .cookie_manager import DouYinCookieManager
from .exception import DataFetchError
from .field import PublishTimeType
from .login import DouYinLogin


class DouYinCrawler(AbstractCrawler):
    context_page: Page
    dy_client: DouYinClient
    browser_context: BrowserContext
    cdp_manager: Optional[CDPBrowserManager]
    cookie_manager: Optional[DouYinCookieManager]

    def __init__(self) -> None:
        self.index_url = "https://www.douyin.com"
        self.cdp_manager = None
        self.cookie_manager = None
        self.ip_proxy_pool = None  # Proxy IP pool for automatic proxy refresh

    async def start(self) -> None:
        playwright_proxy_format, httpx_proxy_format = None, None
        if config.ENABLE_IP_PROXY:
            self.ip_proxy_pool = await create_ip_pool(config.IP_PROXY_POOL_COUNT, enable_validate_ip=True)
            ip_proxy_info: IpInfoModel = await self.ip_proxy_pool.get_proxy()
            playwright_proxy_format, httpx_proxy_format = utils.format_proxy_info(ip_proxy_info)

        async with async_playwright() as playwright:
            # Select startup mode based on configuration
            if config.ENABLE_CDP_MODE:
                utils.logger.info("[DouYinCrawler] 使用CDP模式启动浏览器")
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright,
                    playwright_proxy_format,
                    None,
                    headless=config.CDP_HEADLESS,
                )
            else:
                utils.logger.info("[DouYinCrawler] 使用标准模式启动浏览器")
                # Launch a browser context.
                chromium = playwright.chromium
                self.browser_context = await self.launch_browser(
                    chromium,
                    playwright_proxy_format,
                    user_agent=None,
                    headless=config.HEADLESS,
                )
                # stealth.min.js is a js script to prevent the website from detecting the crawler.
                await self.browser_context.add_init_script(path="libs/stealth.min.js")

            self.context_page = await self.browser_context.new_page()
            await self.context_page.goto(self.index_url)

            # 初始化 Cookie 管理器，尝试从持久化文件加载 Cookie
            self.cookie_manager = DouYinCookieManager(
                browser_context=self.browser_context,
            )
            await self.cookie_manager.load_cookies_from_file()

            self.dy_client = await self.create_douyin_client(httpx_proxy_format)
            if not await self.dy_client.pong(browser_context=self.browser_context):
                login_obj = DouYinLogin(
                    login_type=config.LOGIN_TYPE,
                    login_phone="",  # you phone number
                    browser_context=self.browser_context,
                    context_page=self.context_page,
                    cookie_str=config.COOKIES,
                )
                await login_obj.begin()
                await self.dy_client.update_cookies(browser_context=self.browser_context)
            # 登录成功后保存 Cookie 并启动后台自动刷新
            await self.cookie_manager.save_cookies_to_file()
            self.cookie_manager.set_context_page(self.context_page)
            self.cookie_manager.start_auto_refresh(self.dy_client)

            crawler_type_var.set(config.CRAWLER_TYPE)
            # 涓流模式：低速持续爬取
            await self.trickle_search()

            # 爬取完成，停止自动刷新并做最后一次 Cookie 持久化
            if self.cookie_manager:
                await self.cookie_manager.stop_auto_refresh()

            utils.logger.info("[DouYinCrawler.start] Douyin Crawler finished ...")

    @staticmethod
    def _get_keywords_list() -> List[str]:
        """兼容 KEYWORDS 为字符串或列表的情况"""
        kw = config.KEYWORDS
        if isinstance(kw, list):
            return [k.strip() for k in kw if k.strip()]
        return [k.strip() for k in kw.split(",") if k.strip()]

    async def search(self) -> None:
        """实现抽象基类的 search 方法，内部委托给 trickle_search"""
        await self.trickle_search()

    @staticmethod
    def _human_sleep_time(base: float, jitter_ratio: float = 0.5) -> float:
        """
        生成模拟人类行为的随机休眠时间。
        Args:
            base: 基础休眠秒数
            jitter_ratio: 抖动比例，如 0.5 表示 base * (1 ± 0.5)
        Returns:
            带随机抖动的休眠秒数
        """
        low = base * (1 - jitter_ratio)
        high = base * (1 + jitter_ratio)
        return random.uniform(low, high)

    async def _simulate_user_read(self) -> None:
        """
        模拟用户阅读一条内容的行为：
        - 随机停顿 3~8 秒（可配置）
        - 偶尔滚动页面
        """
        delay = random.uniform(config.USER_READ_DELAY_MIN, config.USER_READ_DELAY_MAX)
        await asyncio.sleep(delay)

        # 30% 概率在阅读时滚动页面
        if random.random() < 0.3:
            try:
                scroll_y = random.randint(100, 400)
                await self.context_page.evaluate(f"window.scrollBy(0, {scroll_y})")
                await asyncio.sleep(random.uniform(0.3, 1.0))
            except Exception:
                pass

    async def _simulate_page_scroll(self) -> None:
        """
        模拟用户翻页行为：
        - 随机停顿 5~15 秒（可配置）
        - 滚动页面到底部附近
        - 偶尔执行随机浏览动作
        """
        delay = random.uniform(config.USER_PAGE_SCROLL_DELAY_MIN, config.USER_PAGE_SCROLL_DELAY_MAX)

        # 模拟用户随机浏览动作（滚动、鼠标移动等）
        if random.random() < config.USER_RANDOM_ACTION_PROBABILITY:
            try:
                actions = ["scroll_up", "scroll_down", "mouse_move"]
                action = random.choice(actions)
                if action == "scroll_up":
                    await self.context_page.evaluate(f"window.scrollBy(0, -{random.randint(100, 300)})")
                elif action == "scroll_down":
                    await self.context_page.evaluate(f"window.scrollBy(0, {random.randint(200, 600)})")
                elif action == "mouse_move":
                    x = random.randint(200, 1200)
                    y = random.randint(200, 800)
                    await self.context_page.mouse.move(x, y)
                utils.logger.debug(f"[DouYinCrawler] 模拟用户随机动作: {action}")
                await asyncio.sleep(random.uniform(1.0, 3.0))
            except Exception:
                pass

        await asyncio.sleep(delay)

    async def _simulate_user_idle(self) -> bool:
        """
        模拟用户"走神"：有一定概率长时间停顿。
        Returns:
            是否触发了走神
        """
        if random.random() < config.USER_IDLE_PROBABILITY:
            idle_time = random.uniform(config.USER_IDLE_DELAY_MIN, config.USER_IDLE_DELAY_MAX)
            utils.logger.info(
                f"[DouYinCrawler] 模拟用户走神，暂停 {idle_time:.0f}s ..."
            )
            await asyncio.sleep(idle_time)
            return True
        return False

    async def _simulate_keyword_switch(self) -> None:
        """
        模拟用户切换搜索关键词的行为：
        - 随机停顿 30~90 秒（可配置）
        - 模拟清空搜索框、输入新关键词的过程
        """
        delay = random.uniform(config.USER_KEYWORD_SWITCH_DELAY_MIN, config.USER_KEYWORD_SWITCH_DELAY_MAX)
        utils.logger.info(f"[DouYinCrawler] 模拟用户切换关键词，休眠 {delay:.1f}s")

        # 切换关键词前偶尔滚动回页面顶部
        if random.random() < 0.5:
            try:
                await self.context_page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(random.uniform(1.0, 3.0))
            except Exception:
                pass

        await asyncio.sleep(delay)

    async def _wait_for_active_time(self) -> None:
        """
        如果当前处于休眠时段，等待直到进入活跃时段。
        等待期间每隔 SLEEP_CHECK_INTERVAL 秒检查一次。
        Cookie 保活由 cookie_manager 后台任务独立维护，不受影响。
        """
        from datetime import datetime

        if not getattr(config, "ENABLE_SCHEDULE_MODE", False):
            return

        if not self.cookie_manager or self.cookie_manager.is_active_time():
            return

        check_interval = getattr(config, "SLEEP_CHECK_INTERVAL", 300)
        now_str = datetime.now().strftime("%H:%M:%S")
        active_hours_str = ", ".join(
            [f"{s}~{e}" for s, e in getattr(config, "ACTIVE_HOURS", [])]
        )
        utils.logger.info(
            f"[DouYinCrawler] 当前时间 {now_str} 处于休眠时段，暂停爬取 | "
            f"活跃时段: {active_hours_str} | "
            f"Cookie 保活仍在后台运行（降频模式）"
        )

        while not self.cookie_manager.is_active_time():
            await asyncio.sleep(check_interval * random.uniform(0.8, 1.2))

        wake_str = datetime.now().strftime("%H:%M:%S")
        utils.logger.info(
            f"[DouYinCrawler] 进入活跃时段 {wake_str}，恢复爬取"
        )

    async def trickle_search(self) -> None:
        """
        涓流模式搜索：持续循环爬取，模拟真实用户浏览行为。

        运行模式：
        - 持续模式（ENABLE_CONTINUOUS_MODE=True）：无限循环，每轮爬完后休眠再继续
        - 单次模式（ENABLE_CONTINUOUS_MODE=False）：只执行一轮

        作息模拟（ENABLE_SCHEDULE_MODE=True）：
        - 只在配置的活跃时段内爬取（如 8:00~12:00, 14:00~18:00, 20:00~23:00）
        - 休眠时段暂停爬取，但 Cookie 保活后台任务持续运行（降频模式）
        - 进入活跃时段后自动恢复爬取

        每轮行为：
        1. 遍历所有关键词，每个关键词爬取指定数量的数据
        2. 每条数据处理后模拟用户阅读停顿（3~8秒）
        3. 每页翻页时模拟滚动和随机浏览（5~15秒）
        4. 偶尔触发"走神"长停顿（30~120秒）
        5. 关键词切换时模拟搜索行为（30~90秒）
        """
        from datetime import datetime

        keywords = self._get_keywords_list()
        max_per_keyword = config.TRICKLE_MAX_NOTES_PER_KEYWORD
        dy_limit_count = 10  # 抖音每页固定返回数
        round_number = 0

        schedule_mode = getattr(config, "ENABLE_SCHEDULE_MODE", False)
        active_hours_str = ", ".join(
            [f"{s}~{e}" for s, e in getattr(config, "ACTIVE_HOURS", [])]
        ) if schedule_mode else "未启用"

        utils.logger.info(
            f"[DouYinCrawler.trickle_search] 启动涓流爬取 | "
            f"持续模式: {config.ENABLE_CONTINUOUS_MODE} | "
            f"作息模拟: {schedule_mode} | "
            f"活跃时段: {active_hours_str} | "
            f"关键词数: {len(keywords)} | 每关键词目标: {max_per_keyword} 条"
        )

        while True:
            # 每轮开始前检查是否在活跃时段
            await self._wait_for_active_time()

            round_number += 1
            today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result: Dict[str, int] = {}

            utils.logger.info(
                f"[DouYinCrawler.trickle_search] ===== 第 {round_number} 轮开始 | {today_str} ====="
            )

            # 每轮随机打乱关键词顺序，避免固定模式
            shuffled_keywords = keywords.copy()
            if len(shuffled_keywords) > 1:
                random.shuffle(shuffled_keywords)

            for kw_idx, keyword in enumerate(shuffled_keywords):
                source_keyword_var.set(keyword)
                collected_count = 0
                aweme_id_set: set = set()  # 去重
                page = 0
                dy_search_id = ""
                consecutive_errors = 0

                utils.logger.info(
                    f"[DouYinCrawler.trickle_search] [{kw_idx+1}/{len(shuffled_keywords)}] "
                    f"开始爬取关键词: '{keyword}'"
                )

                while collected_count < max_per_keyword:
                    try:
                        utils.logger.info(
                            f"[DouYinCrawler.trickle_search] 关键词: '{keyword}' | "
                            f"页码: {page} | 已爬取: {collected_count}/{max_per_keyword}"
                        )
                        posts_res = await self.dy_client.search_info_by_keyword(
                            keyword=keyword,
                            offset=page * dy_limit_count,
                            publish_time=PublishTimeType(config.PUBLISH_TIME_TYPE),
                            search_id=dy_search_id,
                        )
                        consecutive_errors = 0  # 请求成功重置连续错误计数

                        if posts_res.get("data") is None or posts_res.get("data") == []:
                            utils.logger.info(
                                f"[DouYinCrawler.trickle_search] 关键词: '{keyword}' 第 {page} 页无数据，停止"
                            )
                            break

                        if "data" not in posts_res:
                            utils.logger.error(
                                f"[DouYinCrawler.trickle_search] 关键词: '{keyword}' 请求异常，账号可能被风控"
                            )
                            # 风控时主动刷新页面续约 Cookie
                            if self.cookie_manager:
                                utils.logger.info("[DouYinCrawler.trickle_search] 检测到风控，尝试刷新页面续约...")
                                await self.cookie_manager.force_page_refresh()
                                await self.dy_client.update_cookies(browser_context=self.browser_context)
                            break

                        dy_search_id = posts_res.get("extra", {}).get("logid", "")
                        page_aweme_list = []

                        for post_item in posts_res.get("data", []):
                            if collected_count >= max_per_keyword:
                                break
                            try:
                                aweme_info: Dict = (
                                    post_item.get("aweme_info")
                                    or post_item.get("aweme_mix_info", {}).get("mix_items")[0]
                                )
                            except (TypeError, IndexError):
                                continue

                            aweme_id = aweme_info.get("aweme_id", "")
                            if not aweme_id or aweme_id in aweme_id_set:
                                continue
                            aweme_id_set.add(aweme_id)
                            collected_count += 1
                            page_aweme_list.append(aweme_id)
                            await douyin_store.update_douyin_aweme(aweme_item=aweme_info)
                            await self.get_aweme_media(aweme_item=aweme_info)

                            # 模拟用户阅读每条内容（3~8秒 + 偶尔滚动）
                            await self._simulate_user_read()

                        # 批量爬取评论
                        await self.batch_get_note_comments(page_aweme_list)

                        page += 1

                        # 模拟用户翻页行为（5~15秒 + 随机浏览动作）
                        await self._simulate_page_scroll()

                        # 偶尔触发用户"走神"长停顿
                        await self._simulate_user_idle()

                        utils.logger.info(
                            f"[DouYinCrawler.trickle_search] 关键词: '{keyword}' | "
                            f"第 {page} 页完成，已爬取 {collected_count} 条"
                        )

                    except DataFetchError as e:
                        consecutive_errors += 1
                        # 指数退避：基础间隔 * 2^(错误次数-1)，并加随机抖动，上限封顶
                        base_interval = getattr(config, "TRICKLE_ERROR_RETRY_BASE", 30)
                        max_interval = getattr(config, "TRICKLE_ERROR_RETRY_MAX", 600)
                        backoff = min(base_interval * (2 ** (consecutive_errors - 1)), max_interval)
                        backoff_with_jitter = backoff * random.uniform(0.8, 1.2)
                        utils.logger.error(
                            f"[DouYinCrawler.trickle_search] 关键词: '{keyword}' 爬取错误 "
                            f"(连续第 {consecutive_errors} 次): {e} | "
                            f"指数退避等待 {backoff_with_jitter:.0f}s"
                        )
                        if consecutive_errors >= getattr(config, "TRICKLE_MAX_CONSECUTIVE_ERRORS", 5):
                            utils.logger.error(
                                f"[DouYinCrawler.trickle_search] 关键词: '{keyword}' 连续错误达 {consecutive_errors} 次，跳过"
                            )
                            # 连续错误时尝试刷新页面续约
                            if self.cookie_manager:
                                await self.cookie_manager.force_page_refresh()
                                await self.dy_client.update_cookies(browser_context=self.browser_context)
                            break
                        await asyncio.sleep(backoff_with_jitter)

                    except Exception as e:
                        utils.logger.error(
                            f"[DouYinCrawler.trickle_search] 关键词: '{keyword}' 未知错误: {e}"
                        )
                        break

                result[keyword] = collected_count
                utils.logger.info(
                    f"[DouYinCrawler.trickle_search] 关键词: '{keyword}' 爬取完成 | "
                    f"实际: {collected_count}/{max_per_keyword} 条"
                )

                # 关键词之间模拟用户切换搜索词的行为
                if kw_idx < len(shuffled_keywords) - 1:
                    # 切换关键词前检查是否进入休眠时段
                    await self._wait_for_active_time()
                    await self._simulate_keyword_switch()

            # 打印本轮汇总
            total = sum(result.values())
            utils.logger.info(
                f"[DouYinCrawler.trickle_search] 第 {round_number} 轮完成 | "
                f"总计: {total} 条 | 详情: {result}"
            )

            # 判断是否继续循环
            if not config.ENABLE_CONTINUOUS_MODE:
                utils.logger.info("[DouYinCrawler.trickle_search] 单次模式，爬取完成退出")
                break

            # 持续模式：轮次间休眠，模拟用户"刷累了休息一下"
            rest_minutes = random.uniform(
                config.CONTINUOUS_REST_MIN_MINUTES,
                config.CONTINUOUS_REST_MAX_MINUTES,
            )
            rest_seconds = rest_minutes * 60
            next_time = datetime.now().strftime("%H:%M:%S")
            utils.logger.info(
                f"[DouYinCrawler.trickle_search] 持续模式 | 本轮休眠 {rest_minutes:.1f} 分钟 | "
                f"当前时间: {next_time}"
            )
            await asyncio.sleep(rest_seconds)

    async def batch_get_note_comments(self, aweme_list: List[str]) -> None:
        """
        Batch get note comments
        """
        if not config.ENABLE_GET_COMMENTS:
            utils.logger.info(f"[DouYinCrawler.batch_get_note_comments] Crawling comment mode is not enabled")
            return

        task_list: List[Task] = []
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        for aweme_id in aweme_list:
            task = asyncio.create_task(self.get_comments(aweme_id, semaphore), name=aweme_id)
            task_list.append(task)
        if len(task_list) > 0:
            await asyncio.wait(task_list)

    async def get_comments(self, aweme_id: str, semaphore: asyncio.Semaphore) -> None:
        async with semaphore:
            try:
                # 评论爬取间隔与主内容对齐，使用模拟用户阅读延迟配置（3~8秒）
                crawl_interval = random.uniform(
                    config.USER_READ_DELAY_MIN,
                    config.USER_READ_DELAY_MAX
                )
                await self.dy_client.get_aweme_all_comments(
                    aweme_id=aweme_id,
                    crawl_interval=crawl_interval,
                    callback=douyin_store.batch_update_dy_aweme_comments,
                    max_count=config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES,
                )
                # 评论爬取完成后随机休眠，模拟用户看完评论后的停顿
                after_sleep = random.uniform(config.USER_READ_DELAY_MIN, config.USER_PAGE_SCROLL_DELAY_MAX)
                await asyncio.sleep(after_sleep)
                utils.logger.info(f"[DouYinCrawler.get_comments] Sleeping for {after_sleep:.1f} seconds after fetching comments for aweme {aweme_id}")
                utils.logger.info(f"[DouYinCrawler.get_comments] aweme_id: {aweme_id} comments have all been obtained and filtered ...")
            except DataFetchError as e:
                utils.logger.error(f"[DouYinCrawler.get_comments] aweme_id: {aweme_id} get comments failed, error: {e}")

    async def create_douyin_client(self, httpx_proxy: Optional[str]) -> DouYinClient:
        """Create douyin client"""
        cookie_str, cookie_dict = utils.convert_cookies(await self.browser_context.cookies())  # type: ignore
        douyin_client = DouYinClient(
            proxy=httpx_proxy,
            headers={
                "User-Agent": await self.context_page.evaluate("() => navigator.userAgent"),
                "Cookie": cookie_str,
                "Host": "www.douyin.com",
                "Origin": "https://www.douyin.com/",
                "Referer": "https://www.douyin.com/",
                "Content-Type": "application/json;charset=UTF-8",
            },
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
            proxy_ip_pool=self.ip_proxy_pool,  # Pass proxy pool for automatic refresh
        )
        return douyin_client

    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """Launch browser and create browser context"""
        if config.SAVE_LOGIN_STATE:
            user_data_dir = os.path.join(os.getcwd(), "browser_data", config.USER_DATA_DIR % config.PLATFORM)  # type: ignore
            browser_context = await chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                accept_downloads=True,
                headless=headless,
                proxy=playwright_proxy,  # type: ignore
                viewport={
                    "width": 1920,
                    "height": 1080
                },
                user_agent=user_agent,
            )  # type: ignore
            return browser_context
        else:
            browser = await chromium.launch(headless=headless, proxy=playwright_proxy)  # type: ignore
            browser_context = await browser.new_context(viewport={"width": 1920, "height": 1080}, user_agent=user_agent)
            return browser_context

    async def launch_browser_with_cdp(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """
        使用CDP模式启动浏览器
        """
        try:
            self.cdp_manager = CDPBrowserManager()
            browser_context = await self.cdp_manager.launch_and_connect(
                playwright=playwright,
                playwright_proxy=playwright_proxy,
                user_agent=user_agent,
                headless=headless,
            )

            # Add anti-detection script
            await self.cdp_manager.add_stealth_script()

            # Show browser information
            browser_info = await self.cdp_manager.get_browser_info()
            utils.logger.info(f"[DouYinCrawler] CDP浏览器信息: {browser_info}")

            return browser_context

        except Exception as e:
            utils.logger.error(f"[DouYinCrawler] CDP模式启动失败，回退到标准模式: {e}")
            # Fall back to standard mode
            chromium = playwright.chromium
            return await self.launch_browser(chromium, playwright_proxy, user_agent, headless)

    async def close(self) -> None:
        """Close browser context"""
        # 停止 Cookie 自动刷新并做最终持久化
        if self.cookie_manager:
            await self.cookie_manager.stop_auto_refresh()
            self.cookie_manager = None

        # If you use CDP mode, special processing is required
        if self.cdp_manager:
            await self.cdp_manager.cleanup()
            self.cdp_manager = None
        else:
            await self.browser_context.close()
        utils.logger.info("[DouYinCrawler.close] Browser context closed ...")

    async def get_aweme_media(self, aweme_item: Dict):
        """
        获取抖音媒体，自动判断媒体类型是短视频还是帖子图片并下载

        Args:
            aweme_item (Dict): 抖音作品详情
        """
        if not config.ENABLE_GET_MEIDAS:
            utils.logger.info(f"[DouYinCrawler.get_aweme_media] Crawling image mode is not enabled")
            return
        # List of note urls. If it is a short video type, an empty list will be returned.
        note_download_url: List[str] = douyin_store._extract_note_image_list(aweme_item)
        # The video URL will always exist, but when it is a short video type, the file is actually an audio file.
        video_download_url: str = douyin_store._extract_video_download_url(aweme_item)
        # TODO: Douyin does not adopt the audio and video separation strategy, so the audio can be separated from the original video and will not be extracted for the time being.
        if note_download_url:
            await self.get_aweme_images(aweme_item)
        else:
            await self.get_aweme_video(aweme_item)

    async def get_aweme_images(self, aweme_item: Dict):
        """
        get aweme images. please use get_aweme_media

        Args:
            aweme_item (Dict): 抖音作品详情
        """
        if not config.ENABLE_GET_MEIDAS:
            return
        aweme_id = aweme_item.get("aweme_id")
        # List of note urls. If it is a short video type, an empty list will be returned.
        note_download_url: List[str] = douyin_store._extract_note_image_list(aweme_item)

        if not note_download_url:
            return
        picNum = 0
        for url in note_download_url:
            if not url:
                continue
            content = await self.dy_client.get_aweme_media(url)
            await asyncio.sleep(random.random())
            if content is None:
                continue
            extension_file_name = f"{picNum:>03d}.jpeg"
            picNum += 1
            await douyin_store.update_dy_aweme_image(aweme_id, content, extension_file_name)

    async def get_aweme_video(self, aweme_item: Dict):
        """
        get aweme videos. please use get_aweme_media

        Args:
            aweme_item (Dict): 抖音作品详情
        """
        if not config.ENABLE_GET_MEIDAS:
            return
        aweme_id = aweme_item.get("aweme_id")

        # The video URL will always exist, but when it is a short video type, the file is actually an audio file.
        video_download_url: str = douyin_store._extract_video_download_url(aweme_item)

        if not video_download_url:
            return
        content = await self.dy_client.get_aweme_media(video_download_url)
        await asyncio.sleep(random.random())
        if content is None:
            return
        extension_file_name = f"video.mp4"
        await douyin_store.update_dy_aweme_video(aweme_id, content, extension_file_name)