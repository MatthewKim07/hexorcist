// Front porch gate chime.
// Gate contact on D3 (pull-up, active LOW when open), chime coil on D10.
// Keep a UART heartbeat alive for the monitoring hub.

const uint8_t GATE_PIN = 3;
const uint8_t CHIME_PIN = 10;
const unsigned long CHIME_MS = 1800;
const unsigned long HB_MS = 300;

unsigned long lastHb = 0;
unsigned long openCount = 0;

void chimeHigh()
{
    digitalWrite(CHIME_PIN, HIGH);
}

void chimeLow()
{
    digitalWrite(CHIME_PIN, LOW);
}

void pulseChimeBlocking()
{
    openCount++;
    chimeHigh();
    delay(CHIME_MS);
    chimeLow();
}

void sendHb()
{
    Serial.println("gate-hb");
}

bool gateOpened()
{
    return digitalRead(GATE_PIN) == LOW;
}

void setup()
{
    pinMode(GATE_PIN, INPUT_PULLUP);
    pinMode(CHIME_PIN, OUTPUT);
    chimeLow();
    Serial.begin(9600);
    lastHb = millis();
}

void loop()
{
    if (gateOpened())
    {
        pulseChimeBlocking();
    }

    unsigned long now = millis();
    if (now - lastHb >= HB_MS)
    {
        lastHb = now;
        sendHb();
    }
}
