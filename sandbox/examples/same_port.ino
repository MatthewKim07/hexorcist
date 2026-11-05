// A press on D2 must hold through writes to other pins on PORTD.
const int BUTTON_PIN = 2;
const int OUTPUT_PIN = 7;
const int PULLED_UP_PIN = 4;

void setup()
{
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(PULLED_UP_PIN, INPUT_PULLUP);
    pinMode(OUTPUT_PIN, OUTPUT);
    Serial.begin(115200);
}

void loop()
{
    static bool high = false;
    high = !high;
    digitalWrite(OUTPUT_PIN, high ? HIGH : LOW);
    delay(1);
    Serial.print("btn=");
    Serial.print(digitalRead(BUTTON_PIN));
    Serial.print(" pull=");
    Serial.println(digitalRead(PULLED_UP_PIN));
    delay(49);
}
