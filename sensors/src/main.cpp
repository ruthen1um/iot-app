#include <Arduino.h>
#include <HTU21D.h>

HTU21D sensor;

unsigned long previousMillis = 0;
const unsigned long interval = 60000;  // 60 секунд

void setup() {
    Serial.begin(9600);
    sensor.begin();
}

void loop() {
    unsigned long currentMillis = millis();
    if (currentMillis - previousMillis >= interval) {
        previousMillis = currentMillis;

        if (sensor.measure()) {
            float temperature = sensor.getTemperature();
            float humidity = sensor.getHumidity();

            Serial.print("T:");
            Serial.println(temperature, 2);
            Serial.print("H:");
            Serial.println(humidity, 2);
        }
    }
}
