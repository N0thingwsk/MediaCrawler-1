# -*- coding: utf-8 -*-
"""
stealth.min.js 自动更新工具

功能：
1. 启动时自动检查 stealth.min.js 是否需要更新（基于文件年龄）
2. 从 GitHub 下载最新版本的 stealth evasions 脚本
3. 更新前自动备份旧版本，更新失败自动回滚
4. 支持手动触发更新

来源仓库：https://github.com/nicedoc/puppeteer-extra-plugin-stealth-evasions
备用来源：https://github.com/nicedoc/nicedoc.io 的 CDN
"""

import hashlib
import os
import re
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from tools.utils import logger

# stealth.min.js 文件路径（相对于项目根目录）
STEALTH_JS_PATH = "libs/stealth.min.js"
STEALTH_JS_BACKUP_PATH = "libs/stealth.min.js.bak"

# GitHub 下载源列表（按优先级排序，第一个失败会尝试下一个）
DOWNLOAD_SOURCES = [
    # puppeteer-extra-plugin-stealth-evasions 仓库的最新构建产物
    "https://raw.githubusercontent.com/nicedoc/puppeteer-extra-plugin-stealth-evasions/master/stealth.min.js",
    # 备用：requireCDN 镜像
    "https://cdn.jsdelivr.net/gh/nicedoc/puppeteer-extra-plugin-stealth-evasions@master/stealth.min.js",
]

# 文件头部特征，用于验证下载的文件是否为合法的 stealth.min.js
STEALTH_JS_SIGNATURE = "extract-stealth-evasions"

# 最小合法文件大小（字节），防止下载到空文件或错误页面
MIN_VALID_FILE_SIZE = 50 * 1024  # 50KB


def _get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).parent.parent


def _get_stealth_path() -> Path:
    """获取 stealth.min.js 的绝对路径"""
    return _get_project_root() / STEALTH_JS_PATH


def _get_backup_path() -> Path:
    """获取备份文件的绝对路径"""
    return _get_project_root() / STEALTH_JS_BACKUP_PATH


def _get_file_md5(filepath: Path) -> str:
    """计算文件 MD5"""
    md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def _parse_generated_date(filepath: Path) -> Optional[datetime]:
    """
    从 stealth.min.js 文件头部解析生成日期。
    文件头部格式示例：
        * Generated on: Mon, 05 Jun 2023 06:17:57 GMT
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            # 只读前 500 字符，日期信息在文件头部
            header = f.read(500)

        match = re.search(r"Generated on:\s*(.+?)(?:\n|\r)", header)
        if match:
            date_str = match.group(1).strip()
            # 解析 RFC 2822 格式日期
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
    except Exception as e:
        logger.debug(f"[StealthUpdater] 解析生成日期失败: {e}")

    return None


def _get_file_age_days(filepath: Path) -> int:
    """获取文件的年龄（天数），优先使用文件头部的生成日期"""
    # 优先从文件内容解析生成日期
    generated_date = _parse_generated_date(filepath)
    if generated_date:
        age = (datetime.now(generated_date.tzinfo) - generated_date).days
        return max(age, 0)

    # 回退：使用文件修改时间
    mtime = os.path.getmtime(filepath)
    age = (time.time() - mtime) / 86400
    return int(age)


def _validate_stealth_js(filepath: Path) -> bool:
    """
    验证下载的文件是否为合法的 stealth.min.js。
    检查项：
    1. 文件大小 >= 50KB
    2. 文件头部包含特征字符串
    3. 文件内容是合法的 JavaScript（不是 HTML 错误页面）
    """
    try:
        # 检查文件大小
        file_size = filepath.stat().st_size
        if file_size < MIN_VALID_FILE_SIZE:
            logger.warning(
                f"[StealthUpdater] 文件大小异常: {file_size} bytes (最小要求 {MIN_VALID_FILE_SIZE} bytes)"
            )
            return False

        # 检查文件内容特征
        with open(filepath, "r", encoding="utf-8") as f:
            header = f.read(1000)

        # 必须包含 stealth evasions 特征
        if STEALTH_JS_SIGNATURE not in header:
            logger.warning("[StealthUpdater] 文件缺少 stealth evasions 特征签名")
            return False

        # 不能是 HTML 页面（GitHub 404 等）
        if "<html" in header.lower() or "<!doctype" in header.lower():
            logger.warning("[StealthUpdater] 下载到的是 HTML 页面，非 JS 文件")
            return False

        return True

    except Exception as e:
        logger.warning(f"[StealthUpdater] 文件验证失败: {e}")
        return False


def _download_file(url: str, dest: Path, timeout: int = 30) -> bool:
    """
    从指定 URL 下载文件到目标路径。
    使用 urllib 避免额外依赖。
    """
    import urllib.request
    import urllib.error

    try:
        logger.info(f"[StealthUpdater] 正在从 {url} 下载...")

        # 设置请求头，模拟浏览器访问
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
        })

        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                logger.warning(f"[StealthUpdater] HTTP 状态码: {response.status}")
                return False

            content = response.read()

            # 写入临时文件
            temp_path = dest.with_suffix(".tmp")
            with open(temp_path, "wb") as f:
                f.write(content)

            # 验证临时文件
            if not _validate_stealth_js(temp_path):
                temp_path.unlink(missing_ok=True)
                return False

            # 验证通过，移动到目标路径
            shutil.move(str(temp_path), str(dest))
            logger.info(
                f"[StealthUpdater] 下载成功: {len(content)} bytes -> {dest}"
            )
            return True

    except urllib.error.URLError as e:
        logger.warning(f"[StealthUpdater] 网络请求失败: {e}")
    except Exception as e:
        logger.warning(f"[StealthUpdater] 下载异常: {e}")

    # 清理临时文件
    temp_path = dest.with_suffix(".tmp")
    if temp_path.exists():
        temp_path.unlink(missing_ok=True)

    return False


def _backup_current(stealth_path: Path) -> bool:
    """备份当前的 stealth.min.js"""
    backup_path = _get_backup_path()
    try:
        shutil.copy2(str(stealth_path), str(backup_path))
        logger.info(f"[StealthUpdater] 已备份当前版本 -> {backup_path.name}")
        return True
    except Exception as e:
        logger.error(f"[StealthUpdater] 备份失败: {e}")
        return False


def _rollback(stealth_path: Path) -> bool:
    """从备份恢复 stealth.min.js"""
    backup_path = _get_backup_path()
    if not backup_path.exists():
        logger.error("[StealthUpdater] 备份文件不存在，无法回滚")
        return False
    try:
        shutil.copy2(str(backup_path), str(stealth_path))
        logger.info("[StealthUpdater] 已从备份恢复旧版本")
        return True
    except Exception as e:
        logger.error(f"[StealthUpdater] 回滚失败: {e}")
        return False


def get_stealth_info() -> dict:
    """
    获取当前 stealth.min.js 的信息。

    Returns:
        包含文件信息的字典：
        - exists: 文件是否存在
        - path: 文件路径
        - size: 文件大小（字节）
        - age_days: 文件年龄（天）
        - generated_date: 生成日期字符串
        - md5: 文件 MD5
    """
    stealth_path = _get_stealth_path()
    info = {
        "exists": stealth_path.exists(),
        "path": str(stealth_path),
    }

    if not info["exists"]:
        return info

    info["size"] = stealth_path.stat().st_size
    info["age_days"] = _get_file_age_days(stealth_path)
    info["md5"] = _get_file_md5(stealth_path)

    generated_date = _parse_generated_date(stealth_path)
    if generated_date:
        info["generated_date"] = generated_date.strftime("%Y-%m-%d %H:%M:%S")

    return info


def update_stealth_js(force: bool = False) -> Tuple[bool, str]:
    """
    更新 stealth.min.js 到最新版本。

    Args:
        force: 是否强制更新（忽略文件年龄检查）

    Returns:
        (是否更新成功, 描述信息)
    """
    stealth_path = _get_stealth_path()

    # 如果文件不存在，直接下载
    if not stealth_path.exists():
        logger.info("[StealthUpdater] stealth.min.js 不存在，开始下载...")
        for url in DOWNLOAD_SOURCES:
            if _download_file(url, stealth_path):
                return True, "stealth.min.js 下载成功（首次安装）"
        return False, "所有下载源均失败，请检查网络连接"

    # 备份当前版本
    old_md5 = _get_file_md5(stealth_path)
    if not _backup_current(stealth_path):
        return False, "备份当前版本失败，取消更新"

    # 尝试从多个源下载
    for url in DOWNLOAD_SOURCES:
        if _download_file(url, stealth_path):
            new_md5 = _get_file_md5(stealth_path)

            if new_md5 == old_md5:
                logger.info("[StealthUpdater] 下载的版本与当前版本相同，无需更新")
                return True, "已是最新版本，无需更新"

            # 解析新版本的生成日期
            new_date = _parse_generated_date(stealth_path)
            date_str = new_date.strftime("%Y-%m-%d") if new_date else "未知"

            logger.info(
                f"[StealthUpdater] ✅ 更新成功！"
                f"新版本生成日期: {date_str} | "
                f"MD5: {old_md5[:8]}... -> {new_md5[:8]}..."
            )
            return True, f"更新成功，新版本日期: {date_str}"

    # 所有源都失败，回滚
    logger.warning("[StealthUpdater] 所有下载源均失败，正在回滚...")
    _rollback(stealth_path)
    return False, "所有下载源均失败，已回滚到旧版本"


def check_and_update(max_age_days: int = 30) -> None:
    """
    检查 stealth.min.js 是否需要更新，如果超过指定天数则自动更新。
    此函数设计为在爬虫启动时调用，不会因更新失败而阻断主流程。

    Args:
        max_age_days: 最大允许的文件年龄（天），超过则触发更新
    """
    try:
        stealth_path = _get_stealth_path()

        # 文件不存在，必须下载
        if not stealth_path.exists():
            logger.warning("[StealthUpdater] stealth.min.js 不存在！正在下载...")
            success, msg = update_stealth_js()
            if not success:
                logger.error(f"[StealthUpdater] {msg}")
            return

        # 检查文件年龄
        age_days = _get_file_age_days(stealth_path)
        generated_date = _parse_generated_date(stealth_path)
        date_str = generated_date.strftime("%Y-%m-%d") if generated_date else "未知"

        if age_days <= max_age_days:
            logger.info(
                f"[StealthUpdater] stealth.min.js 版本检查通过 | "
                f"生成日期: {date_str} | 年龄: {age_days} 天 | "
                f"阈值: {max_age_days} 天"
            )
            return

        # 超过阈值，触发更新
        logger.info(
            f"[StealthUpdater] stealth.min.js 已过期 | "
            f"生成日期: {date_str} | 年龄: {age_days} 天 (超过 {max_age_days} 天阈值) | "
            f"正在自动更新..."
        )
        success, msg = update_stealth_js()
        if success:
            logger.info(f"[StealthUpdater] {msg}")
        else:
            logger.warning(
                f"[StealthUpdater] 自动更新失败: {msg} | "
                f"将继续使用当前版本（不影响爬虫运行）"
            )

    except Exception as e:
        # 任何异常都不应阻断主流程
        logger.warning(f"[StealthUpdater] 版本检查异常: {e}（不影响爬虫运行）")
