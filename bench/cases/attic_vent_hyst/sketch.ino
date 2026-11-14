// Attic ridge-vent controller for an Uno.
// LM35 on A0, relay driver on D8, momentary override on D3 (pull-up).

const int TEMP_PIN = A0;
const int FAN_PIN = 8;
const int OVERRIDE_PIN = 3;

const float FAN_ON_C = 42.0f;
const float MV_PER_C = 10.0f;
const unsigned long SAMPLE_MS = 50;
const unsigned long STATUS_MS = 1000;

bool fanRunning = false;
unsigned long lastSampleMs = 0;
unsigned long lastStatusMs = 0;
float lastTempC = 0.0f;

float readAtticTempC()
{
    int raw = analogRead(TEMP_PIN);
    float millivolts = raw * (5000.0f / 1023.0f);
    return millivolts / MV_PER_C;
}

void applyFan(bool wantOn)
{
    fanRunning = wantOn;
    digitalWrite(FAN_PIN, wantOn ? HIGH : LOW);
}

void publishStatus()
{
    Serial.print("attic: ");
    Serial.print(lastTempC, 1);
    Serial.print(" C fan=");
    Serial.println(fanRunning ? "ON" : "OFF");
}

void setup()
{
    pinMode(FAN_PIN, OUTPUT);
    pinMode(OVERRIDE_PIN, INPUT_PULLUP);
    digitalWrite(FAN_PIN, LOW);
    Serial.begin(9600);
    lastSampleMs = millis();
    lastStatusMs = millis();
}

void loop()
{
    unsigned long now = millis();

    if (now - lastSampleMs >= SAMPLE_MS)
    {
        lastSampleMs = now;
        lastTempC = readAtticTempC();

        bool overrideHeld = (digitalRead(OVERRIDE_PIN) == LOW);
        if (overrideHeld)
        {
            applyFan(true);
        }
        else
        {
            // Single trip point for the ridge vent.
            if (lastTempC >= FAN_ON_C)
            {
                applyFan(true);
            }
            else
            {
                applyFan(false);
            }
        }
    }

    if (now - lastStatusMs >= STATUS_MS)
    {
        lastStatusMs = now;
        publishStatus();
    }
}
