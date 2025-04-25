import asyncio
import sqlite3
from os import getenv
from datetime import datetime
from aiogram.filters import Command, StateFilter, and_f
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
from dataclasses import dataclass
from sensors import get_temperature, get_humidity
from serial import Serial
from dotenv import load_dotenv

load_dotenv()

TOKEN = getenv('TOKEN')
PORT = getenv('PORT')
DATABASE_PATH = getenv('DATABASE_PATH')

# Интервал проверки условий для отправки напоминания
CHECK_INTERVAL = getenv('CHECK_INTERVAL')

START_MESSAGE = '''Привет. Данный бот позволяет просматривать значения
температуры и влажности с датчиков в режиме реального времени'''

CREATE_NOTIFICATIONS_TABLE = '''
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    parameter TEXT,
    condition TEXT,
    value REAL,
    created_at TIMESTAMP
)
'''

SELECT_USER_NOTIFICATIONS = '''
SELECT * FROM notifications WHERE user_id=?
'''

SELECT_NOTIFICATIONS = '''
SELECT * FROM notifications
'''

INSERT_NOTIFICATION = '''
INSERT INTO notifications (
    user_id,
    parameter,
    condition,
    value,
    created_at
) VALUES (?, ?, ?, ?, ?)
'''

SELECT_USER_NOTIFICATION_BY_ID = '''
SELECT 1 FROM notifications WHERE id=? AND user_id=?
'''

DELETE_NOTIFICATION = '''
DELETE FROM notifications WHERE user_id=? AND id=?
'''

TEMPERATURE_CALLBACK_DATA = 'temperature'
HUMIDITY_CALLBACK_DATA = 'humidity'

LESS_CONDITION_CALLBACK_DATA = 'less'
EQUAL_CONDITION_CALLBACK_DATA = 'equal'
GREATER_CONDITION_CALLBACK_DATA = 'greater'

PARAMETERS_MARKUP = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Температура',
                              callback_data='temperature')],
        [InlineKeyboardButton(text='Влажность', callback_data='humidity')]
    ]
)

CONDITIONS_MARKUP = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='<', callback_data='less'),
            InlineKeyboardButton(text='=', callback_data='equal'),
            InlineKeyboardButton(text='>', callback_data='greater')
        ],
        [InlineKeyboardButton(text='Назад', callback_data='back')]
    ]
)


@dataclass
class Notification:
    id: object
    user_id: object
    parameter: object
    condition: object
    value: object
    created_at: object

    def __str__(self):
        return (
            Notification.parameter_to_str(self.parameter) + ' ' +
            Notification.condition_to_str(self.condition) + ' ' +
            str(self.value)
        ).capitalize()

    @staticmethod
    def parameter_to_str(parameter):
        parameters = {
            TEMPERATURE_CALLBACK_DATA: 'температура',
            HUMIDITY_CALLBACK_DATA: 'влажность',
        }
        return parameters.get(parameter)

    @staticmethod
    def condition_to_str(condition):
        conditions = {
            LESS_CONDITION_CALLBACK_DATA: 'меньше',
            EQUAL_CONDITION_CALLBACK_DATA: 'равна',
            GREATER_CONDITION_CALLBACK_DATA: 'больше',
        }
        return conditions.get(condition)


class SetNotificationStates(StatesGroup):
    waiting_parameter = State()
    waiting_condition = State()
    waiting_value = State()


class DeleteNotificationStates(StatesGroup):
    waiting_index = State()


ser = Serial(PORT)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


@dp.message(and_f(StateFilter(None), Command('start')))
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await message.answer(START_MESSAGE)


@dp.message(Command('cancel'))
async def command_cancel_handler(
    message: Message,
    state: FSMContext
) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer('Сейчас не выполняется ни одна операция')
    else:
        await state.clear()
        await message.answer('Операция отменена')


@dp.message(and_f(StateFilter(None), Command('temperature')))
async def command_temperature_handler(
    message: Message,
    state: FSMContext
) -> None:
    temperature = get_temperature(ser)
    await message.answer(f'Текущее значение температуры: {temperature}')


@dp.message(and_f(StateFilter(None), Command('humidity')))
async def command_humidity_handler(
    message: Message,
    state: FSMContext
) -> None:
    humidity = get_humidity(ser)
    await message.answer(f'Текущее значение влажности: {humidity}')


@dp.message(and_f(StateFilter(None), Command('notifications')))
async def command_notifications_handler(
    message: Message,
    state: FSMContext
) -> None:
    con = sqlite3.connect(DATABASE_PATH)
    with con:
        cur = con.execute(
            SELECT_USER_NOTIFICATIONS,
            (message.from_user.id,)
        )
        notifications = tuple(
            Notification(*row) for row in cur.fetchall())
    con.close()

    if not notifications:
        await message.answer('У вас нет активных уведомлений')
        return

    response_lst = ['Ваши активные уведомления:']

    for idx, notification in enumerate(notifications, start=1):
        response_lst.append(f'({idx}) {notification}')

    await message.answer('\n'.join(response_lst))


@dp.message(and_f(StateFilter(None), Command('setnotification')))
async def command_setnotification_handler(
    message: Message,
    state: FSMContext
) -> None:
    await message.answer(
        'Выберите параметр для уведомления:',
        reply_markup=PARAMETERS_MARKUP
    )
    await state.set_state(SetNotificationStates.waiting_parameter)


@dp.callback_query(SetNotificationStates.waiting_parameter)
async def process_parameter(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    await state.update_data(parameter=callback.data)
    await callback.message.edit_text(
        'Выберите условие:',
        reply_markup=CONDITIONS_MARKUP
    )
    await state.set_state(SetNotificationStates.waiting_condition)
    await callback.answer()


@dp.callback_query(SetNotificationStates.waiting_condition)
async def process_condition(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    if callback.data == 'back':
        await callback.message.edit_text(
            'Выберите параметр:',
            reply_markup=PARAMETERS_MARKUP
        )
        await state.set_state(SetNotificationStates.waiting_parameter)
        await callback.answer()
        return

    await state.update_data(condition=callback.data)
    await callback.message.edit_text(
        'Введите числовое значение:',
        reply_markup=None
    )
    await state.set_state(SetNotificationStates.waiting_value)
    await callback.answer()


@dp.message(SetNotificationStates.waiting_value)
async def process_value(message: Message, state: FSMContext) -> None:
    try:
        value = float(message.text)
        data = await state.get_data()

        parameters = (
            message.from_user.id,
            data['parameter'],
            data['condition'],
            value,
            datetime.now().isoformat(),
        )

        con = sqlite3.connect(DATABASE_PATH)
        with con:
            con.execute(
                INSERT_NOTIFICATION,
                parameters
            )
        con.close()

        await message.answer('Уведомление успешно установлено!')
        await state.clear()

    except ValueError:
        await message.answer('Пожалуйста, введите корректное число')


@dp.message(and_f(StateFilter(None), Command('deletenotification')))
async def command_deletenotification_handler(
    message: Message,
    state: FSMContext
) -> None:
    con = sqlite3.connect(DATABASE_PATH)
    with con:
        cur = con.execute(
            SELECT_USER_NOTIFICATIONS,
            (message.from_user.id,)
        )
        notifications = [Notification(*row) for row in cur.fetchall()]
    con.close()

    if not notifications:
        await message.answer('У вас нет активных уведомлений для удаления')
        return

    await message.answer('Введите номер уведомления для удаления')
    notification_map = {i+1: n.id for i, n in enumerate(notifications)}
    await state.update_data(notification_map=notification_map)
    await state.set_state(DeleteNotificationStates.waiting_index)


@dp.message(DeleteNotificationStates.waiting_index)
async def process_delete_index(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    notification_map = data.get('notification_map')
    try:
        notification_index = int(message.text)
        if notification_index not in notification_map:
            await message.answer(
                'Пожалуйста, введите корректный номер уведомления')
            return

        notification_id = notification_map[notification_index]

        con = sqlite3.connect(DATABASE_PATH)
        with con:
            cur = con.execute(
                SELECT_USER_NOTIFICATION_BY_ID,
                (notification_id, message.from_user.id)
            )
            if not cur.fetchone():
                await message.answer("Уведомление с таким номером не найдено")
                return

            con.execute(
                DELETE_NOTIFICATION,
                (message.from_user.id, notification_id)
            )
        con.close()
        await state.clear()
        await message.answer("Уведомление было успешно удалено!")

    except ValueError:
        await message.answer('Пожалуйста, введите корректное число')


def init_db() -> None:
    con = sqlite3.connect(DATABASE_PATH)
    with con:
        con.execute(CREATE_NOTIFICATIONS_TABLE)
    con.close()


async def monitor_sensors(bot: Bot) -> None:
    while True:
        current_temperature = get_temperature(ser)
        current_humidity = get_humidity(ser)

        con = sqlite3.connect(DATABASE_PATH)
        with con:
            cur = con.execute(SELECT_NOTIFICATIONS)
            notifications = tuple(
                Notification(*row) for row in cur.fetchall())
        con.close()

        for notification in notifications:
            user_id = notification.user_id
            parameter = notification.parameter
            condition = notification.condition
            value = notification.value

            match parameter:
                case 'temperature':
                    current = current_temperature
                case 'humidity':
                    current = current_humidity

            conditions = (
                condition == 'less' and current < value,
                condition == 'greater' and current > value,
                condition == 'equal' and current == value
            )

            if not any(conditions):
                continue

            id = notification.id
            message = f'Сработало уведомление ({id}) {notification}'
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
        BotCommand(command='deletenotification',
                   description='удалить уведомление'),
        BotCommand(command='cancel',
                   description='отменить операцию'),
    ]

    await bot.set_my_commands(commands)

    init_db()

    asyncio.create_task(monitor_sensors(bot))

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
