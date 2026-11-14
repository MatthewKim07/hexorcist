bool cool=false;
void setup(){pinMode(7,OUTPUT);}
void loop(){
  float c=analogRead(A3)*(5.0/1023.0)*100.0;
  if(c>=8) cool=true;
  else if(c<=4) cool=false;
  digitalWrite(7,cool); delay(50);
}
