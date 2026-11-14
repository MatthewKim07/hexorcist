// Wrong: prints millivolts as pH
void setup() { Serial.begin(9600); }
void loop()
{
    int raw = analogRead(A0);
    float mv = raw * (5000.0 / 1023.0);
    Serial.print("pH: ");
    Serial.println(mv);
    delay(1000);
}
