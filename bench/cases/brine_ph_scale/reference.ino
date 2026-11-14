void setup() { Serial.begin(9600); }
void loop()
{
    int raw = analogRead(A0);
    float mv = raw * (5000.0 / 1023.0);
    float ph = mv / 500.0;
    Serial.print("pH: ");
    Serial.println(ph);
    delay(1000);
}
