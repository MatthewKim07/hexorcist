// Reef tank pH logger.
// Linearized probe on A0, optional low-pH LED on D13, UART log at 9600.

const int PROBE_PIN = A0;
const int ALERT_PIN = 13;
const float ALERT_PH = 7.20f;
const unsigned long LOG_PERIOD_MS = 1000;

unsigned long lastLogMs = 0;
unsigned long sampleCount = 0;
float lastPh = 0.0f;
float phMin = 14.0f;
float phMax = 0.0f;
bool alertOn = false;

float adcToMillivolts(int raw)
{
    return raw * (5000.0f / 1023.0f);
}

float computePh(float millivolts)
{
    return millivolts;
}

void trackRange(float ph)
{
    if (ph < phMin)
    {
        phMin = ph;
    }
    if (ph > phMax)
    {
        phMax = ph;
    }
}

void setAlert(bool on)
{
    alertOn = on;
    digitalWrite(ALERT_PIN, on ? HIGH : LOW);
}

void writeLogLine()
{
    Serial.print("pH: ");
    Serial.println(lastPh, 2);
}

void setup()
{
    pinMode(ALERT_PIN, OUTPUT);
    digitalWrite(ALERT_PIN, LOW);
    Serial.begin(9600);
    lastLogMs = millis();
}

void loop()
{
    int raw = analogRead(PROBE_PIN);
    float mv = adcToMillivolts(raw);
    lastPh = computePh(mv);
    sampleCount++;
    trackRange(lastPh);

    if (lastPh < ALERT_PH)
    {
        setAlert(true);
    }
    else
    {
        setAlert(false);
    }

    unsigned long now = millis();
    if (now - lastLogMs >= LOG_PERIOD_MS)
    {
        lastLogMs = now;
        writeLogLine();
    }
}
