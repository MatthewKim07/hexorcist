const byte LVL = A2;
const byte PUMP = 6;
bool pumping = false;
void setup() { pinMode(PUMP, OUTPUT); }
void loop()
{
    float cm = analogRead(LVL) * (5.0 / 1023.0) * 100.0;
    if (cm >= 40.0) pumping = true;
    else if (cm <= 30.0) pumping = false;
    digitalWrite(PUMP, pumping ? HIGH : LOW);
    delay(40);
}
