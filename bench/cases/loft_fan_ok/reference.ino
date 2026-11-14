// Loft cooling fan with hysteresis and a boost button.
// TMP-style linear probe on A3 (10 mV/°C), fan on D5, boost on D4.

const int TEMP_PIN = A3;
const int FAN_PIN = 5;
const int BOOST_PIN = 4;

const float ON_C = 36.0f;
const float OFF_C = 32.0f;
const float MV_PER_C = 10.0f;
const unsigned long SAMPLE_MS = 50;
const unsigned long LOG_MS = 1000;
const int HOLD = 4;

bool fanOn = false;
int onHold = 0;
int offHold = 0;
unsigned long lastSample = 0;
unsigned long lastLog = 0;
float tempC = 0.0f;

float sampleTempC()
{
    int raw = analogRead(TEMP_PIN);
    float mv = raw * (5000.0f / 1023.0f);
    return mv / MV_PER_C;
}

void driveFan(bool on)
{
    fanOn = on;
    digitalWrite(FAN_PIN, on ? HIGH : LOW);
}

void logLine()
{
    Serial.print("loft: ");
    Serial.print(tempC, 1);
    Serial.print(" C fan=");
    Serial.println(fanOn ? "ON" : "OFF");
}

void setup()
{
    pinMode(FAN_PIN, OUTPUT);
    pinMode(BOOST_PIN, INPUT_PULLUP);
    digitalWrite(FAN_PIN, LOW);
    Serial.begin(9600);
    lastSample = millis();
    lastLog = millis();
}

void loop()
{
    unsigned long now = millis();

    if (now - lastSample >= SAMPLE_MS)
    {
        lastSample = now;
        tempC = sampleTempC();

        if (digitalRead(BOOST_PIN) == LOW)
        {
            onHold = 0;
            offHold = 0;
            driveFan(true);
        }
        else
        {
            if (tempC >= ON_C)
            {
                onHold++;
            }
            else
            {
                onHold = 0;
            }
            if (tempC <= OFF_C)
            {
                offHold++;
            }
            else
            {
                offHold = 0;
            }

            if (onHold >= HOLD)
            {
                driveFan(true);
            }
            else if (offHold >= HOLD)
            {
                driveFan(false);
            }
        }
    }

    if (now - lastLog >= LOG_MS)
    {
        lastLog = now;
        logLine();
    }
}
