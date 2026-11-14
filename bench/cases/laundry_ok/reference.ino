// Compact laundry fill/run cycle controller (known-good build).
// Level probe on A0 (10 mV/cm), fill valve on D9, drum motor on D10.
// Reset button on D4 (pull-up) returns to IDLE.

const int LEVEL_PIN = A0;
const int VALVE_PIN = 9;
const int MOTOR_PIN = 10;
const int RESET_PIN = 4;
const float EMPTY_CM = 10.0f;
const float FULL_CM = 25.0f;
const float RUN_MIN_CM = 20.0f;
const float MV_PER_CM = 10.0f;
const unsigned long TICK_MS = 40;
const unsigned long STATUS_MS = 1000;

enum CycleState
{
    ST_IDLE = 0,
    ST_FILL = 1,
    ST_RUN = 2
};

CycleState state = ST_IDLE;
unsigned long lastTick = 0;
unsigned long lastStatus = 0;
float levelCm = 0.0f;

float readLevelCm()
{
    int raw = analogRead(LEVEL_PIN);
    float mv = raw * (5000.0f / 1023.0f);
    return mv / MV_PER_CM;
}

void driveOutputs()
{
    digitalWrite(VALVE_PIN, state == ST_FILL ? HIGH : LOW);
    digitalWrite(MOTOR_PIN, state == ST_RUN ? HIGH : LOW);
}

void printStatus()
{
    Serial.print("laundry st=");
    Serial.print((int)state);
    Serial.print(" cm=");
    Serial.println(levelCm, 1);
}

void setup()
{
    pinMode(VALVE_PIN, OUTPUT);
    pinMode(MOTOR_PIN, OUTPUT);
    pinMode(RESET_PIN, INPUT_PULLUP);
    driveOutputs();
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
        levelCm = readLevelCm();

        if (digitalRead(RESET_PIN) == LOW)
        {
            state = ST_IDLE;
        }
        else if (state == ST_IDLE && levelCm < EMPTY_CM)
        {
            state = ST_FILL;
        }
        else if (state == ST_FILL && levelCm >= FULL_CM)
        {
            state = ST_RUN;
        }
        else if (state == ST_RUN && levelCm < RUN_MIN_CM)
        {
            state = ST_IDLE;
        }

        driveOutputs();
    }

    if (now - lastStatus >= STATUS_MS)
    {
        lastStatus = now;
        printStatus();
    }
}
