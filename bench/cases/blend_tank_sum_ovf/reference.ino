// Blend-tank concentration logger for a process skid.
// Probe on A4 (10 mV/%). Sample button on D5 (pull-up) forces an early print.

const int CONC_PIN = A4;
const int SAMPLE_BTN = 5;
const int WINDOW = 50;
const float MV_PER_PCT = 10.0f;
const unsigned long IDLE_MS = 20;
const unsigned long STATUS_MS = 1000;

long sum = 0;
int n = 0;
float lastPct = 0.0f;
unsigned long lastStatus = 0;
unsigned long batches = 0;

float rawToPct(float raw)
{
    float mv = raw * (5000.0f / 1023.0f);
    return mv / MV_PER_PCT;
}

void resetWindow()
{
    sum = 0;
    n = 0;
}

void publishPct(float pct)
{
    Serial.print("pct: ");
    Serial.println(pct, 1);
    lastPct = pct;
    batches++;
}

void forceSampleNote()
{
    Serial.print("blend force last=");
    Serial.println(lastPct, 1);
}

void setup()
{
    pinMode(SAMPLE_BTN, INPUT_PULLUP);
    Serial.begin(9600);
    resetWindow();
    lastStatus = millis();
}

void loop()
{
    int raw = analogRead(CONC_PIN);
    sum += raw;
    n++;

    if (n >= WINDOW)
    {
        float avg = sum / (float)n;
        float pct = rawToPct(avg);
        publishPct(pct);
        resetWindow();
    }

    if (digitalRead(SAMPLE_BTN) == LOW)
    {
        forceSampleNote();
        delay(30);
    }

    unsigned long now = millis();
    if (now - lastStatus >= STATUS_MS)
    {
        lastStatus = now;
        Serial.print("blend batches=");
        Serial.println(batches);
    }

    delay(IDLE_MS);
}
