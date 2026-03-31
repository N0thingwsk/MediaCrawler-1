# -*- coding: utf-8 -*-
"""
抖音 Cookie 管理模块
负责 Cookie 的持久化（保存到文件 / 从文件加载）和运行时自动刷新。
"""

import asyncio
import json
import os
import time
from typing import Dict, Optional, Tuple

from playwright.async_api import BrowserContext

from tools import utils


class DouYinCookieManager:
    """抖音 Cookie 持久化 & 自动刷新管理器"""

    # Cookie 持久化文件的默认存放目录
    DEFAULT_COOKIE_DIR = os.path.join(os.getcwd(), "browser_data")
    # 持久化文件名
    COOKIE_FILE_NAME = "douyin_cookies.json"
    # 默认自动刷新间隔（秒），每隔 120 秒从浏览器同步一次 Cookie
    DEFAULT_REFRESH_INTERVAL = 120

    def __init__(
        self,
        browser_context: BrowserContext,
        cookie_dir: Optional[str] = None,
        refresh_interval: int = DEFAULT_REFRESH_INTERVAL,
    ):
        """
        Args:
            browser_context: Playwright 浏览器上下文
            cookie_dir: Cookie 文件保存目录，默认为 browser_data/
            refresh_interval: 自动刷新间隔（秒）
        """
        self.browser_context = browser_context
        self.cookie_dir = cookie_dir or self.DEFAULT_COOKIE_DIR
        self.cookie_file_path = os.path.join(self.cookie_dir, self.COOKIE_FILE_NAME)
        self.refresh_interval = refresh_interval
        # 后台刷新任务句柄
        self._refresh_task: Optional[asyncio.Task] = None

    # ======================== 持久化：保存 ========================

    async def save_cookies_to_file(self) -> None:
        """
        将当前浏览器上下文中的 Cookie 序列化保存到 JSON 文件。
        文件结构：
        {
            "cookies": [ {name, value, domain, path, ...}, ... ],
            "saved_at": 1711190000.123
        }
        """
        cookies = await self.browser_context.cookies()
        if not cookies:
            utils.logger.warning("[DouYinCookieManager.save_cookies_to_file] 浏览器中没有 Cookie，跳过保存")
            return

        os.makedirs(self.cookie_dir, exist_ok=True)
        data = {
            "cookies": cookies,
            "saved_at": time.time(),
        }
        with open(self.cookie_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        utils.logger.info(
            f"[DouYinCookieManager.save_cookies_to_file] 已保存 {len(cookies)} 条 Cookie 到 {self.cookie_file_path}"
        )

    # ======================== 持久化：加载 ========================

    async def load_cookies_from_file(self) -> bool:
        """
        从 JSON 文件中加载 Cookie 并注入到浏览器上下文。
        Returns:
            bool: 加载成功返回 True，文件不存在或加载失败返回 False
        """
        if not os.path.exists(self.cookie_file_path):
            utils.logger.info(
                f"[DouYinCookieManager.load_cookies_from_file] Cookie 文件不存在: {self.cookie_file_path}"
            )
            return False

        try:
            with open(self.cookie_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            cookies = data.get("cookies", [])
            saved_at = data.get("saved_at", 0)
            if not cookies:
                utils.logger.warning("[DouYinCookieManager.load_cookies_from_file] Cookie 文件为空")
                return False

            # 注入 Cookie 到浏览器上下文
            await self.browser_context.add_cookies(cookies)  # type: ignore

            age_minutes = (time.time() - saved_at) / 60
            utils.logger.info(
                f"[DouYinCookieManager.load_cookies_from_file] "
                f"已从文件加载 {len(cookies)} 条 Cookie（保存于 {age_minutes:.1f} 分钟前）"
            )
            return True
        except Exception as e:
            utils.logger.error(
                f"[DouYinCookieManager.load_cookies_from_file] 加载 Cookie 文件失败: {e}"
            )
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
        # 同时持久化
        await self.save_cookies_to_file()
        utils.logger.info("[DouYinCookieManager.refresh_cookies] Cookie 已刷新并持久化")
        return cookie_str, cookie_dict

    # ======================== 后台自动刷新任务 ========================

    async def _auto_refresh_loop(self, dy_client) -> None:
        """
        后台协程：定期从浏览器同步 Cookie 到 HTTP 客户端并持久化。
        Args:
            dy_client: DouYinClient 实例，刷新后自动更新其 headers 和 cookie_dict
        """
        utils.logger.info(
            f"[DouYinCookieManager._auto_refresh_loop] 启动 Cookie 自动刷新任务，间隔 {self.refresh_interval}s"
        )
        while True:
            try:
                await asyncio.sleep(self.refresh_interval)
                cookie_str, cookie_dict = await self.refresh_cookies()
                # 更新客户端的 Cookie
                dy_client.headers["Cookie"] = cookie_str
                dy_client.cookie_dict = cookie_dict
                utils.logger.debug(
                    "[DouYinCookieManager._auto_refresh_loop] 客户端 Cookie 已同步"
                )
            except asyncio.CancelledError:
                utils.logger.info("[DouYinCookieManager._auto_refresh_loop] 自动刷新任务已取消")
                break
            except Exception as e:
                utils.logger.error(
                    f"[DouYinCookieManager._auto_refresh_loop] 刷新 Cookie 异常: {e}"
                )
                # 出错后等待一段时间再重试，避免疯狂打日志
                await asyncio.sleep(5)

    def start_auto_refresh(self, dy_client) -> None:
        """
        启动后台自动刷新任务。
        Args:
            dy_client: DouYinClient 实例
        """
        if self._refresh_task is not None and not self._refresh_task.done():
            utils.logger.warning("[DouYinCookieManager.start_auto_refresh] 自动刷新任务已在运行，跳过重复启动")
            return
        self._refresh_task = asyncio.create_task(self._auto_refresh_loop(dy_client))

    async def stop_auto_refresh(self) -> None:
        """停止后台自动刷新任务，并做最后一次持久化"""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        # 停止时做最后一次保存
        await self.save_cookies_to_file()
        utils.logger.info("[DouYinCookieManager.stop_auto_refresh] 自动刷新已停止，Cookie 已最终持久化")
