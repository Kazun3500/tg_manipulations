import asyncio
import datetime
import io
import json
import logging

from textwrap import indent

from openpyxl.workbook import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate
from sqlalchemy import select, func, delete, desc, text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql.functions import count
from telethon.tl.functions.messages import GetMessageReactionsListRequest, GetRepliesRequest
from telethon.tl.types import PeerUser
from telethon.tl.types.messages import MessageReactionsList

from models import User as UserModel, Channel as ChannelModel, Message as MessageModel, Reaction, ChannelMembers
from telethon import TelegramClient, events, sync
from telethon.types import User, Channel, Message

handler = logging.FileHandler('app.log')
handler.setLevel(logging.DEBUG)

logging.getLogger('sqlalchemy').addHandler(handler)

# These example values won't work. You must get your own api_id and
# api_hash from https://my.telegram.org, under API Development.
api_id = 17684030
api_hash = '9ef7b66a557c7166b9a07dddc7ec7c68'
DB_URL = "sqlite+aiosqlite:///database.db"

chat_id = 1897675404
fizik_chat_id = 2140523692


async def update_usernames(session: AsyncSession):
    """
    обновляем список пользователей в чате
    """
    users = await session.execute(select(UserModel))
    for user in users.scalars():
        user.computed_name = str(user)
        session.add(user)
    await session.commit()


async def print_dialogs(client: TelegramClient):
    chats = await client.get_dialogs()
    for dialog in chats:
        print(dialog.name, dialog.entity.id)


async def fetch_messages(client: TelegramClient, session: AsyncSession):
    users = {x.id: x for x in (await session.execute(select(UserModel))).scalars()}
    channels = {x.id: x for x in (await session.execute(select(ChannelModel))).scalars()}
    
    chat = await client.get_entity(chat_id)
    data = await session.execute(select(
                                        func.max(MessageModel.id).label('one'), 
                                        func.min(MessageModel.id).label('two')
                                        ))
    max_message_id, min_message_id = list(data.all())[0]
    print(max_message_id, min_message_id)
    
    #await engine.dispose()    
    channel: Channel = await client.get_entity(chat_id)
    if chat_id not in channels:

        m = ChannelModel(id=chat_id, name=channel.title)
        channels[chat_id] = m
        session.add(m)
        
    # user = await client.get_entity(chat_id)
    # print(user)
    async for message in client.iter_messages(chat, limit=25000, min_id=max_message_id or 0, reverse=True):
        print(message)
        try:
            assert isinstance(message, Message)
            # удаление, добавление пользователей и т.п.
        except:
            continue
        user_id = message.from_id.user_id
        if user_id not in users:
            user: User = await client.get_entity(user_id)
            u = UserModel(id=user_id, name=user.first_name, last_name=user.last_name, phone=user.phone, username=user.username)
            u.computed_name = str(u)
            users[user_id] = u
            session.add(u)
        m = MessageModel(id=message.id, channel_id=chat_id, user_id=user_id,
                            message=message.message, date=message.date)
        session.add(m)
        if not message.reactions:
            continue
        try:
            lst = await client(GetMessageReactionsListRequest(peer=chat, id=message.id, limit=200))
        except:
            print(message.to_json(indent=2))
            break
        assert isinstance(lst, MessageReactionsList)
        to_add = []
        for reaction in lst.reactions:
            if hasattr(reaction.reaction, 'emoticon'):
                r = Reaction(date=reaction.date, user_id=reaction.peer_id.user_id,
                             emoji=reaction.reaction.emoticon, message_id=message.id)
            else:
                r = Reaction(date=reaction.date, user_id=reaction.peer_id.user_id, emoji='',
                             custom_document_id=reaction.reaction.document_id, message_id=message.id)
            to_add.append(r)
        session.add_all(to_add)

            #print(message.reactions.to_json(indent=4))
    # print(chats[0])        
    # print((await client.get_me()).stringify())
    await session.commit()
    

async def update_channel_members(client, session):
    # Обновляем текущий список участников чата
    await session.execute(delete(ChannelMembers).where(ChannelMembers.channel_id==chat_id))
    channel: Channel = await client.get_entity(chat_id)
    users = await client.get_participants(channel)
    for user in users:
        session.add(ChannelMembers(user_id=user.id, channel_id=chat_id))
        print(user)
    await session.commit()


async def get_message(client: TelegramClient, chat: Channel, message_id: int):
    item = await client.get_messages(chat, ids=[message_id])
    return item[0]


async def update_full_json(client: TelegramClient, session: AsyncSession):
    data = await session.execute(select(MessageModel).where(MessageModel.message_json_data=='').order_by(MessageModel.date.desc()).limit(1000))
    channel: Channel = await client.get_entity(chat_id)
    for message in data.scalars():
        print(message)
        message.message_json_data = (await get_message(client, channel, message.id)).to_json(indent=2, ensure_ascii=False)
        session.add(message)
    await session.commit()




async def update_reactions():
    # обновляем реакции в сообщениях. По умолчанию не знал что весь список реакций выдирается отдельно
    # поэтому выдирал только по 3 недавних
    stmt = select(MessageModel.id, count(Reaction.id)).join(MessageModel.reactions).group_by(MessageModel.id).having(
        count(Reaction.id) == 3)
    messages = await session.execute(stmt)
    chat: Channel = await client.get_entity(chat_id)
    messages = messages.all()
    total = len(messages)
    i = 1
    for message in messages:
        print(f"{i}/{total}")
        i += 1
        lst = await client(GetMessageReactionsListRequest(chat, message.id, 200))
        # print(lst.to_json(indent=4))
        await session.execute(delete(Reaction).where(Reaction.message_id == message.id))
        assert isinstance(lst, MessageReactionsList)
        to_add = []
        for reaction in lst.reactions:
            if hasattr(reaction.reaction, 'emoticon'):
                r = Reaction(date=reaction.date, user_id=reaction.peer_id.user_id,
                             emoji=reaction.reaction.emoticon, message_id=message.id)
            else:
                r = Reaction(date=reaction.date, user_id=reaction.peer_id.user_id, emoji='',
                             custom_document_id=reaction.reaction.document_id, message_id=message.id)
            to_add.append(r)
        session.add_all(to_add)
        await session.commit()



async def get_all_message_replies(client: TelegramClient, message_id: int, channel: Channel):
    result = []
    async for message in client.iter_messages(channel, reply_to=message_id):
        result.append(message)
    return result


async def post_messages():
    ch = await client.get_entity(2140523692)

    min_date = datetime.datetime(2024, 5, 16)
    max_date = datetime.datetime(2024, 5, 18)
    result = {}
    messages = await get_all_message_replies(client, 55, ch)

    for item in messages:
        assert isinstance(item, Message)
        if not isinstance(item.from_id, PeerUser):
            continue
        dt = datetime.datetime(item.date.year, item.date.month, item.date.day, item.date.hour, item.date.minute,
                               item.date.second)
        dt += datetime.timedelta(hours=3)
        if not (min_date <= dt < max_date):
            continue
        if item.from_id.user_id not in result:
            result[item.from_id.user_id] = []
        result[item.from_id.user_id].append((item.id, item.message or 'гифка/видео/медиа сообщение'))
    wb = Workbook()
    ws = wb.active
    ws.append(
        ("ID пользователя", "Имя пользователя", "Фамилия пользователя", "Юзернейм пользователя", "Сообщение (первое)"))

    for key, value in result.items():
        user: User = await client.get_entity(key)
        ws.append([user.id, user.first_name, user.last_name, user.username, value[-1][1]])
        print(key, value)
    print(len(result))
    print(len(messages))
    wb.save("test.xlsx")




async def main():
    engine = create_async_engine(DB_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with TelegramClient('session_name', api_id, api_hash) as client, async_session() as session:
        assert isinstance(client, TelegramClient)
        await fetch_messages(client, session)
        # channel: Channel = await client.get_entity(chat_id)
        # print(await get_message(client, channel, 467120))
        # await update_full_json(client, session)
        #await print_dialogs(client)
        #await update_usernames(session)
            # m.media.document.
            # print(m.media.__class__.__qualname__)

            # print(m.to_json(indent=4))

    await engine.dispose()    
    
    
asyncio.run(main())
