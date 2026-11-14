bool on=false; unsigned long t0; int stable=HIGH,last=HIGH; unsigned long ch=0;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(8,OUTPUT);}
void loop(){
  int v=digitalRead(2);
  if(v!=last){ch=millis();last=v;}
  if(millis()-ch>=25 && v!=stable){ stable=v; if(stable==LOW && !on){on=true;t0=millis();digitalWrite(8,HIGH);} }
  if(on && millis()-t0>=2500){on=false;digitalWrite(8,LOW);}
}
