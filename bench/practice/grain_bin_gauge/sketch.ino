// Grain bin gauge: running average of the level probe on A3.
// High-level lamp on D5, level report over UART.

const int PROBE_PIN = A3;
const int LAMP_PIN = 5;
const int WINDOW = 32;
const long HIGH_MM = 4300;
const unsigned long SAMPLE_MS = 30;
const unsigned long REPORT_MS = 1000;

int readings[WINDOW];
int slot = 0;
int total = 0;
unsigned long lastSample = 0;
unsigned long lastReport = 0;

void takeSample()
{
    int raw = analogRead(PROBE_PIN);
    total -= readings[slot];
    readings[slot] = raw;
    total += raw;
    slot = (slot + 1) % WINDOW;
}

long averageMm()
{
    return ((long)total * 5000L) / (1023L * WINDOW);
}

void showLamp()
{
    digitalWrite(LAMP_PIN, averageMm() >= HIGH_MM ? HIGH : LOW);
}

void report()
{
    Serial.print("bin ");
    Serial.print(averageMm());
    Serial.println(" mm");
}

void setup()
{
    pinMode(LAMP_PIN, OUTPUT);
    digitalWrite(LAMP_PIN, LOW);
    Serial.begin(9600);
    for (int i = 0; i < WINDOW; i++)
    {
        readings[i] = 0;
    }
    for (int i = 0; i < WINDOW; i++)
    {
        takeSample();
    }
    lastSample = millis();
    lastReport = millis();
    showLamp();
}

void loop()
{
    unsigned long now = millis();
    if (now - lastSample >= SAMPLE_MS)
    {
        lastSample = now;
        takeSample();
        showLamp();
    }
    if (now - lastReport >= REPORT_MS)
    {
        lastReport = now;
        report();
    }
}
