// Walk-in cooler compressor controller.
// Cabinet probe on A3 (10 mV/°C), compressor on D7, service switch on D4.

const int TEMP_PIN = A3;
const int COMP_PIN = 7;
const int SERVICE_PIN = 4;
const float COOL_ON_C = 8.0f;
const float COOL_OFF_C = 4.0f;
const float FAULT_LOW_C = 0.0f;
const float FAULT_HIGH_C = 60.0f;
const float MV_PER_C = 10.0f;
const unsigned long TICK_MS = 50;
const unsigned long STATUS_MS = 1000;
const int HOLD_N = 3;

bool cooling = false;
int onHold = 0;
int offHold = 0;
unsigned long lastTick = 0;
unsigned long lastStatus = 0;
float tempC = 0.0f;

float readTempC()
{
    int raw = analogRead(TEMP_PIN);
    float mv = raw * (5000.0f / 1023.0f);
    return mv / MV_PER_C;
}

void setCompressor(bool on)
{
    cooling = on;
    digitalWrite(COMP_PIN, on ? HIGH : LOW);
}

void printStatus()
{
    Serial.print("cooler: ");
    Serial.print(tempC, 1);
    Serial.print(" C comp=");
    Serial.println(cooling ? "ON" : "OFF");
}

void setup()
{
    pinMode(COMP_PIN, OUTPUT);
    pinMode(SERVICE_PIN, INPUT_PULLUP);
    setCompressor(false);
    Serial.begin(9600);
    lastTick = millis();
    lastStatus = millis();
}

void loop()
{
    unsigned long now = millis();

    if (now - lastTick >= TICK_MS)
    {
        lastTick = now;
        tempC = readTempC();
        bool service = (digitalRead(SERVICE_PIN) == LOW);
        bool fault = (tempC < FAULT_LOW_C) || (tempC > FAULT_HIGH_C);

        if (service || fault)
        {
            onHold = 0;
            offHold = 0;
            setCompressor(false);
        }
        else
        {
            if (tempC >= COOL_ON_C)
            {
                onHold++;
            }
            else
            {
                onHold = 0;
            }

            if (tempC <= COOL_OFF_C)
            {
                offHold++;
            }
            else
            {
                offHold = 0;
            }

            if (onHold >= HOLD_N)
            {
                setCompressor(true);
            }
            else if (offHold >= HOLD_N)
            {
                setCompressor(false);
            }
        }
    }

    if (now - lastStatus >= STATUS_MS)
    {
        lastStatus = now;
        printStatus();
    }
}
