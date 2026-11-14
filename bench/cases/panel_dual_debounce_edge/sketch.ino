// Control-panel key: toggles a status LED for the technician.
// Key on D2 (pull-up to Vcc, closes to ground), LED on D13.

const int KEY_PIN = 2;
const int LED_PIN = 13;
const unsigned long REPORT_MS = 1000;

bool ledLit = false;
int previous = HIGH;
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

bool risingEdge(int previousLevel, int currentLevel)
{
    return previousLevel == LOW && currentLevel == HIGH;
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
    previous = digitalRead(KEY_PIN);
    lastReport = millis();
    bootMs = millis();
}

void loop()
{
    int nowLevel = digitalRead(KEY_PIN);

    if (risingEdge(previous, nowLevel))
    {
        flipLed();
    }
    previous = nowLevel;

    unsigned long t = millis();
    if (t - lastReport >= REPORT_MS)
    {
        lastReport = t;
        report();
    }
}
