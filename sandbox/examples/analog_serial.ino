void setup()
{
    Serial.begin(9600);
    pinMode(2, INPUT_PULLUP);
}

void loop()
{
    int raw = analogRead(A0);
    Serial.print("raw=");
    Serial.print(raw);
    Serial.print(" mv=");
    Serial.print((raw * 5000L) / 1023L);
    Serial.print(" btn=");
    Serial.println(digitalRead(2));
    delay(500);
}
