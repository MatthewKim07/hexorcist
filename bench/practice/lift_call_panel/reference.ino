// Lift call panel: buzzer acknowledges a press, a status line shows the
// panel is alive. Buzzer on D11, call button on D5 (pull-up).

const int BUZZER_PIN = 11;
const int BUTTON_PIN = 5;
const unsigned long BUZZ_MS = 300;
const unsigned long SETTLE_MS = 15;
const unsigned long BEAT_MS = 500;

int rawLevel = HIGH;
bool held = false;
bool buzzing = false;
unsigned long rawChangedAt = 0;
unsigned long buzzStart = 0;
unsigned long lastBeat = 0;
unsigned int beats = 0;

void acknowledge()
{
    buzzing = true;
    buzzStart = millis();
    digitalWrite(BUZZER_PIN, HIGH);
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
        if (down && !held && !buzzing)
        {
            acknowledge();
        }
        held = down;
    }
}

void heartbeat()
{
    beats++;
    Serial.print("alive ");
    Serial.println(beats);
}

void setup()
{
    pinMode(BUZZER_PIN, OUTPUT);
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    digitalWrite(BUZZER_PIN, LOW);
    Serial.begin(9600);
    rawChangedAt = millis();
    lastBeat = millis();
}

void loop()
{
    scanButton();
    if (buzzing && millis() - buzzStart >= BUZZ_MS)
    {
        buzzing = false;
        digitalWrite(BUZZER_PIN, LOW);
    }
    if (millis() - lastBeat >= BEAT_MS)
    {
        lastBeat = millis();
        heartbeat();
    }
}
