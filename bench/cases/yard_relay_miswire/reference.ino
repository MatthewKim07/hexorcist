// Yard path lamp dusk relay.
// Light sensor on A0 (mV as lux-ish units), relay on D8, manual on D3.

const int LIGHT_PIN = A0;
const int RELAY_PIN = 8;
const int MANUAL_PIN = 3;
const float ON_UNITS = 400.0f;
const float OFF_UNITS = 600.0f;
const unsigned long SAMPLE_MS = 40;
const unsigned long STATUS_MS = 1000;

bool relayOn = false;
unsigned long lastSample = 0;
unsigned long lastStatus = 0;
float lightU = 0.0f;

float readLightUnits()
{
    int raw = analogRead(LIGHT_PIN);
    return raw * (5000.0f / 1023.0f);
}

void setRelay(bool on)
{
    relayOn = on;
    digitalWrite(RELAY_PIN, on ? HIGH : LOW);
}

void printStatus()
{
    Serial.print("yard u=");
    Serial.print(lightU, 0);
    Serial.print(" relay=");
    Serial.println(relayOn ? "ON" : "OFF");
}

void setup()
{
    pinMode(RELAY_PIN, OUTPUT);
    pinMode(MANUAL_PIN, INPUT_PULLUP);
    setRelay(false);
    Serial.begin(9600);
    lastSample = millis();
    lastStatus = millis();
}

void loop()
{
    unsigned long now = millis();

    if (now - lastSample >= SAMPLE_MS)
    {
        lastSample = now;
        lightU = readLightUnits();
        bool manual = (digitalRead(MANUAL_PIN) == LOW);

        if (manual)
        {
            setRelay(true);
        }
        else if (lightU < ON_UNITS)
        {
            setRelay(true);
        }
        else if (lightU > OFF_UNITS)
        {
            setRelay(false);
        }
    }

    if (now - lastStatus >= STATUS_MS)
    {
        lastStatus = now;
        printStatus();
    }
}
