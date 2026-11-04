void setup()
{
    pinMode(9, OUTPUT);
    pinMode(3, INPUT_PULLUP);
}

void loop()
{
    analogWrite(9, 128);
    delay(300);
    analogWrite(9, 0);
    delay(300);
    digitalWrite(9, digitalRead(3));
    delay(300);
}
