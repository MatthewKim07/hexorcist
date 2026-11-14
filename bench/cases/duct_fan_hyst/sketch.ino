// Duct exhaust — missing hysteresis
const int SENSE = A1;
const int FAN = 5;
const float ON_C = 35.0;
bool on = false;
void setup()
{
    pinMode(FAN, OUTPUT);
}
void loop()
{
    float c = analogRead(SENSE) * (5.0 / 1023.0) * 100.0;
    on = c >= ON_C;
    digitalWrite(FAN, on ? HIGH : LOW);
    delay(50);
}
