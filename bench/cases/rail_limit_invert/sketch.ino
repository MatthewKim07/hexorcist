// Linear rail carriage motor enable with end-stop.
// Limit switch on D2 (pull-up to GND when hit), motor enable on D13.
// Jog button on D4 (pull-up) requests motion when clear.

const int LIMIT_PIN = 2;
const int MOTOR_PIN = 13;
const int JOG_PIN = 4;
const unsigned long DEBOUNCE_MS = 25;
const unsigned long STATUS_MS = 900;

int stableLimit = HIGH;
int lastLimit = HIGH;
unsigned long limitEdge = 0;
bool motorEnabled = false;
unsigned long lastStatus = 0;
unsigned long hitCount = 0;

bool limitActiveRaw()
{
    return digitalRead(LIMIT_PIN) == HIGH;
}

void setMotor(bool enabled)
{
    motorEnabled = enabled;
    digitalWrite(MOTOR_PIN, enabled ? HIGH : LOW);
}

void publishStatus()
{
    Serial.print("rail motor=");
    Serial.print(motorEnabled ? 1 : 0);
    Serial.print(" hits=");
    Serial.println(hitCount);
}

void setup()
{
    pinMode(LIMIT_PIN, INPUT_PULLUP);
    pinMode(JOG_PIN, INPUT_PULLUP);
    pinMode(MOTOR_PIN, OUTPUT);
    setMotor(true);
    Serial.begin(9600);
    stableLimit = digitalRead(LIMIT_PIN);
    lastLimit = stableLimit;
    lastStatus = millis();
}

void loop()
{
    unsigned long now = millis();
    int raw = digitalRead(LIMIT_PIN);

    if (raw != lastLimit)
    {
        limitEdge = now;
        lastLimit = raw;
    }

    if ((now - limitEdge) >= DEBOUNCE_MS && raw != stableLimit)
    {
        stableLimit = raw;
        if (limitActiveRaw())
        {
            hitCount++;
        }
    }

    bool hit = (stableLimit == HIGH);
    bool jog = (digitalRead(JOG_PIN) == LOW);

    if (hit)
    {
        setMotor(false);
    }
    else if (jog)
    {
        setMotor(true);
    }
    else
    {
        setMotor(true);
    }

    if (now - lastStatus >= STATUS_MS)
    {
        lastStatus = now;
        publishStatus();
    }
}
