// Bench reagent inject one-shot.
// Start button on D2 (pull-up), inject indicator on D4.
// Heartbeat on UART while idle and during the pulse.

const int START_PIN = 2;
const int INJECT_PIN = 4;
const unsigned long PULSE_MS = 3000;
const unsigned long DEBOUNCE_MS = 30;
const unsigned long HB_MS = 400;

bool pulsing = false;
unsigned long pulseStart = 0;
int stableBtn = HIGH;
int lastBtn = HIGH;
unsigned long btnEdge = 0;
unsigned long lastHb = 0;
unsigned long shots = 0;

void injectHigh()
{
    digitalWrite(INJECT_PIN, HIGH);
}

void injectLow()
{
    digitalWrite(INJECT_PIN, LOW);
}

void sendHb()
{
    Serial.print("inject hb shots=");
    Serial.println(shots);
}

void setup()
{
    pinMode(START_PIN, INPUT_PULLUP);
    pinMode(INJECT_PIN, OUTPUT);
    injectLow();
    Serial.begin(9600);
    stableBtn = digitalRead(START_PIN);
    lastBtn = stableBtn;
    lastHb = millis();
}

void loop()
{
    unsigned long now = millis();
    int raw = digitalRead(START_PIN);

    if (raw != lastBtn)
    {
        btnEdge = now;
        lastBtn = raw;
    }

    if ((now - btnEdge) >= DEBOUNCE_MS && raw != stableBtn)
    {
        stableBtn = raw;
        if (stableBtn == LOW && !pulsing)
        {
            pulsing = true;
            pulseStart = now;
            shots++;
            injectHigh();
            Serial.println("go");
        }
    }

    if (pulsing && (now - pulseStart) >= PULSE_MS)
    {
        pulsing = false;
        injectLow();
    }

    if (now - lastHb >= HB_MS)
    {
        lastHb = now;
        sendHb();
    }
}
