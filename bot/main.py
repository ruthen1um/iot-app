from os import getenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

import serial  
ser = serial.Serial('COM5', 9600, timeout=1)  

TOKEN = getenv('TOKEN')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Привет. Это WeatherGoidaBot")



async def get_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ser.reset_input_buffer()  

    temperature = None
    humidity = None

    for _ in range(10):  
        line = ser.readline().decode('utf-8').strip()
        if "Temperature" in line:
            temperature = line
        elif "Humidity" in line:
            humidity = line
        if temperature and humidity:
            break

    if temperature and humidity:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"{temperature}\n{humidity}")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Не удалось получить данные")


if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    get_handler = CommandHandler('get', get_weather)
    application.add_handler(get_handler)

    application.run_polling()
