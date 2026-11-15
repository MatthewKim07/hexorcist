// Blinks D13 every 500 ms with an absolute deadline. That pattern breaks when millis() wraps past 2^32:
// the deadline wraps to a small number while millis() is still huge, so the "time is up" test is true on every pass.
unsigned long nextToggle = 0;
bool on = false;

void setup()
{
    pinMode(13, OUTPUT);
}

void loop()
{
    if (millis() >= nextToggle)
    {
        on = !on;
        digitalWrite(13, on ? HIGH : LOW);
        nextToggle = millis() + 500;
    }
}
