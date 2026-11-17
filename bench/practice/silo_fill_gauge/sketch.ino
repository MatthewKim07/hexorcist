// Silo level gauge: running average of the level probe on A2.
// Full-level lamp on D6, level report over UART.

const int PROBE_PIN = A2;
const int LAMP_PIN = 6;
const int WINDOW = 40;
const long FULL_MM = 4200;
const unsigned long SAMPLE_MS = 25;
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
    digitalWrite(LAMP_PIN, averageMm() >= FULL_MM ? HIGH : LOW);
}

void report()
{
    Serial.print("level ");
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
