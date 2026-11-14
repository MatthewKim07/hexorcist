// Foyer wall switch: one pushbutton toggles a lamp channel.
// Button D5 to ground (pull-up), lamp driver D11, status over serial.

const int SWITCH_PIN = 5;
const int LAMP_PIN = 11;
const unsigned long DEBOUNCE_MS = 40;
const unsigned long STATUS_EVERY_MS = 1500;

bool lampLit = false;
int stableLevel = HIGH;
int lastReading = HIGH;
unsigned long changeStarted = 0;
unsigned long lastStatusAt = 0;
unsigned long pressEvents = 0;
unsigned long bootMs = 0;

void driveLamp(bool on)
{
    lampLit = on;
    digitalWrite(LAMP_PIN, on ? HIGH : LOW);
}

void flipLamp()
{
    driveLamp(!lampLit);
    pressEvents++;
}

void reportLamp()
{
    Serial.print("foyer lamp=");
    Serial.println(lampLit ? "ON" : "OFF");
}

void setup()
{
    pinMode(SWITCH_PIN, INPUT_PULLUP);
    pinMode(LAMP_PIN, OUTPUT);
    driveLamp(false);
    Serial.begin(9600);
    stableLevel = digitalRead(SWITCH_PIN);
    lastReading = stableLevel;
    lastStatusAt = millis();
    bootMs = millis();
}

void loop()
{
    int raw = digitalRead(SWITCH_PIN);
    unsigned long now = millis();

    if (raw != lastReading)
    {
        changeStarted = now;
        lastReading = raw;
    }

    if ((now - changeStarted) >= DEBOUNCE_MS && raw != stableLevel)
    {
        stableLevel = raw;
        if (stableLevel == LOW)
        {
            flipLamp();
        }
    }

    if (now - lastStatusAt >= STATUS_EVERY_MS)
    {
        lastStatusAt = now;
        reportLamp();
    }
}
