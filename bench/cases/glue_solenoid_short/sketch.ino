// Packaging glue-dot solenoid driver.
// Trigger on D2 (pull-up), solenoid on D8, armed LED on D11.

const int TRIG_PIN = 2;
const int SOL_PIN = 8;
const int ARMED_PIN = 11;
const unsigned long PULSE_MS = 1000;
const unsigned long DEBOUNCE_MS = 25;
const unsigned long HB_MS = 500;

bool pulsing = false;
unsigned long pulseStart = 0;
int stableTrig = HIGH;
int lastTrig = HIGH;
unsigned long trigEdge = 0;
unsigned long lastHb = 0;
unsigned long dots = 0;

void solHigh()
{
    digitalWrite(SOL_PIN, HIGH);
}

void solLow()
{
    digitalWrite(SOL_PIN, LOW);
}

void setArmedLed(bool on)
{
    digitalWrite(ARMED_PIN, on ? HIGH : LOW);
}

void heartbeat()
{
    Serial.print("glue dots=");
    Serial.print(dots);
    Serial.print(" busy=");
    Serial.println(pulsing ? 1 : 0);
}

void setup()
{
    pinMode(TRIG_PIN, INPUT_PULLUP);
    pinMode(SOL_PIN, OUTPUT);
    pinMode(ARMED_PIN, OUTPUT);
    solLow();
    setArmedLed(true);
    Serial.begin(9600);
    stableTrig = digitalRead(TRIG_PIN);
    lastTrig = stableTrig;
    lastHb = millis();
}

void loop()
{
    unsigned long now = millis();
    int raw = digitalRead(TRIG_PIN);

    if (raw != lastTrig)
    {
        trigEdge = now;
        lastTrig = raw;
    }

    if ((now - trigEdge) >= DEBOUNCE_MS && raw != stableTrig)
    {
        stableTrig = raw;
        if (stableTrig == LOW && !pulsing)
        {
            pulsing = true;
            pulseStart = now;
            dots++;
            solHigh();
            setArmedLed(false);
        }
    }

    if (pulsing && (now - pulseStart) >= PULSE_MS)
    {
        pulsing = false;
        solLow();
        setArmedLed(true);
    }

    if (now - lastHb >= HB_MS)
    {
        lastHb = now;
        heartbeat();
    }
}
