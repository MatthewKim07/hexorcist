// Studio kiln door interlock siren.
// Door-open switch on D2 (pull-up, active LOW), piezo driver on D8.
// Spec requires a serial heartbeat while the siren runs.

const int DOOR_PIN = 2;
const int SIREN_PIN = 8;
const unsigned long SIREN_MS = 2000;
const unsigned long HEARTBEAT_MS = 250;
const unsigned long DEBOUNCE_MS = 30;

bool sirenActive = false;
unsigned long sirenStarted = 0;
unsigned long lastHeartbeat = 0;
unsigned long tripCount = 0;

int stableDoor = HIGH;
int lastDoor = HIGH;
unsigned long doorChanged = 0;

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

void setup()
{
    pinMode(DOOR_PIN, INPUT_PULLUP);
    pinMode(SIREN_PIN, OUTPUT);
    sirenOff();
    Serial.begin(9600);
    stableDoor = digitalRead(DOOR_PIN);
    lastDoor = stableDoor;
    lastHeartbeat = millis();
}

void loop()
{
    unsigned long now = millis();
    int door = digitalRead(DOOR_PIN);

    if (door != lastDoor)
    {
        doorChanged = now;
        lastDoor = door;
    }

    if ((now - doorChanged) >= DEBOUNCE_MS && door != stableDoor)
    {
        stableDoor = door;
        if (stableDoor == LOW && !sirenActive)
        {
            sirenActive = true;
            sirenStarted = now;
            tripCount++;
            sirenOn();
        }
    }

    if (sirenActive && (now - sirenStarted) >= SIREN_MS)
    {
        sirenActive = false;
        sirenOff();
    }

    if (now - lastHeartbeat >= HEARTBEAT_MS)
    {
        lastHeartbeat = now;
        emitHeartbeat();
    }
}
