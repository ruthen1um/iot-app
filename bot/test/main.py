import asyncio
import sqlite3
from datetime import datetime
from dataclasses import dataclass
from serial import Serial
from dotenv import dotenv_values

from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import (
    Command,
    StateFilter,
    and_f
)
from aiogram.types import (
    Message,
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from sensors import get_temperature, get_humidity

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


@dataclass
class Config:
    token: str
    port: int
    database_path: str
    check_interval: int

    @classmethod
    def from_env(cls):
        variables = dotenv_values()
        return cls(
            token=variables.get('TOKEN'),
            port=variables.get('PORT'),
            database_path=variables.get('DATABASE_PATH'),
            check_interval=variables.get('CHECK_INTERVAL'),
        )


class SensorBot:
    def __init__(self, token, ser, database_path):
        self.bot = Bot(token=token)
        self.ser = ser
        self.database_path = database_path
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)

        self._setup_commands()
        self.init_db()
        self.register_handlers()

    def _setup_commands(self):
        self.commands = [
            BotCommand(command='start', description='начать работу с ботом'),
            BotCommand(command='temperature',
                       description='текущая температура'),
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

    def init_db(self):
        con = sqlite3.connect(self.database_path)
        with con:
            con.execute(CREATE_NOTIFICATIONS_TABLE)
        con.close()

    def register_handlers(self):
        self.dp.message(
            and_f(StateFilter(None), Command('start'))
        )(self.start)

        self.dp.message(Command('cancel'))(self.cancel)

        self.dp.message(
            and_f(StateFilter(None), Command('temperature'))
        )(self.temperature)

        self.dp.message(
            and_f(StateFilter(None), Command('humidity'))
        )(self.humidity)

        self.dp.message(
            and_f(StateFilter(None), Command('notifications'))
        )(self.notifications)

        self.dp.message(
            and_f(StateFilter(None), Command('setnotification'))
        )(self.setnotification)

        self.dp.callback_query(
            SetNotificationStates.waiting_parameter
        )(self.process_parameter)

        self.dp.callback_query(
            SetNotificationStates.waiting_condition
        )(self.process_condition)

        self.dp.message(
            SetNotificationStates.waiting_value
        )(self.process_value)

        self.dp.message(
            and_f(StateFilter(None), Command('deletenotification'))
        )(self.deletenotification)

        self.dp.message(
            DeleteNotificationStates.waiting_index
        )(self.process_delete_index)

    async def start_polling(self):
        await self.bot.set_my_commands(self.commands)
        await self.dp.start_polling(self.bot)

    async def start(
        self,
        message: Message,
        state: FSMContext
    ) -> None:
        await message.answer(START_MESSAGE)

    async def cancel(
        self,
        message: Message,
        state: FSMContext
    ) -> None:
        current_state = await state.get_state()
        if current_state is None:
            await message.answer('Сейчас не выполняется ни одна операция')
        else:
            await state.clear()
            await message.answer('Операция отменена')

    async def temperature(
        self,
        message: Message,
        state: FSMContext
    ) -> None:
        temperature = get_temperature(self.ser)
        await message.answer(f'Текущее значение температуры: {temperature}')

    async def humidity(
        self,
        message: Message,
        state: FSMContext
    ) -> None:
        humidity = get_humidity(self.ser)
        await message.answer(f'Текущее значение влажности: {humidity}')

    async def notifications(
        self,
        message: Message,
        state: FSMContext
    ) -> None:
        con = sqlite3.connect(self.database_path)
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

    async def setnotification(
        self,
        message: Message,
        state: FSMContext
    ) -> None:
        await message.answer(
            'Выберите параметр для уведомления:',
            reply_markup=PARAMETERS_MARKUP
        )
        await state.set_state(SetNotificationStates.waiting_parameter)

    async def process_parameter(
        self,
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

    async def process_condition(
        self,
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

    async def process_value(
        self,
        message: Message,
        state: FSMContext
    ) -> None:
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

            con = sqlite3.connect(self.database_path)
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

    async def deletenotification(
        self,
        message: Message,
        state: FSMContext
    ) -> None:
        con = sqlite3.connect(self.database_path)
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

    async def process_delete_index(
        self,
        message: Message,
        state: FSMContext
    ) -> None:
        data = await state.get_data()
        notification_map = data.get('notification_map')
        try:
            notification_index = int(message.text)
            if notification_index not in notification_map:
                await message.answer(
                    'Пожалуйста, введите корректный номер уведомления')
                return

            notification_id = notification_map[notification_index]

            con = sqlite3.connect(self.database_path)
            with con:
                cur = con.execute(
                    SELECT_USER_NOTIFICATION_BY_ID,
                    (notification_id, message.from_user.id)
                )
                if not cur.fetchone():
                    await message.answer(
                        'Уведомление с таким номером не найдено')
                    return

                con.execute(
                    DELETE_NOTIFICATION,
                    (message.from_user.id, notification_id)
                )
            con.close()
            await state.clear()
            await message.answer('Уведомление было успешно удалено!')

        except ValueError:
            await message.answer('Пожалуйста, введите корректное число')

    async def port_not_open(self, error) -> None:
        print(error)


async def monitor_sensors(
    bot: Bot,
    database_path,
    check_interval
) -> None:
    while True:
        current_temperature = get_temperature()
        current_humidity = get_humidity()

        con = sqlite3.connect(database_path)
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

            message = f'Сработало уведомление {notification}'
            await bot.send_message(user_id, message)

        await asyncio.sleep(int(check_interval))


async def main() -> None:
    config = Config.from_env()
    ser = Serial(config.port)
    bot = SensorBot(
        token=config.token,
        ser=ser,
        database_path=config.database_path
    )

    asyncio.create_task(
        monitor_sensors(
            bot.bot,
            config.database_path,
            config.check_interval
        )
    )
    await bot.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
