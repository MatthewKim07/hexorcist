const uint8_t KEY = 4;
const uint8_t LED = 10;
const unsigned long DB = 50;
bool state = false;
uint8_t stable = HIGH, last = HIGH;
unsigned long t0 = 0;
void setup() { pinMode(KEY, INPUT_PULLUP); pinMode(LED, OUTPUT); }
void loop()
{
    uint8_t now = digitalRead(KEY);
    if (now != last) { t0 = millis(); last = now; }
    if (millis() - t0 >= DB && now != stable)
    {
        stable = now;
        if (stable == LOW) { state = !state; digitalWrite(LED, state); }
    }
}
