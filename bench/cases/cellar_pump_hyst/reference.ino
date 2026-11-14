// Basement sump controller.
// Ultrasonic level proxy as linear voltage on A1, pump contactor on D7,
// silence button on D4 (active LOW, pull-up).

const uint8_t LEVEL_PIN = A1;
const uint8_t PUMP_PIN = 7;
const uint8_t SILENCE_PIN = 4;

const float START_CM = 45.0f;
const float STOP_CM = 30.0f;
const float MV_PER_CM = 10.0f;
const unsigned long POLL_MS = 40;
const unsigned long LOG_MS = 800;
const int HOLD_N = 5;

bool pumpOn = false;
bool silenceLatched = false;
int riseHold = 0;
int fallHold = 0;
unsigned long lastPoll = 0;
unsigned long lastLog = 0;
float levelCm = 0.0f;

float sampleLevelCm()
{
    int adc = analogRead(LEVEL_PIN);
    float mv = adc * (5000.0f / 1023.0f);
    return mv / MV_PER_CM;
}

void setPump(bool on)
{
    pumpOn = on;
    digitalWrite(PUMP_PIN, on ? HIGH : LOW);
}

void emitLog()
{
    Serial.print("sump cm=");
    Serial.print(levelCm, 1);
    Serial.print(" pump=");
    Serial.print(pumpOn ? 1 : 0);
    Serial.print(" mute=");
    Serial.println(silenceLatched ? 1 : 0);
}

void setup()
{
    pinMode(PUMP_PIN, OUTPUT);
    pinMode(SILENCE_PIN, INPUT_PULLUP);
    digitalWrite(PUMP_PIN, LOW);
    Serial.begin(9600);
    lastPoll = millis();
    lastLog = millis();
}

void loop()
{
    unsigned long t = millis();

    if (digitalRead(SILENCE_PIN) == LOW)
    {
        silenceLatched = true;
        riseHold = 0;
        fallHold = 0;
        setPump(false);
    }

    if (t - lastPoll >= POLL_MS)
    {
        lastPoll = t;
        levelCm = sampleLevelCm();

        if (!silenceLatched)
        {
            if (levelCm >= START_CM)
            {
                riseHold++;
            }
            else
            {
                riseHold = 0;
            }

            if (levelCm <= STOP_CM)
            {
                fallHold++;
            }
            else
            {
                fallHold = 0;
            }

            if (riseHold >= HOLD_N)
            {
                setPump(true);
            }
            else if (fallHold >= HOLD_N)
            {
                setPump(false);
            }
        }
    }

    if (t - lastLog >= LOG_MS)
    {
        lastLog = t;
        emitLog();
    }
}
