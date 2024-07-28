import base64
import io

from jinja2 import Environment, PackageLoader, select_autoescape, FileSystemLoader
import asyncio
import logging

from sqlalchemy import select, func, delete
from sqlalchemy.sql import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from telethon import TelegramClient
from telethon.tl.types import Message

"""
1) топ по количеству сообщений, реакций
2) Реакций пользователю / реакций от пользователя. Только топ 1 любиых для каждого
3) топ за час (реакций, сообщений)
4) самый болтливый день
5) топ медиаа сообщений и лайков за них
6) самая популярная реакция по часам
7) В среднем кто из пользователей в чате пишет по часам топ 5
8) самое залайканное сообщение (в общем и отдельно по реакциям)
9) топ по необычным реакциям
"""

api_id = 17684030
api_hash = '9ef7b66a557c7166b9a07dddc7ec7c68'
DB_URL = "sqlite+aiosqlite:///database.db"
chat_id = 1897675404

env = Environment(
    loader=FileSystemLoader("."),
    autoescape=select_autoescape()
)

TOTAL_STATS_STATEMENT = """
with users_data as (
SELECT u.id, u.computed_name,
count(r2.id) as reactions_from_user,
count(cm.id) as active_now
FROM user u
LEFT JOIN reaction r2 on r2.user_id=u.id
inner JOIN channel_members cm on cm.user_id=u.id
GROUP BY u.id, u.computed_name
),
reactions_from_user as (
    select r.user_id, r.emoji, count(r.id) as cnt
    FROM reaction r
    GROUP BY r.user_id, r.emoji
),
reactions_for_user as (
    select m.user_id, r.emoji, count(r.id) as cnt
    FROM reaction r
    INNER JOIN message m on m.id=r.message_id
    GROUP BY m.user_id, r.emoji
),
user_stats as (
select DISTINCT u.id, u.computed_name,
u.reactions_from_user, u.active_now,
first_value(rfu.emoji) over (PARTITION BY u.id ORDER BY rfu.cnt desc) as reaction_to,
first_value(rfu.cnt) over (PARTITION BY u.id ORDER BY rfu.cnt desc) as reaction_to_count,
 first_value(rfru.emoji) over (PARTITION BY u.id ORDER BY rfru.cnt desc) as reaction_from,
 first_value(rfru.cnt) over (PARTITION BY u.id ORDER BY rfru.cnt desc) as reaction_from_count
FROM users_data u
LEFT JOIN reactions_for_user rfu on rfu.user_id=u.id
LEFT JOIN reactions_from_user rfru on rfru.user_id=u.id
)
select
u.computed_name as "Имя пользователя",
min(m.date) as "Дата первого собщения",
max(m.date) as "Дата последнего сообщения",
 Count(m.id) as "Количество сообщений",
 count(r.id) as "Количестов реакций",
 cast(count(r.id) as REAL)/Count(m.id) as "Полезность сообщений (количество реакций/количество сообщений)",
 u.reactions_from_user as "Количество реакций от пользователя"
 --,
 --u.reaction_to as "Реакцию ставят на сообщения пользователя",
 --u.reaction_to_count as "Количество",
 --u.reaction_from as "Пользователь ставит реакцию другим",
 --u.reaction_from_count as "Количество"
from user_stats u
LEFT JOIN message m on m.user_id=u.id
LEFT JOIN reaction r on r.message_id=m.id
GROUP BY u.computed_name
order by Count(m.id) desc 
"""


async def get_common_stats(session: AsyncSession):
    data = await session.execute(text(TOTAL_STATS_STATEMENT))
    return list(data.mappings().all()[:30])


async def top_messages(session: AsyncSession, client: TelegramClient):
    stmt = text("""with base as (
    select m.message, m.id, u.computed_name, count(r.id) as cnt, r.emoji, r.custom_document_id
    from message m
    inner join main.reaction r on m.id = r.message_id
    inner join main.user u on u.id = m.user_id
    group by m.message, m.id, r.emoji, r.custom_document_id
    order by count(r.id) desc
)
select message, 
id, 
computed_name, 
sum(cnt), 
string_agg(coalesce(emoji, custom_document_id) || ' ' || cnt, ',')
from base
group by message, id, computed_name
order by sum(cnt) desc
limit 30""")

    i = 1
    result = []
    for item in await session.execute(stmt):
        message_text, message_id, username, count, text_stats = item
        tmp = {
            'message': message_text,
            'id': message_id,
            'username': username,
            'count': count,
            'text_stats': text_stats,
            'link': f'https://t.me/c/{chat_id}/{message_id}',
            'deleted': False
        }
        message: Message = await client.get_messages(chat_id, ids=item[1])
        if message is None:
            tmp['deleted'] = True

        else:

            if message.media:
                try:
                    file = io.BytesIO()
                    await client.download_media(message, file)
                    file.seek(0)
                    tmp['media'] = base64.b64encode(file.read()).decode()

                except:
                    tmp['media_missing'] = "Картинка с сообщения не загружена"
        result.append(tmp)
    return result


async def main():
    engine = create_async_engine(DB_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session, TelegramClient('session_name', api_id, api_hash) as client:

        common_stats = await get_common_stats(session)
        top_list = await top_messages(session, client)
        template = env.get_template("report.html")
        with open("rendered.html", 'w') as res:
            res.write(template.render(base_stats=common_stats, top_list=top_list))

    await engine.dispose()    
    

asyncio.run(main())