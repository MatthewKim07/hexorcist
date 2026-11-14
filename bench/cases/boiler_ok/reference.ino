// Small boiler gas-valve thermostat (known-good build).
// Probe on A1 (10 mV/°C), gas valve on D6, lockout key on D3.

const int TEMP_PIN = A1;
const int VALVE_PIN = 6;
const int LOCK_PIN = 3;
const float FIRE_ON_C = 70.0f;
const float FIRE_OFF_C = 75.0f;
const float FAULT_LOW_C = 5.0f;
const float FAULT_HIGH_C = 120.0f;
const float MV_PER_C = 10.0f;
const unsigned long TICK_MS = 40;
const unsigned long STATUS_MS = 1000;

bool firing = false;
unsigned long lastTick = 0;
unsigned long lastStatus = 0;
float tempC = 0.0f;

float readBoilerC()
{
    int raw = analogRead(TEMP_PIN);
    float mv = raw * (5000.0f / 1023.0f);
    return mv / MV_PER_C;
}

void setValve(bool openValve)
{
    firing = openValve;
    digitalWrite(VALVE_PIN, openValve ? HIGH : LOW);
}

void printStatus()
{
    Serial.print("boiler: ");
    Serial.print(tempC, 1);
    Serial.print(" C valve=");
    Serial.println(firing ? "OPEN" : "SHUT");
}

void setup()
{
    pinMode(VALVE_PIN, OUTPUT);
    pinMode(LOCK_PIN, INPUT_PULLUP);
    setValve(false);
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
        tempC = readBoilerC();
        bool locked = (digitalRead(LOCK_PIN) == LOW);
        bool fault = (tempC < FAULT_LOW_C) || (tempC > FAULT_HIGH_C);

        if (locked || fault)
        {
            setValve(false);
        }
        else if (tempC < FIRE_ON_C)
        {
            setValve(true);
        }
        else if (tempC > FIRE_OFF_C)
        {
            setValve(false);
        }
    }

    if (now - lastStatus >= STATUS_MS)
    {
        lastStatus = now;
        printStatus();
    }
}
