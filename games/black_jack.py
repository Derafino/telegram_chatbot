from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, ConversationHandler, CallbackContext
import random

deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4


def deal_card(deck):
    """Deal a single card from the deck."""
    return random.choice(deck)


def deal_hand(deck):
    """Deal a new hand for the player or dealer."""
    return [deal_card(deck), deal_card(deck)]


def sum_hand(hand):
    """Calculate the total value of a hand."""
    if sum(hand) <= 21:
        return sum(hand)
    else:
        # Handle the case where Ace should be counted as 1 instead of 11
        return sum(hand) - 10 if 11 in hand else sum(hand)
