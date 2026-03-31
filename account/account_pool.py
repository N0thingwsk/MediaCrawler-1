# -*- coding: utf-8 -*-
"""
多账号管理器

功能：
1. 管理多个 Cookie 账号，支持轮换爬取
2. 每个账号可绑定独立的代理 IP，防止平台关联
3. 追踪每个账号的使用状态（正常/失效/被限流）
4. 提供简洁的接口，与现有爬虫架构无缝集成
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict

from proxy.proxy_ip_pool import ProxyIpPool, create_ip_pool
from proxy.types import IpInfoModel
from tools import utils


class AccountStatus(str, Enum):
    """账号状态枚举"""
    ACTIVE = "active"          # 正常可用
    RATE_LIMITED = "rate_limited"  # 被限流
    EXPIRED = "expired"        # Cookie 已过期
    BANNED = "banned"          # 被封禁


@dataclass
class AccountInfo:
    """单个账号信息"""
    index: int                          # 账号索引（从1开始）
    cookie_str: str                     # Cookie 字符串
    status: AccountStatus = AccountStatus.ACTIVE  # 账号状态
    proxy: Optional[IpInfoModel] = None  # 绑定的代理 IP
    last_used_time: float = 0.0         # 上次使用时间戳
    total_requests: int = 0             # 总请求数
    failed_requests: int = 0            # 失败请求数
    error_message: str = ""             # 最近的错误信息

    @property
    def name(self) -> str:
        """账号显示名称"""
        return f"账号#{self.index}"

    def mark_used(self) -> None:
        """标记为已使用"""
        self.last_used_time = time.time()
        self.total_requests += 1

    def mark_failed(self, error: str = "") -> None:
        """标记请求失败"""
        self.failed_requests += 1
        self.error_message = error

    def mark_expired(self) -> None:
        """标记为 Cookie 过期"""
        self.status = AccountStatus.EXPIRED
        utils.logger.warning(f"[AccountPool] {self.name} Cookie 已过期，标记为不可用")

    def mark_rate_limited(self) -> None:
        """标记为被限流"""
        self.status = AccountStatus.RATE_LIMITED
        utils.logger.warning(f"[AccountPool] {self.name} 被限流，暂时跳过")

    def is_available(self) -> bool:
        """是否可用"""
        return self.status == AccountStatus.ACTIVE


class AccountPool:
    """
    多账号管理池

    使用方式：
        pool = AccountPool(cookies_list=["cookie1", "cookie2"])
        await pool.init_proxies(ip_pool_count=2)  # 可选：为每个账号分配代理

        for account in pool:
            # 使用 account.cookie_str 和 account.proxy 进行爬取
            ...
    """

    def __init__(self, cookies_list: List[str]) -> None:
        """
        初始化账号池

        Args:
            cookies_list: Cookie 字符串列表
        """
        self.accounts: List[AccountInfo] = []
        self._current_index: int = 0

        for i, cookie_str in enumerate(cookies_list):
            cookie_str = cookie_str.strip()
            if not cookie_str:
                utils.logger.warning(f"[AccountPool] 第 {i + 1} 个 Cookie 为空，已跳过")
                continue
            self.accounts.append(AccountInfo(index=i + 1, cookie_str=cookie_str))

        if not self.accounts:
            raise ValueError("[AccountPool] 没有有效的 Cookie 账号，请检查 COOKIES_LIST 配置")

        utils.logger.info(f"[AccountPool] 已加载 {len(self.accounts)} 个账号")

    @property
    def total_count(self) -> int:
        """总账号数"""
        return len(self.accounts)

    @property
    def active_count(self) -> int:
        """可用账号数"""
        return sum(1 for a in self.accounts if a.is_available())

    async def init_proxies(self, ip_pool_count: int = 2, enable_validate: bool = True) -> None:
        """
        为每个账号分配独立的代理 IP

        Args:
            ip_pool_count: 代理池大小
            enable_validate: 是否验证代理可用性
        """
        utils.logger.info(f"[AccountPool] 开始为 {self.total_count} 个账号分配独立代理...")

        ip_pool = await create_ip_pool(
            ip_pool_count=max(ip_pool_count, self.total_count),
            enable_validate_ip=enable_validate,
        )

        for account in self.accounts:
            try:
                proxy = await ip_pool.get_proxy()
                account.proxy = proxy
                utils.logger.info(
                    f"[AccountPool] {account.name} 已绑定代理: {proxy.ip}:{proxy.port}"
                )
            except Exception as e:
                utils.logger.warning(
                    f"[AccountPool] {account.name} 分配代理失败: {e}，将不使用代理"
                )

    def get_next_account(self) -> Optional[AccountInfo]:
        """
        获取下一个可用账号（轮换策略）

        Returns:
            AccountInfo 或 None（所有账号不可用时）
        """
        if not self.accounts:
            return None

        # 尝试找到下一个可用账号
        checked = 0
        while checked < self.total_count:
            account = self.accounts[self._current_index % self.total_count]
            self._current_index += 1
            checked += 1

            if account.is_available():
                return account

        utils.logger.error("[AccountPool] 所有账号均不可用！")
        return None

    def get_available_accounts(self) -> List[AccountInfo]:
        """获取所有可用账号"""
        return [a for a in self.accounts if a.is_available()]

    def get_proxy_formats(self, account: AccountInfo) -> Tuple[Optional[Dict], Optional[str]]:
        """
        获取账号绑定的代理格式（playwright 格式 和 httpx 格式）

        Args:
            account: 账号信息

        Returns:
            (playwright_proxy_format, httpx_proxy_format)
        """
        if account.proxy is None:
            return None, None
        return utils.format_proxy_info(account.proxy)

    def print_summary(self) -> None:
        """打印账号池状态摘要"""
        utils.logger.info("=" * 60)
        utils.logger.info(f"[AccountPool] 账号池状态摘要")
        utils.logger.info(f"  总账号数: {self.total_count}")
        utils.logger.info(f"  可用账号: {self.active_count}")

        for account in self.accounts:
            proxy_info = f"{account.proxy.ip}:{account.proxy.port}" if account.proxy else "无"
            utils.logger.info(
                f"  {account.name}: 状态={account.status.value}, "
                f"代理={proxy_info}, "
                f"请求数={account.total_requests}, "
                f"失败数={account.failed_requests}"
            )
        utils.logger.info("=" * 60)

    def __iter__(self):
        """迭代所有可用账号"""
        return iter(self.get_available_accounts())

    def __len__(self) -> int:
        return self.total_count
