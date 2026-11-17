// Loading dock horn: a short blast per settled press, plus a status line.
// Horn relay on D12, dock button on D4 (pull-up).

const int HORN_PIN = 12;
const int BUTTON_PIN = 4;
const unsigned long HORN_MS = 60;
const unsigned long SETTLE_MS = 15;
const unsigned long BEAT_MS = 500;

int rawLevel = HIGH;
bool held = false;
unsigned long rawChangedAt = 0;
unsigned long lastBeat = 0;
unsigned int beats = 0;

void blast()
{
    digitalWrite(HORN_PIN, HIGH);
    delay(HORN_MS);
    digitalWrite(HORN_PIN, LOW);
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
        if (down && !held)
        {
            blast();
        }
        held = down;
    }
}

void heartbeat()
{
    beats++;
    Serial.print("dock ");
    Serial.println(beats);
}

void setup()
{
    pinMode(HORN_PIN, OUTPUT);
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    digitalWrite(HORN_PIN, LOW);
    Serial.begin(9600);
    rawChangedAt = millis();
    lastBeat = millis();
}

void loop()
{
    scanButton();
    if (millis() - lastBeat >= BEAT_MS)
    {
        lastBeat = millis();
        heartbeat();
    }
}
