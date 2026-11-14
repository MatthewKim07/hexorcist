bool on=false;
void setup(){pinMode(7,OUTPUT);} // wrong
void loop(){
  float u=analogRead(A0)*(5000.0/1023.0);
  if(u<400) on=true; else if(u>600) on=false;
  digitalWrite(7,on);
  delay(30);
}
