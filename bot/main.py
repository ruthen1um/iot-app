from os import getenv
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    PicklePersistence,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)
from sensors import find_arduino_port, get_temperature, get_humidity
from serial import Serial

TOKEN = getenv('TOKEN')
PERSISTENCE_FILE = getenv('PERSISTENCE_FILE')

START_MESSAGE = '''Привет. Данный бот позволяет просматривать значения
температуры и влажности с датчиков в режиме реального времени.'''

REMINDER_MESSAGE = '''Выберите параметр для установки напоминания.'''

TEMPERATURE_MORE_THAN_MESSAGE = '''Введите значение температуры при превышении
которого вы получите уведомление.'''

TEMPERATURE_LESS_THAN_MESSAGE = '''Введите значение температуры при понижении
ниже которого вы получите уведомление.'''

HUMIDITY_MORE_THAN_MESSAGE = '''Введите значение влажности при превышении
которого вы получите уведомление.'''

HUMIDITY_LESS_THAN_MESSAGE = '''Введите значение влажности при понижении
ниже которого вы получите уведомление.'''

VALUE_SUCCESS_MESSAGE = 'Напоминание успешно запланировано.'

CHOICES_FALLBACK_MESSAGE = 'Выберите один из предложенных вариантов.'

VALUE_FALLBACK_MESSAGE = 'Введите целое число.'

DEFAULT_FALLBACK_MESSAGE = 'Произошла ошибка. Возвращаю в главное меню.'

MAIN_MENU, REMINDER_MENU, CHOOSING_REMINDER_VALUE = range(3)

MAIN_KEYBOARD = [
    ['Температура'],
    ['Влажность'],
    ['Напоминание'],
]

MAIN_MARKUP = ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True)

REMINDER_KEYBOARD = [
    ['Температура больше ...'],
    ['Температура меньше ...'],
    ['Влажность больше ...'],
    ['Влажность меньше ...'],
]

REMINDER_MARKUP = ReplyKeyboardMarkup(REMINDER_KEYBOARD, resize_keyboard=True)


async def start_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=START_MESSAGE,
                                   reply_markup=MAIN_MARKUP)
    return MAIN_MENU


async def sensors_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    functions = {
        'Температура': lambda:
            get_temperature(context.application.bot_data['serial']),
        'Влажность': lambda:
            get_humidity(context.application.bot_data['serial']),
    }
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=functions[update.message.text]())


async def reminder_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=REMINDER_MESSAGE,
                                   reply_markup=REMINDER_MARKUP)
    return REMINDER_MENU


async def reminder_condition_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    options = {
        'Температура больше ...': TEMPERATURE_MORE_THAN_MESSAGE,
        'Температура меньше ...': TEMPERATURE_LESS_THAN_MESSAGE,
        'Влажность больше ...': HUMIDITY_MORE_THAN_MESSAGE,
        'Влажность меньше ...': HUMIDITY_LESS_THAN_MESSAGE,
    }

    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=options[update.message.text],
                                   reply_markup=ReplyKeyboardRemove())
    return CHOOSING_REMINDER_VALUE


async def value_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    # TODO: implement system to send notifications
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=VALUE_SUCCESS_MESSAGE,
                                   reply_markup=MAIN_MARKUP)
    return MAIN_MENU


async def choices_fallback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=CHOICES_FALLBACK_MESSAGE)


async def value_fallback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=VALUE_FALLBACK_MESSAGE)


async def default_fallback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=DEFAULT_FALLBACK_MESSAGE,
                                   reply_markup=MAIN_MARKUP)
    return MAIN_MENU


if __name__ == '__main__':
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .persistence(PicklePersistence(filepath=PERSISTENCE_FILE))
        .build()
    )

    port = find_arduino_port()
    if (port is None):
        # TODO
        pass

    application.bot_data['serial'] = Serial(port, 9600, timeout=1)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_handler)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Text([
                    'Температура',
                    'Влажность',
                ]), sensors_handler),
                MessageHandler(filters.Text(['Напоминание']),
                               reminder_handler),
                MessageHandler(filters.TEXT,
                               choices_fallback_handler),
            ],
            REMINDER_MENU: [
                MessageHandler(filters.Text([
                    'Температура больше ...',
                    'Температура меньше ...',
                    'Влажность больше ...',
                    'Влажность меньше ...',
                ]), reminder_condition_handler),
                MessageHandler(filters.TEXT,
                               choices_fallback_handler),
            ],
            CHOOSING_REMINDER_VALUE: [
                MessageHandler(filters.Regex(r'^-?[1-9]\d*$'),
                               value_handler),
                MessageHandler(filters.TEXT,
                               value_fallback_handler),
            ]
        },
        fallbacks=[MessageHandler(filters.TEXT, default_fallback_handler)],
        name='conversation_handler',
        persistent=True,
    )

    application.add_handler(conv_handler)
    application.run_polling()
