// CNC spindle tach display.
// Tach voltage on A5 (1 mV/rpm), warn lamp on D9, mute on D3.

const int TACH_PIN = A5;
const int WARN_PIN = 9;
const int MUTE_PIN = 3;
const float WARN_RPM = 2000.0f;
const unsigned long PERIOD_MS = 1000;
const unsigned long SAMPLE_MS = 50;

unsigned long lastPrint = 0;
unsigned long lastSample = 0;
float rpm = 0.0f;
float rpmMin = 99999.0f;
float rpmMax = 0.0f;
bool warnLit = false;

float readRpm()
{
    int raw = analogRead(TACH_PIN);
    return raw * (5000.0f / 1023.0f);
}

void trackExtremes(float v)
{
    if (v < rpmMin)
    {
        rpmMin = v;
    }
    if (v > rpmMax)
    {
        rpmMax = v;
    }
}

void updateWarn(float v)
{
    bool muted = (digitalRead(MUTE_PIN) == LOW);
    warnLit = (!muted) && (v >= WARN_RPM);
    digitalWrite(WARN_PIN, warnLit ? HIGH : LOW);
}

void printRpm(float v)
{
    Serial.print("RPM:");
    Serial.println(v, 0);
}

void setup()
{
    pinMode(WARN_PIN, OUTPUT);
    pinMode(MUTE_PIN, INPUT_PULLUP);
    digitalWrite(WARN_PIN, LOW);
    Serial.begin(9600);
    lastPrint = millis();
    lastSample = millis();
}

void loop()
{
    unsigned long now = millis();

    if (now - lastSample >= SAMPLE_MS)
    {
        lastSample = now;
        rpm = readRpm();
        trackExtremes(rpm);
        updateWarn(rpm);
    }

    if (now - lastPrint >= PERIOD_MS)
    {
        lastPrint = now;
        printRpm(rpm);
        Serial.print("spindle min=");
        Serial.print(rpmMin, 0);
        Serial.print(" max=");
        Serial.println(rpmMax, 0);
    }
}
