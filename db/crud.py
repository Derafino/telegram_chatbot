import datetime
from typing import List
from config import COINS_PER_MSG
from sqlalchemy.orm import joinedload

from db.database import Session
from db.models import User, Booster, ActionCooldown, UserAction, UserLevel


class UserCRUD:
    @staticmethod
    def create_user(user_id: int, user_name: str = '', user_nickname: str = '') -> None:
        with Session() as session:
            with session.begin():
                user = User(user_id=user_id, user_name=user_name, user_nickname=user_nickname)
                session.add(user)

    @staticmethod
    def check_user_exists(user_id: int) -> bool:
        with Session() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            return user is not None

    @staticmethod
    def get_all_users() -> List[User]:
        with Session() as session:
            users = session.query(User).all()
            return users

    @staticmethod
    def add_user_coins_per_min():
        with Session() as session:
            with session.begin():
                users = session.query(User).options(joinedload(User.boosters)).all()
                for user in users:
                    user.user_coins += user.user_coins_per_min

    @staticmethod
    def add_user_coins_per_msg(user_id):
        with Session() as session:
            with session.begin():
                user = session.query(User).options(joinedload(User.boosters)).filter_by(user_id=user_id).first()
                user.user_coins += (user.user_coins_per_msg + COINS_PER_MSG)

    @staticmethod
    def get_user_balance(user_id) -> int:
        with Session() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            return user.user_coins

    @staticmethod
    def add_coins(user_id: int, amount: int):
        with Session() as session:
            with session.begin():
                user = session.query(User).filter_by(user_id=user_id).first()
                user.user_coins += amount

    @staticmethod
    def get_boosters_amount(user_id):
        with Session() as session:
            user = session.query(User).options(joinedload(User.boosters)).filter_by(user_id=user_id).first()
            return user.user_coins_per_msg, user.user_coins_per_min


class UserActionCRUD:
    @staticmethod
    def add_action(user_id: int, action_id: int):
        with Session() as session:
            with session.begin():
                now = datetime.datetime.now()
                action = UserAction(user=user_id, action=action_id, last_time=now)
                session.add(action)

    @staticmethod
    def update_action_time(user_id: int, action_id: int):
        with Session() as session:
            with session.begin():
                action_record = session.query(UserAction).filter_by(user=user_id, action=action_id).first()
                now = datetime.datetime.now()
                if not action_record:
                    action = UserAction(user=user_id, action=action_id, last_time=now)
                    session.add(action)
                else:
                    action_record.last_time = now

    @staticmethod
    def get_last_action(user_id: int, action_id: int) -> datetime.datetime | int:
        with Session() as session:
            action_record = session.query(UserAction).filter_by(user=user_id, action=action_id).first()
        if action_record:
            return action_record.last_time
        else:
            return 0


class BoosterCRUD:
    @staticmethod
    def add_boosters():
        with Session() as session:
            with session.begin():
                session.query(Booster).delete()
                boosters_records = [
                    Booster(id=1, booster_name='booster_name_msg1', booster_type=1, bonus_amount=5, base_price=10),
                    Booster(id=2, booster_name='booster_name_msg2', booster_type=1, bonus_amount=10, base_price=20),

                    Booster(id=3, booster_name='booster_name_time1', booster_type=2, bonus_amount=2, base_price=5),
                    Booster(id=4, booster_name='booster_name_time2', booster_type=2, bonus_amount=4, base_price=10),
                    Booster(id=5, booster_name='booster_name_time3', booster_type=2, bonus_amount=8, base_price=20),
                ]
                session.add_all(boosters_records)


class UserLevelCRUD:
    @staticmethod
    def create_level(user_id):
        with Session() as session:
            with session.begin():
                level = UserLevel(user_id=user_id)
                session.add(level)

    @staticmethod
    def get_level(user_id):
        with Session() as session:
            level = session.query(UserLevel).filter_by(user_id=user_id).first()
            if not level:
                UserLevelCRUD.create_level(user_id)
                level = session.query(UserLevel).filter_by(user_id=user_id).first()
            return level

    @staticmethod
    def update_level(user_id, new_level, new_xp, new_xp_needed):
        with Session() as session:
            with session.begin():
                level = session.query(UserLevel).filter_by(user_id=user_id).first()
                level.level = new_level
                level.xp = new_xp
                level.xp_needed = new_xp_needed

    @staticmethod
    def get_top_users():
        with Session() as session:
            user_levels = session.query(UserLevel).options(joinedload(UserLevel.user)).order_by(
                -UserLevel.level, -UserLevel.xp).limit(20).all()
            return user_levels


class ActionCooldownCRUD:
    @staticmethod
    def add_actions():
        with Session() as session:
            with session.begin():
                session.query(ActionCooldown).delete()
                action_cooldown_records = [
                    ActionCooldown(id=1, cooldown=30),  # slot
                    ActionCooldown(id=2, cooldown=30),  # bowling
                    ActionCooldown(id=3, cooldown=30),  # pickpocket
                    ActionCooldown(id=4, cooldown=30),  # crash
                    ActionCooldown(id=5, cooldown=30),  # roulette
                    ActionCooldown(id=6, cooldown=130),  # blackjack
                    ActionCooldown(id=7, cooldown=60),  # msg
                ]
                session.add_all(action_cooldown_records)

    @staticmethod
    def get_cooldown(action_id):
        with Session() as session:
            with session.begin():
                action_record = session.query(ActionCooldown).filter_by(id=action_id).first()
                cooldown = action_record.cooldown
        return cooldown


def setup_database():
    BoosterCRUD.add_boosters()
    ActionCooldownCRUD.add_actions()
