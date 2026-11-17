// Orchard spray controller: one short burst per trigger press.
// Valve relay on D8, trigger button on D2 (pull-up), status over UART.

const int VALVE_PIN = 8;
const int TRIGGER_PIN = 2;
const unsigned long OPEN_MS = 400;
const unsigned long SETTLE_MS = 12;
const unsigned long REPORT_MS = 1000;

bool valveOpen = false;
bool pressed = false;
int rawLevel = HIGH;
unsigned long rawChangedAt = 0;
unsigned long valveOpenedAt = 0;
unsigned long lastReport = 0;
unsigned int bursts = 0;

void openValve()
{
    valveOpen = true;
    valveOpenedAt = millis();
    digitalWrite(VALVE_PIN, HIGH);
    bursts++;
}

void closeValve()
{
    valveOpen = false;
    digitalWrite(VALVE_PIN, LOW);
}

bool deadlineReached()
{
    return millis() - valveOpenedAt >= OPEN_MS;
}

void scanTrigger()
{
    int level = digitalRead(TRIGGER_PIN);
    unsigned long now = millis();
    if (level != rawLevel)
    {
        rawLevel = level;
        rawChangedAt = now;
    }
    if (now - rawChangedAt >= SETTLE_MS)
    {
        bool down = (rawLevel == LOW);
        if (down && !pressed && !valveOpen)
        {
            openValve();
        }
        pressed = down;
    }
}

void report()
{
    Serial.print("spray n=");
    Serial.print(bursts);
    Serial.print(" open=");
    Serial.println(valveOpen ? 1 : 0);
}

void setup()
{
    pinMode(VALVE_PIN, OUTPUT);
    pinMode(TRIGGER_PIN, INPUT_PULLUP);
    digitalWrite(VALVE_PIN, LOW);
    Serial.begin(9600);
    rawChangedAt = millis();
    lastReport = millis();
}

void loop()
{
    scanTrigger();
    if (valveOpen && deadlineReached())
    {
        closeValve();
    }
    if (millis() - lastReport >= REPORT_MS)
    {
        lastReport = millis();
        report();
    }
}
