from jinja2 import Environment, PackageLoader, select_autoescape, FileSystemLoader
import asyncio
import logging

from sqlalchemy import select, func, delete
from sqlalchemy.sql import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine


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

DB_URL = "sqlite+aiosqlite:///database.db"
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
 u.reactions_from_user as "Количество реакций от пользователя",
 u.reaction_to as "Реакцию ставят на сообщения пользователя",
 u.reaction_to_count as "Количество",
 u.reaction_from as "Пользователь ставит реакцию другим",
 u.reaction_from_count as "Количество"
from user_stats u
LEFT JOIN message m on m.user_id=u.id
LEFT JOIN reaction r on r.message_id=m.id
GROUP BY u.computed_name
order by Count(m.id) desc 
"""


async def main():
    engine = create_async_engine(DB_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:

        data = await session.execute(text(TOTAL_STATS_STATEMENT))

        template = env.get_template("report.html")
        with open("rendered.html", 'w') as res:
            res.write(template.render(base_stats=list(data.mappings().all()[:30])))

    await engine.dispose()    
    

asyncio.run(main())