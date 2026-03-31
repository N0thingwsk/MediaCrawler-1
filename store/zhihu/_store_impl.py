# -*- coding: utf-8 -*-
# @Time    : 2025/9/5 19:34
# @Desc    : Zhihu storage implementation class - MySQL only
from typing import Dict

from sqlalchemy import select

from base.base_crawler import AbstractStore
from database.db_session import get_session
from database.models import ZhihuContent, ZhihuComment, ZhihuCreator
from tools import utils


class ZhihuDbStoreImplement(AbstractStore):
    async def store_content(self, content_item: Dict):
        """
        Zhihu content DB storage implementation
        Args:
            content_item: content item dict
        """
        content_id = content_item.get("content_id")
        async with get_session() as session:
            stmt = select(ZhihuContent).where(ZhihuContent.content_id == content_id)
            result = await session.execute(stmt)
            existing_content = result.scalars().first()
            if existing_content:
                for key, value in content_item.items():
                    if hasattr(existing_content, key):
                        setattr(existing_content, key, value)
            else:
                if "add_ts" not in content_item:
                    content_item["add_ts"] = utils.get_current_timestamp()
                new_content = ZhihuContent(**content_item)
                session.add(new_content)
            await session.commit()

    async def store_comment(self, comment_item: Dict):
        """
        Zhihu content DB storage implementation
        Args:
            comment_item: comment item dict
        """
        comment_id = comment_item.get("comment_id")
        async with get_session() as session:
            stmt = select(ZhihuComment).where(ZhihuComment.comment_id == comment_id)
            result = await session.execute(stmt)
            existing_comment = result.scalars().first()
            if existing_comment:
                for key, value in comment_item.items():
                    if hasattr(existing_comment, key):
                        setattr(existing_comment, key, value)
            else:
                if "add_ts" not in comment_item:
                    comment_item["add_ts"] = utils.get_current_timestamp()
                new_comment = ZhihuComment(**comment_item)
                session.add(new_comment)
            await session.commit()

    async def store_creator(self, creator: Dict):
        """
        Zhihu content DB storage implementation
        Args:
            creator: creator dict
        """
        user_id = creator.get("user_id")
        async with get_session() as session:
            stmt = select(ZhihuCreator).where(ZhihuCreator.user_id == user_id)
            result = await session.execute(stmt)
            existing_creator = result.scalars().first()
            if existing_creator:
                for key, value in creator.items():
                    if hasattr(existing_creator, key):
                        setattr(existing_creator, key, value)
            else:
                if "add_ts" not in creator:
                    creator["add_ts"] = utils.get_current_timestamp()
                new_creator = ZhihuCreator(**creator)
                session.add(new_creator)
            await session.commit()