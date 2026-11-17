// Stair light: one press lights the stairs for three seconds.
// Relay on D9, push button on D2, mode switch on D3 (both pull-up).

const int LIGHT_PIN = 9;
const int BUTTON_PIN = 2;
const int MODE_PIN = 3;
const unsigned long LIT_MS = 3000;
const unsigned long SETTLE_MS = 15;
const unsigned long REPORT_MS = 1000;

bool lit = false;
bool held = false;
int rawLevel = HIGH;
int lastMode = HIGH;
unsigned long rawChangedAt = 0;
unsigned long litSince = 0;
unsigned long lastReport = 0;

void armTimer()
{
    litSince = millis();
}

void lightOn()
{
    lit = true;
    armTimer();
    digitalWrite(LIGHT_PIN, HIGH);
}

void lightOff()
{
    lit = false;
    digitalWrite(LIGHT_PIN, LOW);
}

void onModeChange(int mode)
{
    lastMode = mode;
    if (lit)
    {
        armTimer();
    }
}

void scanButton()
{
    int level = digitalRead(BUTTON_PIN);
    unsigned long now = millis();
    if (level != rawLevel)
    {
        rawLevel = level;
        rawChangedAt = now;
    }
    if (now - rawChangedAt >= SETTLE_MS)
    {
        bool down = (rawLevel == LOW);
        if (down && !held && !lit)
        {
            lightOn();
        }
        held = down;
    }
}

void report()
{
    Serial.print("stair mode=");
    Serial.print(lastMode == HIGH ? 1 : 0);
    Serial.print(" lit=");
    Serial.println(lit ? 1 : 0);
}

void setup()
{
    pinMode(LIGHT_PIN, OUTPUT);
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(MODE_PIN, INPUT_PULLUP);
    digitalWrite(LIGHT_PIN, LOW);
    Serial.begin(9600);
    lastMode = digitalRead(MODE_PIN);
    rawChangedAt = millis();
    lastReport = millis();
}

void loop()
{
    scanButton();
    int mode = digitalRead(MODE_PIN);
    if (mode != lastMode)
    {
        onModeChange(mode);
    }
    if (lit && millis() - litSince >= LIT_MS)
    {
        lightOff();
    }
    if (millis() - lastReport >= REPORT_MS)
    {
        lastReport = millis();
        report();
    }
}
