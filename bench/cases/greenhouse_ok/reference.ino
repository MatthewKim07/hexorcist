// Potting-shed vent controller (known-good build).
// Air probe on A0, vent fan on D6, UART status.

const int TEMP_PIN = A0;
const int FAN_PIN = 6;
const float OPEN_C = 30.0f;
const float CLOSE_C = 26.0f;
const float FAULT_LOW_C = 5.0f;
const float FAULT_HIGH_C = 100.0f;
const float MV_PER_C = 10.0f;
const unsigned long TICK_MS = 50;
const unsigned long STATUS_MS = 1000;
const int HOLD_N = 4;
const int CLEAR_N = 8;

bool fanOn = false;
bool faultLatched = false;
int openHold = 0;
int closeHold = 0;
int faultHold = 0;
int clearHold = 0;
unsigned long lastTick = 0;
unsigned long lastStatus = 0;
float tempC = 0.0f;

float readTempC()
{
    int raw = analogRead(TEMP_PIN);
    float mv = raw * (5000.0f / 1023.0f);
    return mv / MV_PER_C;
}

void setFan(bool on)
{
    fanOn = on;
    digitalWrite(FAN_PIN, on ? HIGH : LOW);
}

void printStatus()
{
    Serial.print("shed: ");
    Serial.print(tempC, 1);
    Serial.print(" C fan=");
    Serial.println(fanOn ? "ON" : "OFF");
}

void setup()
{
    pinMode(FAN_PIN, OUTPUT);
    digitalWrite(FAN_PIN, LOW);
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

        bool outOfRange = (tempC < FAULT_LOW_C) || (tempC > FAULT_HIGH_C);
        if (outOfRange)
        {
            faultHold++;
            clearHold = 0;
            openHold = 0;
            closeHold = 0;
        }
        else
        {
            faultHold = 0;
            clearHold++;
            if (tempC >= OPEN_C)
            {
                openHold++;
            }
            else
            {
                openHold = 0;
            }
            if (tempC <= CLOSE_C)
            {
                closeHold++;
            }
            else
            {
                closeHold = 0;
            }
        }

        if (faultHold >= HOLD_N)
        {
            faultLatched = true;
        }
        if (faultLatched && clearHold >= CLEAR_N)
        {
            faultLatched = false;
        }

        if (faultLatched)
        {
            setFan(true);
        }
        else if (openHold >= HOLD_N)
        {
            setFan(true);
        }
        else if (closeHold >= HOLD_N)
        {
            setFan(false);
        }
    }

    if (now - lastStatus >= STATUS_MS)
    {
        lastStatus = now;
        printStatus();
    }
}
