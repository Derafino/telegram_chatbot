from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import expression
from config import logger, COINS_PER_MSG

from db.database import engine

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    user_name = Column(String, unique=True, nullable=True)
    user_nickname = Column(String, unique=True, nullable=False)
    user_coins = Column(Integer, default=0)

    boosters = relationship("UserBooster")

    @property
    def user_coins_per_msg(self):
        amount = COINS_PER_MSG
        for booster in self.boosters:
            if booster.id in (1, 2):
                amount += booster.total_bonus
        return amount

    @property
    def user_coins_per_min(self):
        amount = 0
        for booster in self.boosters:
            if booster.id in (3, 4, 5):
                amount += booster.total_bonus
        return amount


class Booster(Base):
    __tablename__ = "boosters"

    id = Column(Integer, primary_key=True)
    booster_name = Column(String, unique=True, nullable=False)
    booster_type = Column(Integer)
    bonus_amount = Column(Integer)
    base_price = Column(Integer)


class UserBooster(Base):
    __tablename__ = "users_boosters"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    booster_id = Column(Integer, ForeignKey('boosters.id'))
    amount = Column(Integer)
    booster = relationship("Booster")

    @property
    def total_bonus(self):
        return self.amount * self.booster.bonus_amount


class ActionCooldown(Base):
    __tablename__ = "action_cooldown"

    id = Column(Integer, primary_key=True)
    cooldown = Column(Integer)


class UserAction(Base):
    __tablename__ = "user_action"

    id = Column(Integer, primary_key=True)
    action = Column(Integer, ForeignKey('action_cooldown.id'))
    user = Column(Integer, ForeignKey('users.user_id'))
    last_time = Column(DateTime, nullable=False)

    __table_args__ = (UniqueConstraint('action', 'user'),)


Base.metadata.create_all(engine)
