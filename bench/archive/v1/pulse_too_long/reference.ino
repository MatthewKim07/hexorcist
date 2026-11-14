bool on=false; unsigned long t0; int stable=HIGH,last=HIGH; unsigned long ch=0;
void setup(){pinMode(4,INPUT_PULLUP);pinMode(9,OUTPUT);}
void loop(){
  int v=digitalRead(4);
  if(v!=last){ch=millis();last=v;}
  if(millis()-ch>=25 && v!=stable){ stable=v; if(stable==LOW && !on){on=true;t0=millis();digitalWrite(9,HIGH);} }
  if(on && millis()-t0>=800){on=false;digitalWrite(9,LOW);}
}
