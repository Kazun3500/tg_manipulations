--1) топ по количеству сообщений, реакций
with users_data as (
SELECT u.id, u.computed_name,
count(r2.id) as reactions_from_user,
count(cm.id) as active_now
FROM user u
LEFT JOIN reaction r2 on r2.user_id=u.id
LEFT JOIN channel_members cm on cm.user_id=u.id
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
 u.reactions_from_user as "Количество реакций",
 u.reaction_to as "Реакцию ставят на сообщения пользователя",
 u.reaction_to_count as "Количество",
 u.reaction_from as "Пользователь ставит реакцию другим",
 u.reaction_from_count as "Количество"
from user_stats u
LEFT JOIN message m on m.user_id=u.id
LEFT JOIN reaction r on r.message_id=m.id
GROUP BY u.computed_name

-- статистика по реакциям
;
select m.message, m.id, u.computed_name, count(r.id)
from message m
inner join main.reaction r on m.id = r.message_id
inner join main.user u on u.id = m.user_id
group by m.message, m.id
order by count(r.id) desc
;

select m.message, m.id,r.emoji, count(r.id)
from message m
inner join main.reaction r on m.id = r.message_id
group by m.message, m.id, r.emoji
order by count(r.id) desc

;
-- топ сообщений в час по пользователям

WITH RECURSIVE
  cnt(x) AS (
     SELECT 0
     UNION ALL
     SELECT x+1 FROM cnt
      LIMIT 24
  )
select computed_name, hour,max(cnt), date
from (
SELECT u.computed_name , x as hour, count(m.id) as cnt, date(m.date) as date
FROM cnt
inner join message m on cast(strftime('%H', m.date) as real)=cnt.x
INNER  join "user" u on u.id =m.user_id
INNER join channel_members cm on cm.user_id =u.id
group by u.id, x, date(m.date)
ORDER by count(m.id) desc
)
group by computed_name

;
-- просто том сообщений в час

WITH RECURSIVE
  cnt(x) AS (
     SELECT 0
     UNION ALL
     SELECT x+1 FROM cnt
      LIMIT 24
  )
SELECT x, count(m.id), date(m.date)
FROM cnt
inner join message m on cast(strftime('%H', m.date) as real)=cnt.x
group by x, date(m.date)
HAVING  count(m.id)>100
ORDER by count(m.id) desc
;
--- сообщений по часам


WITH RECURSIVE
  cnt(x) AS (
     SELECT 0
     UNION ALL
     SELECT x+1 FROM cnt
      LIMIT 24
  ),
    daily as (
        SELECT
            strftime('%d.%m.%Y', m.date) as date,
            strftime('%H:00', m.date) as time,
            count(m.id) as cnt
FROM cnt
inner join message m on cast(strftime('%H', m.date) as real)=cnt.x
group by strftime('%d.%m.%Y', m.date),strftime('%H:00', m.date)
    )
select
        distinct
       time,
       avg(cnt) over (partition by time),
       max(cnt) over (partition by time),
       min(cnt) over (partition by time),
       first_value(date) over (partition by time order by cnt desc),
       first_value(date) over (partition by time order by cnt)
from daily

;
-- кто пишет по часам

WITH RECURSIVE
  cnt(x) AS (
     SELECT 0
     UNION ALL
     SELECT x+1 FROM cnt
      LIMIT 24
  ),
    daily as (
        SELECT
            strftime('%d.%m.%Y', m.date) as date,
            strftime('%H:00', m.date) as time,
            u.computed_name,
            count(m.id) as cnt
FROM cnt
inner join message m on cast(strftime('%H', m.date) as real)=cnt.x
inner join main.user u on u.id = m.user_id
group by strftime('%d.%m.%Y', m.date),strftime('%H:00', m.date), u.computed_name
    ),
    for_avg as (
        select distinct computed_name, time, cast((sum(cnt) over (partition by computed_name, time)) as real)/(sum(cnt) over (partition by time)) as percent
        from daily
    )
select
    distinct
    d.*,
    first_value(fa.computed_name) over (partition by d.time order by fa.percent desc )
        from (
            select distinct
    d.time,
    first_value(d.computed_name) over (partition by d.time order by cnt desc ) as max_messages,
    first_value(d.computed_name) over (partition by d.time order by cnt ) as min_messages
from daily d
             ) as d
inner join for_avg fa on fa.time=d.time
