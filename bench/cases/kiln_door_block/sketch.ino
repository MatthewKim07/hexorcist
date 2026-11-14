// Studio kiln door interlock siren.
// Door-open switch on D2 (pull-up, active LOW), piezo driver on D8.
// Spec requires a serial heartbeat while the siren runs.

const int DOOR_PIN = 2;
const int SIREN_PIN = 8;
const unsigned long SIREN_MS = 2000;
const unsigned long HEARTBEAT_MS = 250;

unsigned long lastHeartbeat = 0;
unsigned long tripCount = 0;
bool sirenArmed = false;

void sirenOn()
{
    digitalWrite(SIREN_PIN, HIGH);
}

void sirenOff()
{
    digitalWrite(SIREN_PIN, LOW);
}

void emitHeartbeat()
{
    Serial.println("hb");
}

bool doorOpen()
{
    return digitalRead(DOOR_PIN) == LOW;
}

void runSirenBurst()
{
    tripCount++;
    sirenOn();
    delay(SIREN_MS);
    sirenOff();
}

void setup()
{
    pinMode(DOOR_PIN, INPUT_PULLUP);
    pinMode(SIREN_PIN, OUTPUT);
    sirenOff();
    Serial.begin(9600);
    lastHeartbeat = millis();
}

void loop()
{
    if (doorOpen())
    {
        sirenArmed = true;
        runSirenBurst();
        sirenArmed = false;
    }

    unsigned long now = millis();
    if (now - lastHeartbeat >= HEARTBEAT_MS)
    {
        lastHeartbeat = now;
        emitHeartbeat();
    }
}
