// Shop hoist contactor with mushroom e-stop.
// E-stop on D3 (NC to ground via switch, pull-up), contactor on D5.
// Run request on D6 (pull-up).

const int ESTOP_PIN = 3;
const int CONTACTOR_PIN = 5;
const int RUN_PIN = 6;
const unsigned long SETTLE_MS = 30;
const unsigned long BEAT_MS = 1100;

int stableStop = HIGH;
int lastStop = HIGH;
unsigned long stopEdge = 0;
bool contactorOn = false;
unsigned long lastBeat = 0;
unsigned long tripCount = 0;

bool estopActive(int level)
{
    return level == LOW;
}

void setContactor(bool on)
{
    contactorOn = on;
    digitalWrite(CONTACTOR_PIN, on ? HIGH : LOW);
}

void heartbeat()
{
    Serial.print("hoist run=");
    Serial.print(contactorOn ? 1 : 0);
    Serial.print(" trips=");
    Serial.println(tripCount);
}

void setup()
{
    pinMode(ESTOP_PIN, INPUT_PULLUP);
    pinMode(RUN_PIN, INPUT_PULLUP);
    pinMode(CONTACTOR_PIN, OUTPUT);
    setContactor(false);
    Serial.begin(9600);
    stableStop = digitalRead(ESTOP_PIN);
    lastStop = stableStop;
    lastBeat = millis();
}

void loop()
{
    unsigned long now = millis();
    int raw = digitalRead(ESTOP_PIN);

    if (raw != lastStop)
    {
        stopEdge = now;
        lastStop = raw;
    }

    if ((now - stopEdge) >= SETTLE_MS && raw != stableStop)
    {
        if (estopActive(raw) && !estopActive(stableStop))
        {
            tripCount++;
        }
        stableStop = raw;
    }

    bool stopped = estopActive(stableStop);
    bool runReq = (digitalRead(RUN_PIN) == LOW);

    if (stopped)
    {
        setContactor(false);
    }
    else if (runReq)
    {
        setContactor(true);
    }
    else
    {
        setContactor(true);
    }

    if (now - lastBeat >= BEAT_MS)
    {
        lastBeat = now;
        heartbeat();
    }
}
