int prev=HIGH; bool on=false; unsigned long t0=0;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(4,OUTPUT);}
void loop(){
  int v=digitalRead(2);
  if(prev==HIGH && v==LOW && !on){ on=true; t0=millis(); digitalWrite(4,HIGH); }
  if(on && millis()-t0>=2000){ on=false; digitalWrite(4,LOW); }
  prev=v;
}
