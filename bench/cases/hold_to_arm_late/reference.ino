// Tool-arm interlock: hold-to-arm then release to clear.
// Hold button on D3 (pull-up), armed lamp on D8.
// Aux confirm on D5 (pull-up) is logged only.

const int HOLD_PIN = 3;
const int ARMED_PIN = 8;
const int CONFIRM_PIN = 5;
const unsigned long ARM_MS = 500;
const unsigned long STATUS_MS = 1000;

bool held = false;
unsigned long downSince = 0;
bool armed = false;
unsigned long lastStatus = 0;
unsigned long armEvents = 0;

void setArmed(bool on)
{
    if (on && !armed)
    {
        armEvents++;
    }
    armed = on;
    digitalWrite(ARMED_PIN, on ? HIGH : LOW);
}

void publishStatus()
{
    Serial.print("arm lit=");
    Serial.print(armed ? 1 : 0);
    Serial.print(" events=");
    Serial.println(armEvents);
}

void setup()
{
    pinMode(HOLD_PIN, INPUT_PULLUP);
    pinMode(CONFIRM_PIN, INPUT_PULLUP);
    pinMode(ARMED_PIN, OUTPUT);
    setArmed(false);
    Serial.begin(9600);
    lastStatus = millis();
}

void loop()
{
    unsigned long now = millis();
    bool down = (digitalRead(HOLD_PIN) == LOW);
    bool confirm = (digitalRead(CONFIRM_PIN) == LOW);

    if (down)
    {
        if (!held)
        {
            held = true;
            downSince = now;
        }
        if ((now - downSince) >= ARM_MS)
        {
            setArmed(true);
        }
        else
        {
            setArmed(false);
        }
    }
    else
    {
        held = false;
        setArmed(false);
    }

    if (confirm)
    {
        Serial.println("arm confirm");
        delay(20);
    }

    if (now - lastStatus >= STATUS_MS)
    {
        lastStatus = now;
        publishStatus();
    }
}
