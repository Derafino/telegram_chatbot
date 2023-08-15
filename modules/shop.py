from typing import List, Union

from db.crud import BoosterCRUD


class ShopItem:
    def __init__(self, name, base_price):
        self.name = name
        self.base_price = base_price

    def calculate_price(self, owned_boosters_count=0):
        """Calculate the price of the item."""
        return self.base_price

    def display_info(self, amount=0, count=0):
        """Display information about the item."""
        return f"{self.name} - {self.calculate_price() / 100} coins"


class ShopItemBooster(ShopItem):
    def __init__(self, booster_id, name, base_price, booster_type, bonus_amount):
        super().__init__(name, base_price)
        self.booster_id = booster_id
        self.booster_type = booster_type
        self.bonus_amount = bonus_amount


class ShopItemBoosterMSG(ShopItemBooster):
    def calculate_price(self, owned_boosters_count=0):
        """Custom logic to calculate the price for message boosters."""
        price = self.base_price
        increment = 20
        for _ in range(owned_boosters_count):
            price += increment
            increment += 10
        return price

    def display_info(self, amount=0, count=0):
        """Display information about the item."""
        return f"{amount/100}/MSG. ({count})"


class ShopItemBoosterPerMin(ShopItemBooster):
    def calculate_price(self, owned_boosters_count=0):
        """Custom logic to calculate the price for per-minute boosters."""
        price = self.base_price
        increment = 20
        for _ in range(owned_boosters_count):
            price += increment
            increment += 25
        return price

    def display_info(self, amount=0, count=0):
        """Display information about the item."""
        return f"{amount/100}/MIN. ({count})"


def get_items_for_sale() -> dict:
    items_for_sale = list()
    items_for_sale += get_boosters_for_sale()
    shop_items = {}
    for i, item in enumerate(items_for_sale):
        shop_items[f'item{i}'] = item
    return shop_items


def get_boosters_for_sale() -> List[Union[ShopItemBoosterMSG, ShopItemBoosterPerMin]]:
    boosters = BoosterCRUD.get_all_boosters()
    boosters_for_sale = list()
    for b in boosters:
        if b.booster_type == 1:
            boosters_for_sale.append(ShopItemBoosterMSG(booster_id=b.id, name=b.booster_name, base_price=b.base_price,
                                                        booster_type=b.booster_type, bonus_amount=b.bonus_amount))
        elif b.booster_type == 2:
            boosters_for_sale.append(
                ShopItemBoosterPerMin(booster_id=b.id, name=b.booster_name, base_price=b.base_price,
                                      booster_type=b.booster_type, bonus_amount=b.bonus_amount))
        else:
            pass
    return boosters_for_sale


SHOP_ITEMS = get_items_for_sale()
