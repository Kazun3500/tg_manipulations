import datetime
from typing import List
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

class Base(DeclarativeBase):
    pass


class Channel(Base):
    __tablename__="channel"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str|None]
    messages: Mapped[list["Message"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str|None]
    phone: Mapped[str|None]
    last_name: Mapped[str|None]
    username: Mapped[str|None]

    computed_name: Mapped[str|None] = mapped_column(default='')

    messages: Mapped[list["Message"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reactions: Mapped[list["Reaction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id})>"

    def __str__(self):
        username = self.username or ''.strip()
        name =  f"{self.name or ''} {self.last_name or ''}".strip()
        if username:
            return f"{name} ({username})"
        else:
            return name



class ChannelMembers(Base):
    __tablename__ = "channel_members"
    id: Mapped[int]  = mapped_column(primary_key=True)
    channel_id: Mapped[int]
    user_id: Mapped[int]
    

class Message(Base):
    __tablename__ = "message"
    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[Channel] = relationship(back_populates="messages")
    channel_id: Mapped[int] = mapped_column(ForeignKey("channel.id"))
    message: Mapped[str]
    date: Mapped[datetime.datetime]
    user: Mapped[User] = relationship(back_populates="messages")
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    reactions: Mapped[list["Reaction"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )
    #def __repr__(self) -> str:
    #    return f"User(id={self.id!r}, name={self.name!r}, fullname={self.fullname!r})"

class Reaction(Base):
    __tablename__ = "reaction"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.datetime]
    emoji: Mapped[str] = mapped_column(default="")
    custom_document_id: Mapped[int|None] = mapped_column(default=None)
    user: Mapped[User] = relationship(back_populates="reactions")
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    
    message: Mapped[Message] = relationship(back_populates="reactions")
    message_id: Mapped[int] = mapped_column(ForeignKey("message.id"))