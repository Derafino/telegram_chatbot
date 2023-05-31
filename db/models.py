from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from config import COINS_PER_MSG

from db.database import engine

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    user_name = Column(String, unique=True, nullable=True)
    user_nickname = Column(String, unique=True, nullable=False)
    user_coins = Column(Integer, default=0)

    boosters = relationship("UserBooster", back_populates="user")
    user_level = relationship("UserLevel", back_populates="user")

    @property
    def user_coins_per_msg(self):
        amount = COINS_PER_MSG
        for booster in self.boosters:
            if booster.booster_id in (1, 2):
                amount += booster.total_bonus
        return amount

    @property
    def user_coins_per_min(self):
        amount = 0
        for booster in self.boosters:
            if booster.booster_id in (3, 4, 5):
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
    user = relationship("User", back_populates="boosters")

    @property
    def total_bonus(self):
        return self.amount * self.booster.bonus_amount


class UserLevel(Base):
    __tablename__ = "users_level"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    level = Column(Integer, default=0)
    xp = Column(Integer, default=0)
    xp_needed = Column(Integer, default=100)
    user = relationship("User", back_populates="user_level")

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
