import datetime
import json
import os
import random
from typing import List
from config import COINS_PER_MSG, MSG_CD, WHO_CD, BALL8_CD, PICK_CD, RATING_CD, ANIME_CD, BJ_CD, logger
from sqlalchemy.orm import joinedload

from db.database import Session
from db.models import User, Booster, ActionCooldown, UserAction, UserLevel, UserBooster, Giveaway, GiveawayParticipant, \
    GiveawayGift


class UserCRUD:
    @staticmethod
    def create_user(user_id: int, user_name: str = '', user_nickname: str = '') -> None:
        with Session() as session:
            with session.begin():
                existing_user = session.query(User).filter_by(user_id=user_id).first()

                if not existing_user:
                    user = User(user_id=user_id, user_name=user_name, user_nickname=user_nickname)
                    session.add(user)
                    logger.debug(f"User with ID {user_id} created.")
                else:
                    logger.debug(f"User with ID {user_id} already exists in the database. Skipping creation.")

    @staticmethod
    def delete_user(user_id):
        with Session() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            if user:
                session.delete(user)
                session.commit()
                logger.debug(f"User with ID {user_id} and associated data has been deleted.")
            else:
                logger.debug(f"User with ID {user_id} not found.")

    @staticmethod
    def get_user_by_id(user_id):
        with Session() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            return user

    @staticmethod
    def get_user_id_by_username(user_name):
        with Session() as session:
            user = session.query(User).filter_by(user_name=user_name).first()
            return user.user_id if user else None

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


class GiveawayCRUD:
    @staticmethod
    def create_giveaway(giveaway_type: str, description: str, end_datetime: str,
                        gifts: list,
                        message_id: int = None) -> int:
        with Session() as session:
            new_giveaway = Giveaway(type=giveaway_type, message_id=message_id, description=description,
                                    end_datetime=end_datetime,
                                    winners=len(gifts))
            session.add(new_giveaway)
            session.commit()
            for gift_data in gifts:
                gift_name, amount = gift_data.get('name'), gift_data.get('amount')
                if gift_name and amount:
                    giveaway_gift = GiveawayGift(giveaway_id=new_giveaway.id, gift_name=gift_name, amount=amount)
                    session.add(giveaway_gift)
                    session.commit()
            return new_giveaway.id

    @staticmethod
    def delete_giveaway(giveaway_id: int):
        with Session() as session:
            session.query(GiveawayParticipant).filter_by(giveaway_id=giveaway_id).delete()
            session.query(GiveawayGift).filter_by(giveaway_id=giveaway_id).delete()
            session.query(Giveaway).filter_by(id=giveaway_id).delete()
            session.commit()

    @staticmethod
    def add_participant(user_id: int, giveaway_id: int):
        with Session() as session:
            participant = GiveawayParticipant(user_id=user_id, giveaway_id=giveaway_id)
            session.add(participant)
            session.commit()

    @staticmethod
    def has_user_participated(user_id: int, giveaway_id: int) -> bool:
        with Session() as session:
            existing_participant = session.query(GiveawayParticipant).filter_by(user_id=user_id,
                                                                                giveaway_id=giveaway_id).first()
            return existing_participant is not None

    @staticmethod
    def get_participant_count(giveaway_id: int):
        with Session() as session:
            count = session.query(GiveawayParticipant).filter_by(giveaway_id=giveaway_id).count()
            return count

    @staticmethod
    def set_message_id(giveaway_id: int, message_id: int):
        with Session() as session:
            giveaway = session.query(Giveaway).filter_by(id=giveaway_id).first()
            if giveaway:
                giveaway.message_id = message_id
                session.commit()

    @staticmethod
    def get_giveaway_end_datetime(giveaway_id: int) -> int:
        with Session() as session:
            giveaway = session.query(Giveaway).filter_by(id=giveaway_id).first()
            if giveaway:
                return giveaway.end_datetime.timestamp()

    @staticmethod
    def select_giveaway_winners(giveaway_id: int) -> list:
        with Session() as session:
            giveaway = session.query(Giveaway).filter_by(id=giveaway_id).first()
            if not giveaway:
                return []

            participants = session.query(GiveawayParticipant).filter_by(giveaway_id=giveaway_id).all()

            gifts = session.query(GiveawayGift).filter_by(giveaway_id=giveaway_id).all()

            random.shuffle(participants)
            random.shuffle(gifts)

            winners = []
            used_gifts = set()

            for participant in participants:
                if not gifts:
                    break
                gift = random.choice(gifts)
                if gift.id not in used_gifts:
                    winners.append(
                        {"winner": participant.user_id, "gift": {"name": gift.gift_name, "amount": gift.amount}})
                    used_gifts.add(gift.id)

            GiveawayCRUD.delete_giveaway(giveaway_id)
            return winners

    @staticmethod
    def get_all_giveaways():
        with Session() as session:
            giveaways = session.query(Giveaway).all()
            return giveaways

    @staticmethod
    def get_giveaway_message_id(giveaway_id: int) -> int:
        with Session() as session:
            giveaway = session.query(Giveaway).filter_by(id=giveaway_id).first()
            return giveaway.message_id


def setup_database():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "..", "boosters.json")
    with open(file_path, 'r', encoding="UTF-8") as f:
        boosters = json.load(f)
    boosters = [Booster(**b) for b in boosters['boosters']]
    BoosterCRUD.add_boosters(boosters)
    ActionCooldownCRUD.add_actions()
