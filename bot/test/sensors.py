import time
import random

SENSORS_READ_DELAY = 1

_last_temperature = None
_last_humidity = None
_last_read_time = 0


def find_arduino_port():
    return None


def _generate_fake_sensor_data():
    temperature = round(random.uniform(18.0, 30.0), 1)
    humidity = round(random.uniform(30.0, 70.0), 1)
    return temperature, humidity


def _update_sensor_data(_=None):
    global _last_temperature, _last_humidity, _last_read_time

    current_time = time.time()
    if current_time - _last_read_time >= SENSORS_READ_DELAY:
        temperature, humidity = _generate_fake_sensor_data()

        _last_temperature = temperature
        _last_humidity = humidity
        _last_read_time = current_time


def get_temperature(_=None) -> float:
    _update_sensor_data()
    return _last_temperature


def get_humidity(_=None) -> float:
    _update_sensor_data()
    return _last_humidity
