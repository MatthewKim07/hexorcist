const int HEAT=9;
bool on=false;
void setup(){pinMode(HEAT,OUTPUT);}
void loop(){
  long mv = analogRead(A0) * 5000L / 1023;
  float c = mv / 10.0;
  if(c < 18.0) on=true;
  else if(c > 22.0) on=false;
  digitalWrite(HEAT, on?HIGH:LOW);
  delay(50);
}
