# -*- coding: utf-8 -*-
# @Time    : 2025/9/5 19:34
# @Desc    : Tieba storage implementation class - MySQL only
from typing import Dict

from sqlalchemy import select

from base.base_crawler import AbstractStore
from database.models import TiebaNote, TiebaComment, TiebaCreator
from tools import utils
from database.db_session import get_session


class TieBaDbStoreImplement(AbstractStore):
    async def store_content(self, content_item: Dict):
        """
        tieba content DB storage implementation
        Args:
            content_item: content item dict
        """
        note_id = content_item.get("note_id")
        async with get_session() as session:
            stmt = select(TiebaNote).where(TiebaNote.note_id == note_id)
            res = await session.execute(stmt)
            db_note = res.scalar_one_or_none()
            if db_note:
                for key, value in content_item.items():
                    setattr(db_note, key, value)
            else:
                db_note = TiebaNote(**content_item)
                session.add(db_note)
            await session.commit()

    async def store_comment(self, comment_item: Dict):
        """
        tieba content DB storage implementation
        Args:
            comment_item: comment item dict
        """
        comment_id = comment_item.get("comment_id")
        async with get_session() as session:
            stmt = select(TiebaComment).where(TiebaComment.comment_id == comment_id)
            res = await session.execute(stmt)
            db_comment = res.scalar_one_or_none()
            if db_comment:
                for key, value in comment_item.items():
                    setattr(db_comment, key, value)
            else:
                db_comment = TiebaComment(**comment_item)
                session.add(db_comment)
            await session.commit()

    async def store_creator(self, creator: Dict):
        """
        tieba content DB storage implementation
        Args:
            creator: creator dict
        """
        user_id = creator.get("user_id")
        async with get_session() as session:
            stmt = select(TiebaCreator).where(TiebaCreator.user_id == user_id)
            res = await session.execute(stmt)
            db_creator = res.scalar_one_or_none()
            if db_creator:
                for key, value in creator.items():
                    setattr(db_creator, key, value)
            else:
                db_creator = TiebaCreator(**creator)
                session.add(db_creator)
            await session.commit()