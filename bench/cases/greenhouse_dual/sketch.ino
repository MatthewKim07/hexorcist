// Greenhouse ridge-vent controller.
// Soil-air LM35 on A2, exhaust fan relay on D9, UART status.

const int SENSOR_PIN = A2;
const int FAN_PIN = 9;
const float OPEN_C = 28.0f;
const float MV_PER_C = 10.0f;
const unsigned long TICK_MS = 50;
const unsigned long STATUS_MS = 1000;

bool fanOn = false;
unsigned long lastTick = 0;
unsigned long lastStatus = 0;
unsigned long sampleCount = 0;
float tempC = 0.0f;
float tempMin = 999.0f;
float tempMax = -999.0f;

float readTempC()
{
    int raw = analogRead(SENSOR_PIN);
    float mv = raw * (5000.0f / 1023.0f);
    return mv / MV_PER_C;
}

void trackTemp(float c)
{
    if (c < tempMin)
    {
        tempMin = c;
    }
    if (c > tempMax)
    {
        tempMax = c;
    }
}

void setFan(bool on)
{
    fanOn = on;
    digitalWrite(FAN_PIN, on ? HIGH : LOW);
}

void printStatus()
{
    Serial.print("gh: ");
    Serial.print(tempC, 1);
    Serial.print(" C fan=");
    Serial.println(fanOn ? "ON" : "OFF");
}

void setup()
{
    pinMode(FAN_PIN, OUTPUT);
    digitalWrite(FAN_PIN, LOW);
    Serial.begin(9600);
    lastTick = millis();
    lastStatus = millis();
}

void loop()
{
    unsigned long now = millis();

    if (now - lastTick >= TICK_MS)
    {
        lastTick = now;
        tempC = readTempC();
        sampleCount++;
        trackTemp(tempC);

        if (tempC >= OPEN_C)
        {
            setFan(true);
        }
        else
        {
            setFan(false);
        }
    }

    if (now - lastStatus >= STATUS_MS)
    {
        lastStatus = now;
        printStatus();
    }
}
