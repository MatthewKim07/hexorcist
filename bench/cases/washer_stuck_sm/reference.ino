enum {IDLE,FILL,RUN} st=IDLE;
void setup(){pinMode(9,OUTPUT);pinMode(10,OUTPUT);}
void loop(){
  float cm=analogRead(A0)*(5.0/1023.0)*100.0;
  if(st==IDLE && cm<10) st=FILL;
  else if(st==FILL && cm>=25) st=RUN;
  else if(st==RUN && cm<20) st=IDLE;
  digitalWrite(9, st==FILL);
  digitalWrite(10, st==RUN);
  delay(40);
}
