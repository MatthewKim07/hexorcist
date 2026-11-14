#define GATE 7
#define BEEP 11
unsigned long until=0, lastHb=0;
int stable=HIGH,last=HIGH; unsigned long ch=0;
void setup(){pinMode(GATE,INPUT_PULLUP);pinMode(BEEP,OUTPUT);Serial.begin(9600);}
void loop(){
  int now=digitalRead(GATE);
  if(now!=last){ch=millis();last=now;}
  if(millis()-ch>=25 && now!=stable){
    stable=now;
    if(stable==LOW && until==0){digitalWrite(BEEP,HIGH); until=millis()+1500;}
  }
  if(until && millis()>=until){digitalWrite(BEEP,LOW); until=0;}
  if(millis()-lastHb>=200){ lastHb=millis(); Serial.println("hb"); }
}
