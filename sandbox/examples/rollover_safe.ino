// The same blink written with an elapsed-time test, which is correct across the 2^32 ms wrap of millis().
// It prints the clock it sees, so a test can read the start value and the wrap back from the serial log.
unsigned long lastToggle = 0;
bool on = false;

void setup()
{
    pinMode(13, OUTPUT);
    Serial.begin(9600);
}

void loop()
{
    if (millis() - lastToggle >= 500)
    {
        lastToggle = millis();
        on = !on;
        digitalWrite(13, on ? HIGH : LOW);
        Serial.print("ms=");
        Serial.print(millis());
        Serial.print(" us=");
        Serial.println(micros());
    }
}
