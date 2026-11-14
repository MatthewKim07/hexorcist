// Bench chemistry pH logger for the teaching lab.
// Linearized probe on A1 (500 mV/pH), range LED on D10.

const int PH_PIN = A1;
const int RANGE_PIN = 10;
const float MV_PER_PH = 500.0f;
const float LOW_PH = 6.50f;
const float HIGH_PH = 8.50f;
const unsigned long PERIOD_MS = 1000;

unsigned long lastPrint = 0;
unsigned long sampleCount = 0;
float phValue = 0.0f;
float phMin = 14.0f;
float phMax = 0.0f;
bool inBand = true;

float adcMillivolts(int raw)
{
    return raw * (5000.0f / 1023.0f);
}

float millivoltsToPh(float mv)
{
    return mv / MV_PER_PH;
}

void trackPh(float ph)
{
    if (ph < phMin)
    {
        phMin = ph;
    }
    if (ph > phMax)
    {
        phMax = ph;
    }
}

void updateRangeLamp(float ph)
{
    inBand = (ph >= LOW_PH) && (ph <= HIGH_PH);
    digitalWrite(RANGE_PIN, inBand ? LOW : HIGH);
}

void printPh()
{
    Serial.print("pH: ");
    Serial.println(phValue, 2);
}

void setup()
{
    pinMode(RANGE_PIN, OUTPUT);
    digitalWrite(RANGE_PIN, LOW);
    Serial.begin(9600);
    lastPrint = millis();
}

void loop()
{
    int raw = analogRead(PH_PIN);
    float mv = adcMillivolts(raw);
    phValue = millivoltsToPh(mv);
    sampleCount++;
    trackPh(phValue);
    updateRangeLamp(phValue);

    unsigned long now = millis();
    if (now - lastPrint >= PERIOD_MS)
    {
        lastPrint = now;
        printPh();
    }
}
