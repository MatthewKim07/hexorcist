// Shop bench run/stop: mushroom estop toggles the "machine armed" lamp.
// Estop contact on D6 (NC to ground via switch, pull-up), armed lamp on D9.

const uint8_t ESTOP_PIN = 6;
const uint8_t ARMED_PIN = 9;
const unsigned long SETTLE_MS = 50;
const unsigned long BEAT_MS = 1200;

bool armed = false;
uint8_t stable = HIGH;
uint8_t lastSeen = HIGH;
unsigned long edgeAt = 0;
unsigned long lastBeat = 0;
unsigned long pressCount = 0;
unsigned long bootMs = 0;

void writeArmed(bool level)
{
    armed = level;
    digitalWrite(ARMED_PIN, level ? HIGH : LOW);
}

void toggleArmed()
{
    writeArmed(!armed);
    pressCount++;
}

void heartbeat()
{
    Serial.print("shop armed=");
    Serial.print(armed ? 1 : 0);
    Serial.print(" presses=");
    Serial.println(pressCount);
}

void setup()
{
    pinMode(ESTOP_PIN, INPUT_PULLUP);
    pinMode(ARMED_PIN, OUTPUT);
    writeArmed(false);
    Serial.begin(9600);
    stable = digitalRead(ESTOP_PIN);
    lastSeen = stable;
    lastBeat = millis();
    bootMs = millis();
}

void loop()
{
    uint8_t sample = digitalRead(ESTOP_PIN);
    unsigned long now = millis();

    if (sample != lastSeen)
    {
        edgeAt = now;
        lastSeen = sample;
    }

    if ((now - edgeAt) >= SETTLE_MS && sample != stable)
    {
        stable = sample;
        if (stable == LOW)
        {
            toggleArmed();
        }
    }

    if (now - lastBeat >= BEAT_MS)
    {
        lastBeat = now;
        heartbeat();
    }
}
