const byte LVL = A2;
const byte PUMP = 6;
void setup() { pinMode(PUMP, OUTPUT); }
void loop()
{
    float cm = analogRead(LVL) * (5.0 / 1023.0) * 100.0;
    digitalWrite(PUMP, cm >= 40.0 ? HIGH : LOW);
    delay(40);
}
