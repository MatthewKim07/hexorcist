// Doorbell chime: a settled press sounds the chime for 300 ms.
// Chime driver on D7, doorbell button on D4 (pull-up), status over UART.

const int CHIME_PIN = 7;
const int BUTTON_PIN = 4;
const unsigned long CHIME_MS = 300;
const unsigned long REPORT_MS = 1000;
const int POLL_MS = 30;
const int CONFIRM_SAMPLES = 2;

int lowSamples = 0;
bool armed = true;
bool chiming = false;
unsigned long chimeStart = 0;
unsigned long lastReport = 0;
unsigned int rings = 0;

void startChime()
{
    chiming = true;
    chimeStart = millis();
    rings++;
    digitalWrite(CHIME_PIN, HIGH);
}

void endChime()
{
    chiming = false;
    digitalWrite(CHIME_PIN, LOW);
}

void pollButton()
{
    if (digitalRead(BUTTON_PIN) == LOW)
    {
        if (lowSamples < CONFIRM_SAMPLES)
        {
            lowSamples++;
        }
        if (lowSamples == CONFIRM_SAMPLES && armed)
        {
            armed = false;
            if (!chiming)
            {
                startChime();
            }
        }
    }
    else
    {
        lowSamples = 0;
        armed = true;
    }
}

void report()
{
    Serial.print("chime n=");
    Serial.println(rings);
}

void setup()
{
    pinMode(CHIME_PIN, OUTPUT);
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    digitalWrite(CHIME_PIN, LOW);
    Serial.begin(9600);
    lastReport = millis();
}

void loop()
{
    pollButton();
    if (chiming && millis() - chimeStart >= CHIME_MS)
    {
        endChime();
    }
    if (millis() - lastReport >= REPORT_MS)
    {
        lastReport = millis();
        report();
    }
    delay(POLL_MS);
}
