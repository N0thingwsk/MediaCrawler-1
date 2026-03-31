# -*- coding: utf-8 -*-
# @Time    : 2025/9/5 19:34
# @Desc    : Kuaishou storage implementation class - MySQL only
from typing import Dict

from sqlalchemy import select

from base.base_crawler import AbstractStore
from database.db_session import get_session
from database.models import KuaishouVideo, KuaishouVideoComment
from tools import utils


class KuaishouDbStoreImplement(AbstractStore):
    async def store_creator(self, creator: Dict):
        pass

    async def store_content(self, content_item: Dict):
        """
        Kuaishou content DB storage implementation
        Args:
            content_item: content item dict
        """
        video_id = content_item.get("video_id")
        async with get_session() as session:
            result = await session.execute(select(KuaishouVideo).where(KuaishouVideo.video_id == video_id))
            video_detail = result.scalar_one_or_none()

            if not video_detail:
                content_item["add_ts"] = utils.get_current_timestamp()
                new_content = KuaishouVideo(**content_item)
                session.add(new_content)
            else:
                for key, value in content_item.items():
                    if hasattr(video_detail, key):
                        setattr(video_detail, key, value)
            await session.commit()

    async def store_comment(self, comment_item: Dict):
        """
        Kuaishou comment DB storage implementation
        Args:
            comment_item: comment item dict
        """
        comment_id = comment_item.get("comment_id")
        async with get_session() as session:
            result = await session.execute(
                select(KuaishouVideoComment).where(KuaishouVideoComment.comment_id == comment_id))
            comment_detail = result.scalar_one_or_none()

            if not comment_detail:
                comment_item["add_ts"] = utils.get_current_timestamp()
                new_comment = KuaishouVideoComment(**comment_item)
                session.add(new_comment)
            else:
                for key, value in comment_item.items():
                    if hasattr(comment_detail, key):
                        setattr(comment_detail, key, value)
            await session.commit()