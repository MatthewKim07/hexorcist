// Greenhouse nutrient drip pulse scheduler.
// Pulse driver on D8, pause button on D4 (pull-up).

const int DRIP_PIN = 8;
const int PAUSE_PIN = 4;
const byte PERIOD_MS = 800;
const unsigned long PULSE_MS = 50;
const unsigned long LOG_MS = 1600;

uint8_t nextDue = 0;
unsigned long pulseUntil = 0;
unsigned long lastLog = 0;
unsigned long dripCount = 0;
bool pulsing = false;
bool paused = false;

void dripHigh()
{
    digitalWrite(DRIP_PIN, HIGH);
}

void dripLow()
{
    digitalWrite(DRIP_PIN, LOW);
}

void startPulse(unsigned long now)
{
    pulsing = true;
    pulseUntil = now + PULSE_MS;
    dripHigh();
    dripCount++;
    Serial.println("drip");
}

void endPulse()
{
    pulsing = false;
    dripLow();
}

void printLog()
{
    Serial.print("drip n=");
    Serial.print(dripCount);
    Serial.print(" pause=");
    Serial.println(paused ? 1 : 0);
}

void setup()
{
    pinMode(DRIP_PIN, OUTPUT);
    pinMode(PAUSE_PIN, INPUT_PULLUP);
    dripLow();
    Serial.begin(9600);
    nextDue = (uint8_t)(millis() + PERIOD_MS);
    lastLog = millis();
}

void loop()
{
    unsigned long now = millis();
    uint8_t now8 = (uint8_t)now;
    paused = (digitalRead(PAUSE_PIN) == LOW);

    if (pulsing && (long)(now - pulseUntil) >= 0)
    {
        endPulse();
    }

    if (!paused && !pulsing && (uint8_t)(now8 - nextDue) < 128 && now8 >= nextDue)
    {
        nextDue = (uint8_t)(now8 + PERIOD_MS);
        startPulse(now);
    }

    if (paused)
    {
        nextDue = (uint8_t)(now8 + PERIOD_MS);
    }

    if (now - lastLog >= LOG_MS)
    {
        lastLog = now;
        printLog();
    }
}
