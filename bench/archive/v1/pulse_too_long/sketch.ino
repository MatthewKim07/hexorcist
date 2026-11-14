bool on=false; unsigned long t0; int prev=HIGH;
void setup(){pinMode(4,INPUT_PULLUP);pinMode(9,OUTPUT);}
void loop(){
  int v=digitalRead(4);
  if(prev==HIGH && v==LOW && !on){on=true;t0=millis();digitalWrite(9,HIGH);}
  if(on && millis()-t0>=2000){on=false;digitalWrite(9,LOW);}
  prev=v;
}
