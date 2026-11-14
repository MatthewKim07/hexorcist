// uint8_t millis slice wraps, blink runs too fast
const int LED=12;
uint8_t last=0;
bool on=false;
void setup(){ pinMode(LED,OUTPUT); Serial.begin(9600); last=millis(); }
void loop(){
  uint8_t now = millis();
  if((uint8_t)(now-last) >= 500){
    last=now;
    on=!on;
    digitalWrite(LED,on?HIGH:LOW);
    if(on) Serial.println("tick");
  }
}
