// Tank mixer scheduler: 2 s of mixing in every 5 s cycle.
// Relay on D6, hold switch on D3 (pull-up).

const int MIXER_PIN = 6;
const int HOLD_PIN = 3;
const uint16_t RUN_MS = 2000;
const uint16_t CYCLE_MS = 5000;

uint16_t cycleStart = 0;
bool running = false;
unsigned int runCount = 0;

uint16_t tickNow()
{
    return (uint16_t)millis();
}

uint16_t sinceCycleStart(uint16_t now)
{
    return (uint16_t)(now - cycleStart);
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
    cycleStart = now;
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
    cycleStart = tickNow();
}

void loop()
{
    uint16_t now = tickNow();
    if (running)
    {
        if (sinceCycleStart(now) >= RUN_MS)
        {
            stopRun();
        }
    }
    else if (sinceCycleStart(now) >= CYCLE_MS)
    {
        startRun(now);
    }
    drive();
}
