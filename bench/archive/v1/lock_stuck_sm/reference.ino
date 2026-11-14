bool locked=false;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(3,INPUT_PULLUP);pinMode(9,OUTPUT);}
void loop(){
  if(digitalRead(2)==LOW && digitalRead(3)==LOW) locked=true;
  if(digitalRead(3)==HIGH) locked=false;
  digitalWrite(9, locked);
}
