int stable=HIGH,last=HIGH; unsigned long ch=0; bool on=false; unsigned long t0=0;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(4,OUTPUT);}
void loop(){
  int v=digitalRead(2);
  if(v!=last){ch=millis();last=v;}
  if(millis()-ch>=30 && v!=stable){
    stable=v;
    if(stable==LOW && !on){ on=true; t0=millis(); digitalWrite(4,HIGH); }
  }
  if(on && millis()-t0>=3000){ on=false; digitalWrite(4,LOW); }
}
