// Safe-deposit vault lock latch.
// Request button on D2, door-closed sense on D3 (both pull-up), lock solenoid on D9.

const int REQ_PIN = 2;
const int DOOR_PIN = 3;
const int LOCK_PIN = 9;
const unsigned long DEBOUNCE_MS = 35;
const unsigned long STATUS_MS = 1000;

bool locked = false;
int stableReq = HIGH;
int lastReq = HIGH;
unsigned long reqEdge = 0;
unsigned long lastStatus = 0;
unsigned long engageCount = 0;

void setLock(bool on)
{
    locked = on;
    digitalWrite(LOCK_PIN, on ? HIGH : LOW);
}

void publishStatus()
{
    Serial.print("vault lock=");
    Serial.print(locked ? 1 : 0);
    Serial.print(" engages=");
    Serial.println(engageCount);
}

bool doorClosed()
{
    return digitalRead(DOOR_PIN) == LOW;
}

void setup()
{
    pinMode(REQ_PIN, INPUT_PULLUP);
    pinMode(DOOR_PIN, INPUT_PULLUP);
    pinMode(LOCK_PIN, OUTPUT);
    setLock(false);
    Serial.begin(9600);
    stableReq = digitalRead(REQ_PIN);
    lastReq = stableReq;
    lastStatus = millis();
}

void loop()
{
    unsigned long now = millis();
    int raw = digitalRead(REQ_PIN);

    if (raw != lastReq)
    {
        reqEdge = now;
        lastReq = raw;
    }

    if ((now - reqEdge) >= DEBOUNCE_MS && raw != stableReq)
    {
        stableReq = raw;
        if (stableReq == LOW && doorClosed() && !locked)
        {
            setLock(true);
            engageCount++;
        }
    }

    if (!doorClosed())
    {
        setLock(false);
    }

    if (now - lastStatus >= STATUS_MS)
    {
        lastStatus = now;
        publishStatus();
    }
}
