# -*- coding: utf-8 -*-
"""
抖音 Cookie 管理模块
负责 Cookie 的持久化（保存到文件 / 从文件加载）和运行时自动刷新。
增强功能：页面活跃保持、主动刷新页面续约、模拟用户微操作防止会话过期。
"""

import asyncio
import json
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from playwright.async_api import BrowserContext, Page

import config
from tools import utils


class DouYinCookieManager:
    """抖音 Cookie 持久化 & 自动刷新 & 会话保活管理器"""

    # Cookie 持久化文件的默认存放目录
    DEFAULT_COOKIE_DIR = os.path.join(os.getcwd(), "browser_data")
    # 持久化文件名
    COOKIE_FILE_NAME = "douyin_cookies.json"

    def __init__(
        self,
        browser_context: BrowserContext,
        cookie_dir: Optional[str] = None,
    ):
        """
        Args:
            browser_context: Playwright 浏览器上下文
            cookie_dir: Cookie 文件保存目录，默认为 browser_data/
        """
        self.browser_context = browser_context
        self.cookie_dir = cookie_dir or self.DEFAULT_COOKIE_DIR
        self.cookie_file_path = os.path.join(self.cookie_dir, self.COOKIE_FILE_NAME)

        # 从配置读取各项间隔
        self.refresh_interval = getattr(config, "COOKIE_REFRESH_INTERVAL", 90)
        self.keep_alive_interval = getattr(config, "PAGE_KEEP_ALIVE_INTERVAL", 60)
        self.full_refresh_interval = getattr(config, "PAGE_FULL_REFRESH_INTERVAL", 600)

        # 后台任务句柄
        self._refresh_task: Optional[asyncio.Task] = None
        self._keep_alive_task: Optional[asyncio.Task] = None
        self._page_refresh_task: Optional[asyncio.Task] = None

        # 上下文页面引用（用于页面级操作）
        self._context_page: Optional[Page] = None

        # 上次页面完整刷新时间
        self._last_full_refresh = time.time()

        # 停止标志，用于通知后台任务优雅退出
        self._stopped = False

        # 作息时间配置
        self._schedule_enabled = getattr(config, "ENABLE_SCHEDULE_MODE", False)
        self._active_hours: List[tuple] = getattr(config, "ACTIVE_HOURS", [])
        self._sleep_keep_alive_multiplier = getattr(config, "SLEEP_KEEP_ALIVE_MULTIPLIER", 5)
        self._sleep_page_refresh_multiplier = getattr(config, "SLEEP_PAGE_REFRESH_MULTIPLIER", 3)

    def set_context_page(self, page: Page) -> None:
        """设置用于页面操作的 Page 对象"""
        self._context_page = page

    def _is_page_alive(self) -> bool:
        """检查页面和浏览器上下文是否仍然可用"""
        if self._stopped:
            return False
        if not self._context_page:
            return False
        try:
            # Playwright 的 Page 对象在关闭后 is_closed() 返回 True
            if self._context_page.is_closed():
                return False
        except Exception:
            return False
        return True

    @staticmethod
    def _is_closed_error(error: Exception) -> bool:
        """判断异常是否为浏览器/页面已关闭的错误"""
        error_msg = str(error).lower()
        closed_keywords = ["closed", "disconnected", "disposed", "target page", "destroyed"]
        return any(kw in error_msg for kw in closed_keywords)

    def is_active_time(self) -> bool:
        """
        判断当前时间是否在活跃时段内。
        如果未启用作息模式，始终返回 True。
        """
        if not self._schedule_enabled or not self._active_hours:
            return True

        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute  # 当前时间转为分钟数

        for start_str, end_str in self._active_hours:
            start_h, start_m = map(int, start_str.split(":"))
            end_h, end_m = map(int, end_str.split(":"))
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m

            if start_minutes <= end_minutes:
                # 不跨午夜：如 08:00 ~ 12:00
                if start_minutes <= current_minutes < end_minutes:
                    return True
            else:
                # 跨午夜：如 22:00 ~ 06:00
                if current_minutes >= start_minutes or current_minutes < end_minutes:
                    return True

        return False

    def _get_interval_multiplier(self) -> float:
        """
        根据当前时段返回间隔倍率。
        活跃时段返回 1.0，休眠时段返回配置的倍率。
        """
        if self.is_active_time():
            return 1.0
        return float(self._sleep_keep_alive_multiplier)

    # ======================== 持久化：保存 ========================

    async def save_cookies_to_file(self) -> None:
        """
        将当前浏览器上下文中的 Cookie 序列化保存到 JSON 文件。
        """
        cookies = await self.browser_context.cookies()
        if not cookies:
            utils.logger.warning("[CookieManager] 浏览器中没有 Cookie，跳过保存")
            return

        os.makedirs(self.cookie_dir, exist_ok=True)
        data = {
            "cookies": cookies,
            "saved_at": time.time(),
        }
        with open(self.cookie_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        utils.logger.info(
            f"[CookieManager] 已保存 {len(cookies)} 条 Cookie 到 {self.cookie_file_path}"
        )

    # ======================== 持久化：加载 ========================

    async def load_cookies_from_file(self) -> bool:
        """
        从 JSON 文件中加载 Cookie 并注入到浏览器上下文。
        """
        if not os.path.exists(self.cookie_file_path):
            utils.logger.info(f"[CookieManager] Cookie 文件不存在: {self.cookie_file_path}")
            return False

        try:
            with open(self.cookie_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            cookies = data.get("cookies", [])
            saved_at = data.get("saved_at", 0)
            if not cookies:
                utils.logger.warning("[CookieManager] Cookie 文件为空")
                return False

            await self.browser_context.add_cookies(cookies)  # type: ignore

            age_minutes = (time.time() - saved_at) / 60
            utils.logger.info(
                f"[CookieManager] 已从文件加载 {len(cookies)} 条 Cookie（保存于 {age_minutes:.1f} 分钟前）"
            )
            return True
        except Exception as e:
            utils.logger.error(f"[CookieManager] 加载 Cookie 文件失败: {e}")
            return False

    # ======================== 运行时刷新 ========================

    def get_cookie_str_and_dict(self, cookies) -> Tuple[str, Dict]:
        """将浏览器原始 Cookie 列表转为 (cookie_str, cookie_dict)"""
        return utils.convert_cookies(cookies)

    async def refresh_cookies(self) -> Tuple[str, Dict]:
        """
        手动触发一次 Cookie 刷新：
        1. 从浏览器上下文获取最新 Cookie
        2. 持久化到文件
        3. 返回 (cookie_str, cookie_dict)
        """
        cookies = await self.browser_context.cookies()
        cookie_str, cookie_dict = self.get_cookie_str_and_dict(cookies)
        await self.save_cookies_to_file()
        utils.logger.debug("[CookieManager] Cookie 已刷新并持久化")
        return cookie_str, cookie_dict

    # ======================== 页面活跃保持（轻量级） ========================

    async def _simulate_micro_interaction(self) -> None:
        """
        在页面上执行轻量级微操作，保持会话活跃。
        模拟真实用户的微小动作：鼠标微移、轻微滚动、悬停、选中文字等。
        包含 8 种动作类型，随机选择执行，更贴近真实用户行为。
        """
        if not self._is_page_alive():
            return

        try:
            action = random.choice([
                "scroll", "mouse_move", "focus",
                "hover_element", "mouse_curve", "select_text",
                "visibility_change", "touch_scroll"
            ])

            if action == "scroll":
                # 轻微滚动页面（上下随机，幅度随机）
                scroll_y = random.randint(-80, 80)
                await self._context_page.evaluate(f"window.scrollBy(0, {scroll_y})")

            elif action == "mouse_move":
                # 鼠标随机移动到页面某个位置
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                await self._context_page.mouse.move(x, y)

            elif action == "focus":
                # 触发页面焦点/鼠标移动事件
                await self._context_page.evaluate("document.dispatchEvent(new Event('mousemove'))")

            elif action == "hover_element":
                # 模拟鼠标悬停在页面上的某个可见元素上（如视频卡片、标题等）
                hover_js = """
                (() => {
                    const elements = document.querySelectorAll('a, div[class*="video"], div[class*="card"], span');
                    if (elements.length > 0) {
                        const el = elements[Math.floor(Math.random() * Math.min(elements.length, 20))];
                        el.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
                        el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
                    }
                })()
                """
                await self._context_page.evaluate(hover_js)

            elif action == "mouse_curve":
                # 模拟鼠标沿曲线移动（真实用户鼠标轨迹不是直线）
                start_x = random.randint(100, 600)
                start_y = random.randint(100, 400)
                end_x = start_x + random.randint(-200, 200)
                end_y = start_y + random.randint(-150, 150)
                # 分 3~5 步移动，模拟曲线轨迹
                steps = random.randint(3, 5)
                for i in range(steps):
                    ratio = (i + 1) / steps
                    # 加入随机偏移模拟曲线
                    jitter_x = random.randint(-15, 15)
                    jitter_y = random.randint(-10, 10)
                    cur_x = int(start_x + (end_x - start_x) * ratio + jitter_x)
                    cur_y = int(start_y + (end_y - start_y) * ratio + jitter_y)
                    cur_x = max(0, min(cur_x, 1200))
                    cur_y = max(0, min(cur_y, 800))
                    await self._context_page.mouse.move(cur_x, cur_y)
                    await asyncio.sleep(random.uniform(0.05, 0.15))

            elif action == "select_text":
                # 模拟用户无意识地选中一小段文字后取消（常见的真实用户行为）
                select_js = """
                (() => {
                    const textNodes = document.querySelectorAll('p, span, h1, h2, h3');
                    if (textNodes.length > 0) {
                        const el = textNodes[Math.floor(Math.random() * Math.min(textNodes.length, 10))];
                        const range = document.createRange();
                        if (el.firstChild && el.firstChild.nodeType === 3) {
                            const textLen = el.firstChild.textContent.length;
                            if (textLen > 2) {
                                const start = Math.floor(Math.random() * (textLen - 2));
                                const end = Math.min(start + Math.floor(Math.random() * 5) + 1, textLen);
                                range.setStart(el.firstChild, start);
                                range.setEnd(el.firstChild, end);
                                const sel = window.getSelection();
                                sel.removeAllRanges();
                                sel.addRange(range);
                                setTimeout(() => sel.removeAllRanges(), 300);
                            }
                        }
                    }
                })()
                """
                await self._context_page.evaluate(select_js)

            elif action == "visibility_change":
                # 模拟用户切换标签页后回来（触发 visibilitychange 事件）
                await self._context_page.evaluate(
                    "document.dispatchEvent(new Event('visibilitychange'))"
                )
                await asyncio.sleep(random.uniform(0.5, 2.0))
                await self._context_page.evaluate(
                    "document.dispatchEvent(new Event('focus'))"
                )

            elif action == "touch_scroll":
                # 模拟触摸式平滑滚动（与普通 scroll 不同，更像移动端/触控板行为）
                smooth_js = f"""
                window.scrollBy({{
                    top: {random.randint(-120, 120)},
                    left: 0,
                    behavior: 'smooth'
                }})
                """
                await self._context_page.evaluate(smooth_js)

            utils.logger.debug(f"[CookieManager] 页面微操作: {action}")
        except Exception as e:
            if self._is_closed_error(e):
                utils.logger.debug("[CookieManager] 页面已关闭，停止微操作")
            else:
                utils.logger.debug(f"[CookieManager] 页面微操作异常（可忽略）: {e}")

    async def _keep_alive_loop(self) -> None:
        """
        后台协程：定期执行页面微操作，保持浏览器会话活跃。
        防止因长时间无操作导致 Cookie/Session 被服务端判定为过期。
        活跃时段：正常频率（~60s）；休眠时段：降频（~300s）。
        """
        utils.logger.info(
            f"[CookieManager] 启动页面活跃保持任务，活跃间隔 {self.keep_alive_interval}s，"
            f"休眠倍率 x{self._sleep_keep_alive_multiplier}"
        )
        while True:
            try:
                # 根据时段动态调整间隔
                multiplier = self._get_interval_multiplier()
                base_interval = self.keep_alive_interval * multiplier
                actual_interval = base_interval * random.uniform(0.7, 1.3)

                if multiplier > 1.0:
                    utils.logger.debug(
                        f"[CookieManager] 休眠时段，保活间隔降频至 {actual_interval:.0f}s"
                    )

                await asyncio.sleep(actual_interval)
                if not self._is_page_alive():
                    utils.logger.info("[CookieManager] 页面已关闭，页面活跃保持任务退出")
                    break
                await self._simulate_micro_interaction()
            except asyncio.CancelledError:
                utils.logger.info("[CookieManager] 页面活跃保持任务已取消")
                break
            except Exception as e:
                if self._is_closed_error(e):
                    utils.logger.info("[CookieManager] 页面/浏览器已关闭，页面活跃保持任务退出")
                    break
                utils.logger.debug(f"[CookieManager] 页面活跃保持异常: {e}")
                await asyncio.sleep(5)

    # ======================== 页面完整刷新续约 ========================

    async def _do_page_refresh(self) -> None:
        """
        执行一次页面完整刷新，触发服务端 Cookie 续约。
        模拟用户按 F5 刷新页面的行为。
        """
        if not self._is_page_alive():
            return

        try:
            utils.logger.info("[CookieManager] 执行页面刷新以续约 Cookie ...")
            await self._context_page.reload(wait_until="domcontentloaded", timeout=30000)

            # 刷新后等待页面稳定
            await asyncio.sleep(random.uniform(2.0, 5.0))

            # 模拟刷新后的用户行为：轻微滚动
            scroll_y = random.randint(100, 300)
            await self._context_page.evaluate(f"window.scrollBy(0, {scroll_y})")

            self._last_full_refresh = time.time()
            utils.logger.info("[CookieManager] 页面刷新完成，Cookie 已续约")
        except Exception as e:
            if self._is_closed_error(e):
                utils.logger.info("[CookieManager] 页面/浏览器已关闭，跳过页面刷新")
            else:
                utils.logger.warning(f"[CookieManager] 页面刷新异常: {e}")

    async def _page_refresh_loop(self) -> None:
        """
        后台协程：定期刷新页面以续约 Cookie。
        间隔时间带随机抖动，避免被检测为机器行为。
        活跃时段：正常频率（~600s）；休眠时段：降频（~1800s）。
        """
        utils.logger.info(
            f"[CookieManager] 启动页面定期刷新任务，活跃间隔 {self.full_refresh_interval}s，"
            f"休眠倍率 x{self._sleep_page_refresh_multiplier}"
        )
        while True:
            try:
                # 根据时段动态调整刷新间隔
                if self.is_active_time():
                    refresh_multiplier = 1.0
                else:
                    refresh_multiplier = float(self._sleep_page_refresh_multiplier)

                base_interval = self.full_refresh_interval * refresh_multiplier
                actual_interval = base_interval * random.uniform(0.7, 1.3)

                if refresh_multiplier > 1.0:
                    utils.logger.debug(
                        f"[CookieManager] 休眠时段，页面刷新间隔降频至 {actual_interval:.0f}s"
                    )

                await asyncio.sleep(actual_interval)
                if not self._is_page_alive():
                    utils.logger.info("[CookieManager] 页面已关闭，页面定期刷新任务退出")
                    break
                await self._do_page_refresh()
            except asyncio.CancelledError:
                utils.logger.info("[CookieManager] 页面定期刷新任务已取消")
                break
            except Exception as e:
                if self._is_closed_error(e):
                    utils.logger.info("[CookieManager] 页面/浏览器已关闭，页面定期刷新任务退出")
                    break
                utils.logger.warning(f"[CookieManager] 页面定期刷新异常: {e}")
                await asyncio.sleep(10)

    # ======================== Cookie 自动同步任务 ========================

    async def _auto_refresh_loop(self, dy_client) -> None:
        """
        后台协程：定期从浏览器同步 Cookie 到 HTTP 客户端并持久化。
        活跃时段：正常频率（~90s）；休眠时段：降频（~450s）。
        """
        utils.logger.info(
            f"[CookieManager] 启动 Cookie 自动同步任务，活跃间隔 {self.refresh_interval}s"
        )
        while True:
            try:
                multiplier = self._get_interval_multiplier()
                base_interval = self.refresh_interval * multiplier
                actual_interval = base_interval * random.uniform(0.8, 1.2)
                await asyncio.sleep(actual_interval)
                cookie_str, cookie_dict = await self.refresh_cookies()
                # 更新客户端的 Cookie
                dy_client.headers["Cookie"] = cookie_str
                dy_client.cookie_dict = cookie_dict
                utils.logger.debug("[CookieManager] 客户端 Cookie 已同步")
            except asyncio.CancelledError:
                utils.logger.info("[CookieManager] Cookie 自动同步任务已取消")
                break
            except Exception as e:
                if self._is_closed_error(e):
                    utils.logger.info("[CookieManager] 浏览器已关闭，Cookie 自动同步任务退出")
                    break
                utils.logger.error(f"[CookieManager] Cookie 同步异常: {e}")
                await asyncio.sleep(5)

    # ======================== 启动 / 停止所有后台任务 ========================

    def start_auto_refresh(self, dy_client) -> None:
        """
        启动所有后台保活任务：
        1. Cookie 自动同步
        2. 页面活跃保持（微操作）
        3. 页面定期刷新（完整刷新续约）
        """
        # Cookie 自动同步
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._auto_refresh_loop(dy_client))

        # 页面活跃保持
        if self._context_page and (self._keep_alive_task is None or self._keep_alive_task.done()):
            self._keep_alive_task = asyncio.create_task(self._keep_alive_loop())

        # 页面定期刷新
        if self._context_page and (self._page_refresh_task is None or self._page_refresh_task.done()):
            self._page_refresh_task = asyncio.create_task(self._page_refresh_loop())

        utils.logger.info("[CookieManager] 所有后台保活任务已启动")

    async def stop_auto_refresh(self) -> None:
        """停止所有后台任务，并做最后一次 Cookie 持久化"""
        self._stopped = True
        tasks = [self._refresh_task, self._keep_alive_task, self._page_refresh_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._refresh_task = None
        self._keep_alive_task = None
        self._page_refresh_task = None

        # 停止时做最后一次保存（浏览器可能已关闭，忽略错误）
        try:
            await self.save_cookies_to_file()
        except Exception as e:
            if not self._is_closed_error(e):
                utils.logger.warning(f"[CookieManager] 最终持久化 Cookie 失败: {e}")
        utils.logger.info("[CookieManager] 所有后台任务已停止，Cookie 已最终持久化")

    # ======================== 手动触发页面刷新（供外部调用） ========================

    async def force_page_refresh(self) -> None:
        """
        外部主动触发一次页面刷新续约。
        适用于检测到 Cookie 即将过期或请求异常时调用。
        """
        if not self._is_page_alive():
            utils.logger.debug("[CookieManager] 页面已关闭，跳过强制刷新")
            return
        await self._do_page_refresh()
        # 刷新后立即同步 Cookie
        cookies = await self.browser_context.cookies()
        cookie_str, cookie_dict = self.get_cookie_str_and_dict(cookies)
        await self.save_cookies_to_file()
        return cookie_str, cookie_dict
