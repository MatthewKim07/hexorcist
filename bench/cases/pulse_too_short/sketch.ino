bool on=false; unsigned long t0; int prev=HIGH;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(8,OUTPUT);}
void loop(){
  int v=digitalRead(2);
  if(prev==HIGH && v==LOW && !on){on=true;t0=millis();digitalWrite(8,HIGH);}
  if(on && millis()-t0>=1000){on=false;digitalWrite(8,LOW);}
  prev=v;
}
