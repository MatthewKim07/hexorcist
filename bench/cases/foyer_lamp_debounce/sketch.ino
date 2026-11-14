// Foyer wall switch: one pushbutton toggles a lamp channel.
// Button D5 to ground (pull-up), lamp driver D11, status over serial.

const int SWITCH_PIN = 5;
const int LAMP_PIN = 11;
const unsigned long STATUS_EVERY_MS = 1500;

bool lampLit = false;
int previousRaw = HIGH;
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

bool isPressedEdge(int previous, int current)
{
    return previous == HIGH && current == LOW;
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
    previousRaw = digitalRead(SWITCH_PIN);
    lastStatusAt = millis();
    bootMs = millis();
}

void loop()
{
    int raw = digitalRead(SWITCH_PIN);

    if (isPressedEdge(previousRaw, raw))
    {
        flipLamp();
    }
    previousRaw = raw;

    unsigned long now = millis();
    if (now - lastStatusAt >= STATUS_EVERY_MS)
    {
        lastStatusAt = now;
        reportLamp();
    }
}
