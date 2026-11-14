// Shop bench run/stop: mushroom estop toggles the "machine armed" lamp.
// Estop contact on D6 (NC to ground via switch, pull-up), armed lamp on D9.

const uint8_t ESTOP_PIN = 6;
const uint8_t ARMED_PIN = 9;
const unsigned long BEAT_MS = 1200;

bool armed = false;
uint8_t priorSample = HIGH;
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

bool fallingEdge(uint8_t previous, uint8_t current)
{
    return previous == HIGH && current == LOW;
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
    priorSample = digitalRead(ESTOP_PIN);
    lastBeat = millis();
    bootMs = millis();
}

void loop()
{
    uint8_t sample = digitalRead(ESTOP_PIN);

    if (fallingEdge(priorSample, sample))
    {
        toggleArmed();
    }
    priorSample = sample;

    unsigned long now = millis();
    if (now - lastBeat >= BEAT_MS)
    {
        lastBeat = now;
        heartbeat();
    }
}
