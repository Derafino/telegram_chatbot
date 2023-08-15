import datetime
import json
import os
from typing import List
from config import COINS_PER_MSG, MSG_CD, WHO_CD, BALL8_CD, PICK_CD, RATING_CD, ANIME_CD, BJ_CD, logger
from sqlalchemy.orm import joinedload

from db.database import Session
from db.models import User, Booster, ActionCooldown, UserAction, UserLevel, UserBooster


class UserCRUD:
    @staticmethod
    def create_user(user_id: int, user_name: str = '', user_nickname: str = '') -> None:
        with Session() as session:
            with session.begin():
                user = User(user_id=user_id, user_name=user_name, user_nickname=user_nickname)
                session.add(user)

    @staticmethod
    def get_user_by_id(user_id):
        with Session() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            return user

    @staticmethod
    def check_user_exists(user_id: int) -> bool:
        user = UserCRUD.get_user_by_id(user_id)
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
                    logger.debug(f"{user.user_id} +{user.user_coins_per_min} {user.user_coins}")
                    user.user_coins += user.user_coins_per_min

    @staticmethod
    def add_user_coins_per_msg(user_id):
        with Session() as session:
            with session.begin():
                user = session.query(User).options(joinedload(User.boosters)).filter_by(user_id=user_id).first()
                user.user_coins += (user.user_coins_per_msg + COINS_PER_MSG)
                logger.debug(f"{user_id} +{COINS_PER_MSG} {user.user_coins}")

    @staticmethod
    def get_user_balance(user_id) -> int:
        user = UserCRUD.get_user_by_id(user_id)
        return user.user_coins

    @staticmethod
    def add_coins(user_id: int, amount: int):
        with Session() as session:
            logger.debug(f"{user_id} +{amount}")
            user = session.query(User).filter_by(user_id=user_id).first()
            user.user_coins += amount
            session.commit()

    @staticmethod
    def get_boosters_amount(user_id):
        with Session() as session:
            user = session.query(User).options(joinedload(User.boosters)).filter_by(user_id=user_id).first()
            return user.user_coins_per_msg, user.user_coins_per_min

    @staticmethod
    def pay_coins(user_id, n):
        with Session() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            if user is None:
                logger.error(f"No user found with ID {user_id}")
                return False

            logger.info(f"User {user_id} has {user.user_coins} coins")

            if user.user_coins >= n:
                user.user_coins -= n
                session.commit()
                logger.info(f"Subtracted {n} coins from user {user_id}. New balance: {user.user_coins}")
                return True
            else:
                logger.info(f"User {user_id} does not have enough coins")
                return False


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
    def add_boosters(boosters: List[Booster]):
        with Session() as session:
            with session.begin():
                session.query(Booster).delete()
                session.add_all(boosters)

    @staticmethod
    def get_all_boosters() -> List[Booster]:
        with Session() as session:
            boosters = session.query(Booster).all()
            return boosters


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
                logger.debug(f"{user_id} {new_level} {new_xp}")
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
                    ActionCooldown(id=1, cooldown=MSG_CD),  # msg
                    ActionCooldown(id=2, cooldown=WHO_CD),  # who
                    ActionCooldown(id=3, cooldown=BALL8_CD),  # 8ball
                    ActionCooldown(id=4, cooldown=PICK_CD),  # pick
                    ActionCooldown(id=5, cooldown=RATING_CD),  # rating
                    ActionCooldown(id=6, cooldown=ANIME_CD),  # anime
                    ActionCooldown(id=7, cooldown=BJ_CD),  # bj
                ]
                session.add_all(action_cooldown_records)

    @staticmethod
    def get_cooldown(action_id):
        with Session() as session:
            with session.begin():
                action_record = session.query(ActionCooldown).filter_by(id=action_id).first()
                cooldown = action_record.cooldown
        return cooldown


class UsersBoostersCRUD:
    @staticmethod
    def get_booster_count(user_id, booster_id):
        with Session() as session:
            booster_record = session.query(UserBooster).filter_by(user_id=user_id, booster_id=booster_id).first()
            return booster_record.amount if booster_record else 0

    @staticmethod
    def increment_or_create(user_id, booster_id):
        with Session() as session:
            booster_record = session.query(UserBooster).filter_by(user_id=user_id, booster_id=booster_id).first()

            if booster_record:
                booster_record.amount += 1
            else:
                new_booster = UserBooster(user_id=user_id, booster_id=booster_id, amount=1)
                session.add(new_booster)

            session.commit()


def setup_database():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "..", "boosters.json")
    with open(file_path, 'r', encoding="UTF-8") as f:
        boosters = json.load(f)
    boosters = [Booster(**b) for b in boosters['boosters']]
    BoosterCRUD.add_boosters(boosters)
    ActionCooldownCRUD.add_actions()
