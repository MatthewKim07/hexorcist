void setup(){pinMode(2,INPUT_PULLUP);pinMode(12,OUTPUT);} // wrong pin 12
void loop(){ digitalWrite(12, digitalRead(2)==LOW ? HIGH : LOW); }
