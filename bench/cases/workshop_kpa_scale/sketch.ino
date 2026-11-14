// Compressed-air manifold pressure logger for the workshop.
// Transducer on A2: 10 mV/kPa with 500 mV zero offset. Gauge lamp on D12.

const int PRESSURE_PIN = A2;
const int GAUGE_PIN = 12;
const float WARN_KPA = 90.0f;
const float MV_PER_KPA = 10.0f;
const unsigned long SAMPLE_MS = 1000;

unsigned long lastSample = 0;
unsigned long readingCount = 0;
float lastKpa = 0.0f;
float minKpa = 9999.0f;
float maxKpa = 0.0f;
bool gaugeLit = false;

float readMillivolts()
{
    int raw = analogRead(PRESSURE_PIN);
    return raw * (5000.0f / 1023.0f);
}

float millivoltsToKpa(float mv)
{
    return mv / MV_PER_KPA;
}

void trackExtremes(float kpa)
{
    if (kpa < minKpa)
    {
        minKpa = kpa;
    }
    if (kpa > maxKpa)
    {
        maxKpa = kpa;
    }
}

void updateGauge(float kpa)
{
    gaugeLit = (kpa >= WARN_KPA);
    digitalWrite(GAUGE_PIN, gaugeLit ? HIGH : LOW);
}

void printReading()
{
    Serial.print("kPa: ");
    Serial.println(lastKpa, 1);
}

void setup()
{
    pinMode(GAUGE_PIN, OUTPUT);
    digitalWrite(GAUGE_PIN, LOW);
    Serial.begin(9600);
    lastSample = millis();
}

void loop()
{
    unsigned long now = millis();
    if (now - lastSample < SAMPLE_MS)
    {
        return;
    }
    lastSample = now;

    float mv = readMillivolts();
    lastKpa = millivoltsToKpa(mv);
    readingCount++;
    trackExtremes(lastKpa);
    updateGauge(lastKpa);
    printReading();
}
