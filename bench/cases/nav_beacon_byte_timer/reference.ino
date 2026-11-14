// Harbor nav beacon: 500 ms on / 500 ms off on D12.
// Quiet mode switch on D3 (pull-up). Status over UART.

const int BEACON_PIN = 12;
const int QUIET_PIN = 3;
const unsigned long HALF_MS = 500;
const unsigned long STATUS_MS = 2000;

bool lampOn = false;
unsigned long lastEdge = 0;
unsigned long lastStatus = 0;
unsigned long risingCount = 0;
bool quietHeld = false;

void setBeacon(bool on)
{
    lampOn = on;
    digitalWrite(BEACON_PIN, on ? HIGH : LOW);
}

void emitTick()
{
    Serial.println("tick");
    risingCount++;
}

void publishStatus()
{
    Serial.print("nav rises=");
    Serial.print(risingCount);
    Serial.print(" quiet=");
    Serial.println(quietHeld ? 1 : 0);
}

bool readQuiet()
{
    return digitalRead(QUIET_PIN) == LOW;
}

void setup()
{
    pinMode(BEACON_PIN, OUTPUT);
    pinMode(QUIET_PIN, INPUT_PULLUP);
    setBeacon(false);
    Serial.begin(9600);
    lastEdge = millis();
    lastStatus = millis();
}

void loop()
{
    quietHeld = readQuiet();
    unsigned long now = millis();

    if (quietHeld)
    {
        setBeacon(false);
        lastEdge = now;
    }
    else if (now - lastEdge >= HALF_MS)
    {
        lastEdge = now;
        bool nextOn = !lampOn;
        setBeacon(nextOn);
        if (nextOn)
        {
            emitTick();
        }
    }

    if (now - lastStatus >= STATUS_MS)
    {
        lastStatus = now;
        publishStatus();
    }
}
