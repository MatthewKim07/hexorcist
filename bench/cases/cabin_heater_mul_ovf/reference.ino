// Cabin heater enable with comfort band.
// LM35 on A0, heater relay on D9, frost override on D2 (pull-up).

const int TEMP_PIN = A0;
const int HEAT_PIN = 9;
const int FROST_PIN = 2;
const float HEAT_ON_C = 18.0f;
const float HEAT_OFF_C = 22.0f;
const float MV_PER_C = 10.0f;
const unsigned long SAMPLE_MS = 50;
const unsigned long STATUS_MS = 1000;

bool heaterOn = false;
unsigned long lastSample = 0;
unsigned long lastStatus = 0;
float lastC = 0.0f;

float readCabinC()
{
    long mv = analogRead(TEMP_PIN) * 5000L / 1023;
    return mv / MV_PER_C;
}

void applyHeater(bool on)
{
    heaterOn = on;
    digitalWrite(HEAT_PIN, on ? HIGH : LOW);
}

void publishStatus()
{
    Serial.print("cabin: ");
    Serial.print(lastC, 1);
    Serial.print(" C heat=");
    Serial.println(heaterOn ? "ON" : "OFF");
}

void setup()
{
    pinMode(HEAT_PIN, OUTPUT);
    pinMode(FROST_PIN, INPUT_PULLUP);
    applyHeater(false);
    Serial.begin(9600);
    lastSample = millis();
    lastStatus = millis();
}

void loop()
{
    unsigned long now = millis();

    if (now - lastSample >= SAMPLE_MS)
    {
        lastSample = now;
        lastC = readCabinC();
        bool frost = (digitalRead(FROST_PIN) == LOW);

        if (frost)
        {
            applyHeater(true);
        }
        else if (lastC < HEAT_ON_C)
        {
            applyHeater(true);
        }
        else if (lastC > HEAT_OFF_C)
        {
            applyHeater(false);
        }
    }

    if (now - lastStatus >= STATUS_MS)
    {
        lastStatus = now;
        publishStatus();
    }
}
