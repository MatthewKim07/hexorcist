const int BTN=2; const int SIREN=9;
void setup(){ pinMode(BTN,INPUT_PULLUP); pinMode(SIREN,OUTPUT); Serial.begin(9600); }
void loop(){
  if(digitalRead(BTN)==LOW){
    digitalWrite(SIREN,HIGH);
    delay(2000);
    digitalWrite(SIREN,LOW);
  }
}
