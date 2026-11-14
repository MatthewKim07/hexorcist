// Recording-studio panic siren with non-blocking pulse and heartbeat.
// Panic button on D4 (pull-up), siren driver on D7.

const int PANIC_PIN = 4;
const int SIREN_PIN = 7;
const unsigned long PULSE_MS = 2500;
const unsigned long HB_MS = 400;
const unsigned long DEBOUNCE_MS = 35;

bool sirenOn = false;
unsigned long sirenStart = 0;
unsigned long lastHb = 0;

int stableBtn = HIGH;
int lastBtn = HIGH;
unsigned long btnChanged = 0;

void sirenHigh()
{
    digitalWrite(SIREN_PIN, HIGH);
}

void sirenLow()
{
    digitalWrite(SIREN_PIN, LOW);
}

void sendHb()
{
    Serial.println("hb");
}

void setup()
{
    pinMode(PANIC_PIN, INPUT_PULLUP);
    pinMode(SIREN_PIN, OUTPUT);
    sirenLow();
    Serial.begin(9600);
    stableBtn = digitalRead(PANIC_PIN);
    lastBtn = stableBtn;
    lastHb = millis();
}

void loop()
{
    unsigned long now = millis();
    int btn = digitalRead(PANIC_PIN);

    if (btn != lastBtn)
    {
        btnChanged = now;
        lastBtn = btn;
    }

    if ((now - btnChanged) >= DEBOUNCE_MS && btn != stableBtn)
    {
        stableBtn = btn;
        if (stableBtn == LOW && !sirenOn)
        {
            sirenOn = true;
            sirenStart = now;
            sirenHigh();
        }
    }

    if (sirenOn && (now - sirenStart) >= PULSE_MS)
    {
        sirenOn = false;
        sirenLow();
    }

    if (now - lastHb >= HB_MS)
    {
        lastHb = now;
        sendHb();
    }
}
