// Tank mixer scheduler: 2 s of mixing in every 5 s cycle.
// Relay on D6, hold switch on D3 (pull-up).

const int MIXER_PIN = 6;
const int HOLD_PIN = 3;
const uint16_t RUN_MS = 2000;
const uint16_t CYCLE_MS = 5000;

uint16_t nextRunAt = 0;
uint16_t stopRunAt = 0;
bool running = false;
unsigned int runCount = 0;

uint16_t tickNow()
{
    return (uint16_t)millis();
}

void announceRun()
{
    Serial.print("mix ");
    Serial.println(runCount);
}

void startRun(uint16_t now)
{
    running = true;
    runCount++;
    stopRunAt = now + RUN_MS;
    nextRunAt = now + CYCLE_MS;
    announceRun();
}

void stopRun()
{
    running = false;
}

bool held()
{
    return digitalRead(HOLD_PIN) == LOW;
}

void drive()
{
    bool on = running && !held();
    digitalWrite(MIXER_PIN, on ? HIGH : LOW);
}

void setup()
{
    pinMode(MIXER_PIN, OUTPUT);
    pinMode(HOLD_PIN, INPUT_PULLUP);
    digitalWrite(MIXER_PIN, LOW);
    Serial.begin(9600);
    nextRunAt = tickNow() + CYCLE_MS;
}

void loop()
{
    uint16_t now = tickNow();
    if (running)
    {
        if (now >= stopRunAt)
        {
            stopRun();
        }
    }
    else if (now >= nextRunAt)
    {
        startRun(now);
    }
    drive();
}
