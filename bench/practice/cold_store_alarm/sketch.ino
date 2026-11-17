// Cold-store alarm: relay on D10 follows the probe on A1.
// Three high samples in a row raise it, a clearly low sample clears it.

const int PROBE_PIN = A1;
const int ALARM_PIN = 10;
const float RAISE_C = 12.0;
const float CLEAR_C = 8.0;
const int RUN_NEEDED = 3;
const unsigned long SAMPLE_MS = 20;
const unsigned long REPORT_MS = 500;

float lastC = 0.0;
int highRun = 0;
bool alarmOn = false;
unsigned long lastSample = 0;
unsigned long lastReport = 0;

float readCelsius()
{
    int raw = analogRead(PROBE_PIN);
    return (raw * 5000.0 / 1023.0 - 500.0) / 10.0;
}

void setAlarm(bool on)
{
    alarmOn = on;
    digitalWrite(ALARM_PIN, on ? HIGH : LOW);
}

void evaluate(float c)
{
    lastC = c;
    if (c >= RAISE_C)
    {
        if (highRun < RUN_NEEDED)
        {
            highRun++;
        }
        if (highRun >= RUN_NEEDED)
        {
            setAlarm(true);
        }
    }
    else if (c <= CLEAR_C)
    {
        highRun = 0;
        setAlarm(false);
    }
}

void report()
{
    Serial.print("cold ");
    Serial.print(lastC, 1);
    Serial.print(" C alarm=");
    Serial.println(alarmOn ? 1 : 0);
}

void setup()
{
    pinMode(ALARM_PIN, OUTPUT);
    digitalWrite(ALARM_PIN, LOW);
    Serial.begin(9600);
    lastC = readCelsius();
    lastSample = millis();
    lastReport = millis();
}

void loop()
{
    unsigned long now = millis();
    if (now - lastSample >= SAMPLE_MS)
    {
        lastSample = now;
        evaluate(readCelsius());
    }
    if (now - lastReport >= REPORT_MS)
    {
        lastReport = now;
        report();
    }
}
