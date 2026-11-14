const int BTN = 3;
const int LAMP = 8;
const unsigned long DEBOUNCE_MS = 40;
bool lit = false;
int stable = HIGH;
int last = HIGH;
unsigned long changed = 0;
void setup()
{
    pinMode(BTN, INPUT_PULLUP);
    pinMode(LAMP, OUTPUT);
}
void loop()
{
    int v = digitalRead(BTN);
    if (v != last)
    {
        changed = millis();
        last = v;
    }
    if (millis() - changed >= DEBOUNCE_MS && v != stable)
    {
        stable = v;
        if (stable == LOW)
        {
            lit = !lit;
            digitalWrite(LAMP, lit ? HIGH : LOW);
        }
    }
}
