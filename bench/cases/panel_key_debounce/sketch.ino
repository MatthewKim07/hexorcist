const uint8_t KEY = 4;
const uint8_t LED = 10;
bool state = false;
uint8_t was = HIGH;
void setup() { pinMode(KEY, INPUT_PULLUP); pinMode(LED, OUTPUT); }
void loop()
{
    uint8_t now = digitalRead(KEY);
    if (was == HIGH && now == LOW) { state = !state; digitalWrite(LED, state); }
    was = now;
}
