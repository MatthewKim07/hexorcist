#define GATE 7
#define BEEP 11
void setup(){pinMode(GATE,INPUT_PULLUP);pinMode(BEEP,OUTPUT);Serial.begin(9600);}
void loop(){
  static int prev=HIGH;
  int now=digitalRead(GATE);
  if(prev==HIGH && now==LOW){
    digitalWrite(BEEP,HIGH);
    delay(1500);
    digitalWrite(BEEP,LOW);
  }
  prev=now;
}
