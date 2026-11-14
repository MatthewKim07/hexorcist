// Front porch gate chime.
// Gate contact on D3 (pull-up, active LOW when open), chime coil on D10.
// Keep a UART heartbeat alive for the monitoring hub.

const uint8_t GATE_PIN = 3;
const uint8_t CHIME_PIN = 10;
const unsigned long CHIME_MS = 1800;
const unsigned long HB_MS = 300;
const unsigned long SETTLE_MS = 35;

bool chimeRunning = false;
unsigned long chimeStart = 0;
unsigned long lastHb = 0;
unsigned long openCount = 0;

int stableGate = HIGH;
int lastGate = HIGH;
unsigned long gateEdgeAt = 0;

void chimeHigh()
{
    digitalWrite(CHIME_PIN, HIGH);
}

void chimeLow()
{
    digitalWrite(CHIME_PIN, LOW);
}

void sendHb()
{
    Serial.println("gate-hb");
}

void setup()
{
    pinMode(GATE_PIN, INPUT_PULLUP);
    pinMode(CHIME_PIN, OUTPUT);
    chimeLow();
    Serial.begin(9600);
    stableGate = digitalRead(GATE_PIN);
    lastGate = stableGate;
    lastHb = millis();
}

void loop()
{
    unsigned long now = millis();
    int gate = digitalRead(GATE_PIN);

    if (gate != lastGate)
    {
        gateEdgeAt = now;
        lastGate = gate;
    }

    if ((now - gateEdgeAt) >= SETTLE_MS && gate != stableGate)
    {
        stableGate = gate;
        if (stableGate == LOW && !chimeRunning)
        {
            chimeRunning = true;
            chimeStart = now;
            openCount++;
            chimeHigh();
        }
    }

    if (chimeRunning && (now - chimeStart) >= CHIME_MS)
    {
        chimeRunning = false;
        chimeLow();
    }

    if (now - lastHb >= HB_MS)
    {
        lastHb = now;
        sendHb();
    }
}
