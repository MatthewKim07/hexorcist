// Patio weather node: TMP36 logger with hold-to-freeze button.
// TMP36 on A0 (10 mV/°C + 500 mV), freeze button on D5, range lamp on D7.

const int TEMP_PIN = A0;
const int FREEZE_PIN = 5;
const int RANGE_PIN = 7;
const float MV_PER_C = 10.0f;
const float OFFSET_MV = 500.0f;
const float LOW_C = -10.0f;
const float HIGH_C = 50.0f;
const unsigned long PERIOD_MS = 1000;

unsigned long lastPrint = 0;
float tempC = 0.0f;
float frozenC = 0.0f;
bool freezeHeld = false;
unsigned long samples = 0;

float readTempC()
{
    int raw = analogRead(TEMP_PIN);
    float volts = raw * (5.0f / 1023.0f);
    return (volts - (OFFSET_MV / 1000.0f)) * 100.0f;
}

void updateRangeLamp(float c)
{
    bool ok = (c >= LOW_C) && (c <= HIGH_C);
    digitalWrite(RANGE_PIN, ok ? LOW : HIGH);
}

void printTemp(float c)
{
    Serial.print("temp=");
    Serial.println(c, 1);
}

void setup()
{
    pinMode(FREEZE_PIN, INPUT_PULLUP);
    pinMode(RANGE_PIN, OUTPUT);
    digitalWrite(RANGE_PIN, LOW);
    Serial.begin(9600);
    lastPrint = millis();
}

void loop()
{
    tempC = readTempC();
    samples++;
    freezeHeld = (digitalRead(FREEZE_PIN) == LOW);
    if (freezeHeld)
    {
        frozenC = tempC;
    }

    float report = freezeHeld ? frozenC : tempC;
    updateRangeLamp(report);

    unsigned long now = millis();
    if (now - lastPrint >= PERIOD_MS)
    {
        lastPrint = now;
        printTemp(report);
        Serial.print("weather n=");
        Serial.println(samples);
    }
}
