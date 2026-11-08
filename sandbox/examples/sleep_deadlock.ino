#include <avr/interrupt.h>
#include <avr/sleep.h>

void setup()
{
    Serial.begin(9600);
    Serial.println("going down");
    Serial.flush();
    cli();
    set_sleep_mode(SLEEP_MODE_PWR_DOWN);
    sleep_enable();
    sleep_cpu();
}

void loop()
{
}
