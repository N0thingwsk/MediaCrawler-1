# -*- coding: utf-8 -*-
# @Time    : 2025/9/5 19:34
# @Desc    : Weibo storage implementation class - MySQL only
from typing import Dict

from sqlalchemy import select

from base.base_crawler import AbstractStore
from database.models import WeiboCreator, WeiboNote, WeiboNoteComment
from tools import utils
from database.db_session import get_session


class WeiboDbStoreImplement(AbstractStore):

    async def store_content(self, content_item: Dict):
        """
        Weibo content DB storage implementation
        Args:
            content_item: content item dict

        Returns:

        """
        note_id = int(content_item.get("note_id"))
        content_item["note_id"] = note_id
        async with get_session() as session:
            stmt = select(WeiboNote).where(WeiboNote.note_id == note_id)
            res = await session.execute(stmt)
            db_note = res.scalar_one_or_none()
            if db_note:
                db_note.last_modify_ts = utils.get_current_timestamp()
                for key, value in content_item.items():
                    if hasattr(db_note, key):
                        setattr(db_note, key, value)
            else:
                content_item["add_ts"] = utils.get_current_timestamp()
                content_item["last_modify_ts"] = utils.get_current_timestamp()
                db_note = WeiboNote(**content_item)
                session.add(db_note)
            await session.commit()

    async def store_comment(self, comment_item: Dict):
        """
        Weibo content DB storage implementation
        Args:
            comment_item: comment item dict

        Returns:

        """
        comment_id = int(comment_item.get("comment_id"))
        comment_item["comment_id"] = comment_id
        comment_item["note_id"] = int(comment_item.get("note_id", 0) or 0)
        comment_item["create_time"] = int(comment_item.get("create_time", 0) or 0)
        comment_item["comment_like_count"] = str(comment_item.get("comment_like_count", "0"))
        comment_item["sub_comment_count"] = str(comment_item.get("sub_comment_count", "0"))
        comment_item["parent_comment_id"] = str(comment_item.get("parent_comment_id", "0"))

        async with get_session() as session:
            stmt = select(WeiboNoteComment).where(WeiboNoteComment.comment_id == comment_id)
            res = await session.execute(stmt)
            db_comment = res.scalar_one_or_none()
            if db_comment:
                db_comment.last_modify_ts = utils.get_current_timestamp()
                for key, value in comment_item.items():
                    if hasattr(db_comment, key):
                        setattr(db_comment, key, value)
            else:
                comment_item["add_ts"] = utils.get_current_timestamp()
                comment_item["last_modify_ts"] = utils.get_current_timestamp()
                db_comment = WeiboNoteComment(**comment_item)
                session.add(db_comment)
            await session.commit()

    async def store_creator(self, creator: Dict):
        """
        Weibo creator DB storage implementation
        Args:
            creator:

        Returns:

        """
        user_id = int(creator.get("user_id"))
        creator["user_id"] = user_id
        async with get_session() as session:
            stmt = select(WeiboCreator).where(WeiboCreator.user_id == user_id)
            res = await session.execute(stmt)
            db_creator = res.scalar_one_or_none()
            if db_creator:
                db_creator.last_modify_ts = utils.get_current_timestamp()
                for key, value in creator.items():
                    if hasattr(db_creator, key):
                        setattr(db_creator, key, value)
            else:
                creator["add_ts"] = utils.get_current_timestamp()
                creator["last_modify_ts"] = utils.get_current_timestamp()
                db_creator = WeiboCreator(**creator)
                session.add(db_creator)
            await session.commit()