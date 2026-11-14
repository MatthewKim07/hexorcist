// Control-panel key: toggles a status LED for the technician.
// Key on D2 (pull-up to Vcc, closes to ground), LED on D13.

const int KEY_PIN = 2;
const int LED_PIN = 13;
const unsigned long SETTLE_MS = 40;
const unsigned long REPORT_MS = 1000;

bool ledLit = false;
int stable = HIGH;
int lastSeen = HIGH;
unsigned long changedAt = 0;
unsigned long lastReport = 0;
unsigned long edgeCount = 0;
unsigned long bootMs = 0;

void writeLed(bool on)
{
    ledLit = on;
    digitalWrite(LED_PIN, on ? HIGH : LOW);
}

void flipLed()
{
    writeLed(!ledLit);
    edgeCount++;
}

void report()
{
    Serial.print("panel led=");
    Serial.print(ledLit ? 1 : 0);
    Serial.print(" edges=");
    Serial.println(edgeCount);
}

void setup()
{
    pinMode(KEY_PIN, INPUT_PULLUP);
    pinMode(LED_PIN, OUTPUT);
    writeLed(false);
    Serial.begin(9600);
    stable = digitalRead(KEY_PIN);
    lastSeen = stable;
    lastReport = millis();
    bootMs = millis();
}

void loop()
{
    int nowLevel = digitalRead(KEY_PIN);
    unsigned long t = millis();

    if (nowLevel != lastSeen)
    {
        changedAt = t;
        lastSeen = nowLevel;
    }

    if ((t - changedAt) >= SETTLE_MS && nowLevel != stable)
    {
        stable = nowLevel;
        if (stable == LOW)
        {
            flipLed();
        }
    }

    if (t - lastReport >= REPORT_MS)
    {
        lastReport = t;
        report();
    }
}
