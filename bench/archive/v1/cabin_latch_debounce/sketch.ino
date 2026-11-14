// Cabin lamp latch — no debounce
const int BTN = 3;
const int LAMP = 8;
bool lit = false;
int prev = HIGH;
void setup()
{
    pinMode(BTN, INPUT_PULLUP);
    pinMode(LAMP, OUTPUT);
}
void loop()
{
    int v = digitalRead(BTN);
    if (prev == HIGH && v == LOW)
    {
        lit = !lit;
        digitalWrite(LAMP, lit ? HIGH : LOW);
    }
    prev = v;
}
