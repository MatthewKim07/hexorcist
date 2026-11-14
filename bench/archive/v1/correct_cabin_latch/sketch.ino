bool lit=false; int stable=HIGH,last=HIGH; unsigned long ch=0;
void setup(){pinMode(3,INPUT_PULLUP);pinMode(8,OUTPUT);}
void loop(){
  int v=digitalRead(3);
  if(v!=last){ch=millis();last=v;}
  if(millis()-ch>=40 && v!=stable){ stable=v; if(stable==LOW){lit=!lit;digitalWrite(8,lit);} }
}
