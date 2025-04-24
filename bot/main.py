import asyncio
import sqlite3
from os import getenv
from datetime import datetime
from aiogram.filters import Command
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from sensors import get_temperature, get_humidity
from serial import Serial

TOKEN = getenv('TOKEN')
PORT = getenv('PORT')

# Интервал проверки условий для отправки напоминания
CHECK_INTERVAL = 10

START_MESSAGE = '''Привет. Данный бот позволяет просматривать значения
температуры и влажности с датчиков в режиме реального времени'''


INIT_SCRIPT = '''
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    parameter TEXT,
    condition TEXT,
    value REAL,
    created_at TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
)
'''


def init_db():
    db = sqlite3.connect('notifications.db')
    cursor = db.cursor()
    cursor.execute(INIT_SCRIPT)
    db.commit()
    db.close()


class NotificationStates(StatesGroup):
    waiting_parameter = State()
    waiting_condition = State()
    waiting_value = State()


ser = Serial(PORT)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


def get_parameters_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='Температура',
                                  callback_data='temperature')],
            [InlineKeyboardButton(text='Влажность', callback_data='humidity')]
        ]
    )


def get_conditions_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text='<', callback_data='less'),
                InlineKeyboardButton(text='=', callback_data='equal'),
                InlineKeyboardButton(text='>', callback_data='greater')
            ],
            [InlineKeyboardButton(text='Назад', callback_data='back')]
        ]
    )


@dp.message(Command('start'))
async def command_start_handler(message: Message) -> None:
    await message.answer(START_MESSAGE)


@dp.message(Command('temperature'))
async def command_temperature_handler(message: Message) -> None:
    await message.answer(
        f'Текущее значение температуры: {get_temperature(ser)}')


@dp.message(Command('humidity'))
async def command_humidity_handler(message: Message) -> None:
    await message.answer(f'Текущее значение влажности: {get_humidity(ser)}')


@dp.message(Command('notifications'))
async def command_notifications_handler(message: Message) -> None:
    db = sqlite3.connect('notifications.db')
    cursor = db.cursor()
    query = 'SELECT * FROM notifications WHERE user_id=? AND is_active=1'
    cursor.execute(query, (message.from_user.id,))
    notifications = cursor.fetchall()
    db.close()

    if not notifications:
        await message.answer('У вас нет активных уведомлений')
        return

    response_lst = ['Ваши активные уведомления:']

    params = {
        'temperature': 'Температура',
        'humidity': 'Влажность',
    }
    conds = {
        'less': 'меньше',
        'greater': 'больше',
        'equal': 'равна',
    }

    for i, n in enumerate(notifications, start=1):
        param, cond, value = n[2:5]
        response_lst.append(f'{i}) {params[param]} {conds[cond]} {value}')

    await message.answer('\n'.join(response_lst))


@dp.message(Command('setnotification'))
async def command_setnotification_handler(
    message: Message,
    state: FSMContext
) -> None:
    await message.answer(
        'Выберите параметр для уведомления:',
        reply_markup=get_parameters_keyboard()
    )
    await state.set_state(NotificationStates.waiting_parameter)


@dp.callback_query(NotificationStates.waiting_parameter)
async def process_parameter(callback: CallbackQuery, state: FSMContext):
    if callback.data == 'back':
        await callback.message.edit_text(
            'Выберите параметр:',
            reply_markup=get_parameters_keyboard()
        )
        return

    await state.update_data(parameter=callback.data)
    await callback.message.edit_text(
        'Выберите условие:',
        reply_markup=get_conditions_keyboard()
    )
    await state.set_state(NotificationStates.waiting_condition)
    await callback.answer()


@dp.callback_query(NotificationStates.waiting_condition)
async def process_condition(callback: CallbackQuery, state: FSMContext):
    if callback.data == 'back':
        await callback.message.edit_text(
            'Выберите параметр:',
            reply_markup=get_parameters_keyboard()
        )
        await state.set_state(NotificationStates.waiting_parameter)
        await callback.answer()
        return

    await state.update_data(condition=callback.data)
    await callback.message.edit_text(
        'Введите числовое значение:',
        reply_markup=None
    )
    await state.set_state(NotificationStates.waiting_value)
    await callback.answer()


@dp.message(NotificationStates.waiting_value)
async def process_value(message: Message, state: FSMContext):
    try:
        value = float(message.text)
        data = await state.get_data()

        db = sqlite3.connect('notifications.db')
        cursor = db.cursor()
        cursor.execute(
            'INSERT INTO notifications \
            (user_id, parameter, condition, value, created_at) VALUES \
            (?, ?, ?, ?, ?)',
            (message.from_user.id, data['parameter'], data['condition'], value,
             datetime.now())
        )
        db.commit()
        db.close()

        await message.answer('Уведомление успешно установлено!')
        await state.clear()
    except ValueError:
        await message.answer('Пожалуйста, введите корректное число')


async def monitor_sensors(bot: Bot):
    while True:
        current_temperature = get_temperature(ser)
        current_humidity = get_humidity(ser)

        db = sqlite3.connect('notifications.db')
        cursor = db.cursor()
        cursor.execute('SELECT * FROM notifications WHERE is_active=1')
        notifications = cursor.fetchall()
        db.close()

        for n in notifications:
            user_id, param, cond, value = n[1:5]
            should_alert = False

            if param == 'temperature':
                current = current_temperature
            else:
                current = current_humidity

            conditions = (
                cond == 'less' and current < value,
                cond == 'greater' and current > value,
                cond == 'equal' and current == value
            )

            if any(c for c in conditions):
                should_alert = True

            if should_alert:
                message = 'Сработало уведомление!\n' \
                          f'{param.capitalize()} сейчас {current}'
                await bot.send_message(user_id, message)

        await asyncio.sleep(CHECK_INTERVAL)


async def main() -> None:
    bot = Bot(token=TOKEN)

    commands = [
        BotCommand(command='start', description='начать работу с ботом'),
        BotCommand(command='temperature', description='текущая температура'),
        BotCommand(command='humidity', description='текущая влажность'),
        BotCommand(command='notifications',
                   description='активные уведомления'),
        BotCommand(command='setnotification',
                   description='установить уведомление'),
    ]

    await bot.set_my_commands(commands)

    init_db()

    asyncio.create_task(monitor_sensors(bot))

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
