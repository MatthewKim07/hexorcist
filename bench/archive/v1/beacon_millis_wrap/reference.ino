const int LED=12;
unsigned long last=0;
bool on=false;
void setup(){ pinMode(LED,OUTPUT); Serial.begin(9600); last=millis(); }
void loop(){
  unsigned long now=millis();
  if(now-last >= 500){
    last=now;
    on=!on;
    digitalWrite(LED,on?HIGH:LOW);
    if(on) Serial.println("tick");
  }
}
