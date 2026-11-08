// Jumps into erased flash, so the CPU runs off the end of program memory.
void setup()
{
    Serial.begin(9600);
    Serial.println("jumping");
    Serial.flush();
    void (*wild)(void) = (void (*)(void))0x3FF0;
    wild();
    Serial.println("survived");
}

void loop()
{
}
