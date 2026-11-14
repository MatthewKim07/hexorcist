// Greenhouse mist injector timed pulse.
// Trigger on D4 (pull-up), injector on D9, ready lamp on D12.

const int TRIG_PIN = 4;
const int INJ_PIN = 9;
const int READY_PIN = 12;
const unsigned long PULSE_MS = 800;
const unsigned long DEBOUNCE_MS = 25;
const unsigned long HB_MS = 450;

bool pulsing = false;
unsigned long pulseStart = 0;
int stableTrig = HIGH;
int lastTrig = HIGH;
unsigned long trigEdge = 0;
unsigned long lastHb = 0;
unsigned long shots = 0;

void injHigh()
{
    digitalWrite(INJ_PIN, HIGH);
}

void injLow()
{
    digitalWrite(INJ_PIN, LOW);
}

void setReady(bool on)
{
    digitalWrite(READY_PIN, on ? HIGH : LOW);
}

void heartbeat()
{
    Serial.print("mist shots=");
    Serial.print(shots);
    Serial.print(" busy=");
    Serial.println(pulsing ? 1 : 0);
}

void setup()
{
    pinMode(TRIG_PIN, INPUT_PULLUP);
    pinMode(INJ_PIN, OUTPUT);
    pinMode(READY_PIN, OUTPUT);
    injLow();
    setReady(true);
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
            shots++;
            injHigh();
            setReady(false);
        }
    }

    if (pulsing && (now - pulseStart) >= PULSE_MS)
    {
        pulsing = false;
        injLow();
        setReady(true);
    }

    if (now - lastHb >= HB_MS)
    {
        lastHb = now;
        heartbeat();
    }
}
