bool fire=false;
void setup(){pinMode(6,OUTPUT);}
void loop(){
  float t=analogRead(A1)*(5.0/1023.0)*100.0;
  if(t<70) fire=true; else if(t>75) fire=false;
  digitalWrite(6,fire); delay(40);
}
