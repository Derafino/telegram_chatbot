import random


def magic_8_ball_phrase():
    answers = ['Безперечно', 'Ніяких сумнівів', 'Певно так', 'Можеш бути впевнений у цьому', 'Мені здається - так',
               'Найімовірніше', 'Хороші перспективи', 'Знаки кажуть - так', 'Так', 'Поки не зрозуміло, спробуй знову',
               'Запитай пізніше', 'Краще не казати', 'Зараз не можна передбачити', 'Сконцентруйся і спитай знову',
               'Навіть не думай', 'Моя відповідь - ні', 'За моїми даними - ні', 'Перспективи не дуже хороші',
               'Дуже сумнівно']
    return random.choice(answers)
