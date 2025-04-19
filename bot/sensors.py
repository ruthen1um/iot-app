import serial
import serial.tools.list_ports
import time

SENSORS_READ_DELAY = 60

_last_temperature = None
_last_humidity = None
_last_read_time = 0


def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if any(
            substr in port.description
            for substr in ("Arduino", "USB-SERIAL", "CH340")
        ):
            return port.device
    return None


def _update_sensor_data(ser: serial.Serial):
    global _last_temperature, _last_humidity, _last_read_time

    current_time = time.time()
    if current_time - _last_read_time >= SENSORS_READ_DELAY:
        ser.reset_input_buffer()
        temperature = None
        humidity = None

        for _ in range(10):
            line = ser.readline().decode('utf-8').strip()
            if line.startswith("T:"):
                temperature = float(line[2:])
            elif line.startswith("H:"):
                humidity = float(line[2:])
            if temperature is not None and humidity is not None:
                break

        _last_temperature = temperature if temperature else _last_temperature
        _last_humidity = humidity if humidity else _last_humidity
        _last_read_time = current_time


def get_temperature(ser: serial.Serial) -> float:
    _update_sensor_data(ser)
    return _last_temperature


def get_humidity(ser: serial.Serial) -> float:
    _update_sensor_data(ser)
    return _last_humidity
