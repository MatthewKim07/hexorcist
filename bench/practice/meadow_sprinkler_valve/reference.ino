// Meadow sprinkler zone: one 500 ms burst per start press.
// Valve relay on D10, start button on D6 (pull-up), status over UART.

const int ZONE_PIN = 10;
const int START_PIN = 6;
const unsigned long BURST_MS = 500;
const unsigned long SETTLE_MS = 20;
const unsigned long REPORT_MS = 1000;

bool zoneOpen = false;
bool held = false;
int rawLevel = HIGH;
unsigned long rawChangedAt = 0;
unsigned long closeAt = 0;
unsigned long lastReport = 0;
unsigned int bursts = 0;

void openZone()
{
    zoneOpen = true;
    closeAt = millis() + BURST_MS;
    digitalWrite(ZONE_PIN, HIGH);
    bursts++;
}

void closeZone()
{
    zoneOpen = false;
    digitalWrite(ZONE_PIN, LOW);
}

bool closeDue()
{
    return (long)(millis() - closeAt) >= 0;
}

void scanStart()
{
    int level = digitalRead(START_PIN);
    unsigned long now = millis();
    if (level != rawLevel)
    {
        rawLevel = level;
        rawChangedAt = now;
    }
    if (now - rawChangedAt >= SETTLE_MS)
    {
        bool down = (rawLevel == LOW);
        if (down && !held && !zoneOpen)
        {
            openZone();
        }
        held = down;
    }
}

void report()
{
    Serial.print("zone n=");
    Serial.println(bursts);
}

void setup()
{
    pinMode(ZONE_PIN, OUTPUT);
    pinMode(START_PIN, INPUT_PULLUP);
    digitalWrite(ZONE_PIN, LOW);
    Serial.begin(9600);
    rawChangedAt = millis();
    lastReport = millis();
}

void loop()
{
    scanStart();
    if (zoneOpen && closeDue())
    {
        closeZone();
    }
    if (millis() - lastReport >= REPORT_MS)
    {
        lastReport = millis();
        report();
    }
}
