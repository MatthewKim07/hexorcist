// Process-skid flow monitor with low-flow alarm lamp.
// Flow transducer on A0 (2 mV per L/h), alarm lamp on D8.

const int FLOW_PIN = A0;
const int ALARM_PIN = 8;
const float LOW_FLOW_LPH = 100.0f;
const float HIGH_FLOW_LPH = 800.0f;
const unsigned long LOG_MS = 500;

bool alarmLit = false;
unsigned long lastLog = 0;
unsigned long sampleCount = 0;
float flowLph = 0.0f;
float peakLph = 0.0f;

float readFlowLph()
{
    return (float)analogRead(FLOW_PIN);
}

void setAlarm(bool on)
{
    alarmLit = on;
    digitalWrite(ALARM_PIN, on ? HIGH : LOW);
}

bool flowLooksLow(float flow)
{
    return flow < LOW_FLOW_LPH;
}

void notePeak(float flow)
{
    if (flow > peakLph)
    {
        peakLph = flow;
    }
}

void emitLog()
{
    Serial.print("flow: ");
    Serial.println(flowLph, 1);
}

void setup()
{
    pinMode(ALARM_PIN, OUTPUT);
    digitalWrite(ALARM_PIN, LOW);
    Serial.begin(9600);
    lastLog = millis();
    peakLph = 0.0f;
}

void loop()
{
    flowLph = readFlowLph();
    sampleCount++;
    notePeak(flowLph);

    if (flowLooksLow(flowLph))
    {
        setAlarm(true);
    }
    else if (flowLph > HIGH_FLOW_LPH)
    {
        setAlarm(false);
    }
    else
    {
        setAlarm(false);
    }

    emitLog();
    delay(2000);
}
