from os import getenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

import serial
import serial.tools.list_ports
import time

PORT = "C3"  


last_temperature = None
last_humidity = None
last_read_time = 

def _update_sensor_data():
    global last_temperature, last_humidity, last_read_time

    current_time = time.time()
    if current_time - last_read_time >= 60:
        ser.reset_input_buffer()
        temp = None
        hum = None

        for _ in range(10):  
            try:
                line = ser.readline().decode('utf-8').strip()
                if line.startswith("T:"):
                    temp = float(line[2:])
                elif line.startswith("H:"):
                    hum = float(line[2:])
                if temp is not None and hum is not None:
                    break
            except Exception:
                continue

        if temp is not None:
            last_temperature = temp
        if hum is not None:
            last_humidity = hum
        last_read_time = current_time

def get_temperature() -> float:
    _update_sensor_data()
    return last_temperature

def get_humidity() -> float:
    _update_sensor_data()
    return last_humidity





TOKEN = getenv('TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Привет. Это WeatherGoidaBot")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    application.run_polling()
