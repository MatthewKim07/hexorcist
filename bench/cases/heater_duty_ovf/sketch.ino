// intermediate int overflow: analogRead*5000 exceeds 16-bit int
const int HEAT=9;
bool on=false;
void setup(){pinMode(HEAT,OUTPUT);}
void loop(){
  int mv = analogRead(A0) * 5000 / 1023;
  float c = mv / 10.0;
  if(c < 18.0) on=true;
  else if(c > 22.0) on=false;
  digitalWrite(HEAT, on?HIGH:LOW);
  delay(50);
}
