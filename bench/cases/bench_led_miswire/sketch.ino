// Electronics-bench user LED mirror.
// Momentary probe button on D2 (pull-up), user LED on D13.
// Mode switch on D4 (pull-up) selects steady vs blink-while-held.

const int BTN_PIN = 2;
const int LED_PIN = 12;
const int MODE_PIN = 4;
const unsigned long BLINK_MS = 120;
const unsigned long STATUS_MS = 1000;

bool lit = false;
unsigned long lastBlink = 0;
unsigned long lastStatus = 0;
unsigned long pressMs = 0;

void setLed(bool on)
{
    lit = on;
    digitalWrite(LED_PIN, on ? HIGH : LOW);
}

void publishStatus()
{
    Serial.print("bench led=");
    Serial.print(lit ? 1 : 0);
    Serial.print(" held_ms=");
    Serial.println(pressMs);
}

void setup()
{
    pinMode(BTN_PIN, INPUT_PULLUP);
    pinMode(MODE_PIN, INPUT_PULLUP);
    pinMode(LED_PIN, OUTPUT);
    setLed(false);
    Serial.begin(9600);
    lastBlink = millis();
    lastStatus = millis();
}

void loop()
{
    unsigned long now = millis();
    bool pressed = (digitalRead(BTN_PIN) == LOW);
    bool blinkMode = (digitalRead(MODE_PIN) == LOW);

    if (!pressed)
    {
        pressMs = 0;
        setLed(false);
    }
    else if (!blinkMode)
    {
        pressMs = now;
        setLed(true);
    }
    else
    {
        if (pressMs == 0)
        {
            pressMs = now;
            lastBlink = now;
            setLed(true);
        }
        if (now - lastBlink >= BLINK_MS)
        {
            lastBlink = now;
            setLed(!lit);
        }
    }

    if (now - lastStatus >= STATUS_MS)
    {
        lastStatus = now;
        publishStatus();
    }
}
