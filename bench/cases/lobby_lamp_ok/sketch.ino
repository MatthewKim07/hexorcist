// Lobby accent lamp toggle with contact settle.
// Momentary switch on D3 (pull-up), lamp channel on D12.

const uint8_t BTN_PIN = 3;
const uint8_t LAMP_PIN = 12;
const unsigned long SETTLE_MS = 45;
const unsigned long STATUS_MS = 1400;

bool lampOn = false;
uint8_t stable = HIGH;
uint8_t lastRaw = HIGH;
unsigned long edgeMs = 0;
unsigned long statusMs = 0;
unsigned long toggles = 0;

void setLamp(bool on)
{
    lampOn = on;
    digitalWrite(LAMP_PIN, on ? HIGH : LOW);
}

void toggleLamp()
{
    setLamp(!lampOn);
    toggles++;
}

void printStatus()
{
    Serial.print("lobby lamp=");
    Serial.print(lampOn ? "ON" : "OFF");
    Serial.print(" n=");
    Serial.println(toggles);
}

void setup()
{
    pinMode(BTN_PIN, INPUT_PULLUP);
    pinMode(LAMP_PIN, OUTPUT);
    setLamp(false);
    Serial.begin(9600);
    stable = digitalRead(BTN_PIN);
    lastRaw = stable;
    statusMs = millis();
}

void loop()
{
    uint8_t raw = digitalRead(BTN_PIN);
    unsigned long now = millis();

    if (raw != lastRaw)
    {
        edgeMs = now;
        lastRaw = raw;
    }

    if ((now - edgeMs) >= SETTLE_MS && raw != stable)
    {
        stable = raw;
        if (stable == LOW)
        {
            toggleLamp();
        }
    }

    if (now - statusMs >= STATUS_MS)
    {
        statusMs = now;
        printStatus();
    }
}
