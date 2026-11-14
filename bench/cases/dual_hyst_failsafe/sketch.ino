bool on=false;
void setup(){pinMode(9,OUTPUT);}
void loop(){
  float c=analogRead(A2)*(5.0/1023.0)*100.0;
  on = c>=28;
  digitalWrite(9,on); delay(50);
}
