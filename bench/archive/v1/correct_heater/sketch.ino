bool on=false;
void setup(){pinMode(9,OUTPUT);}
void loop(){
  float c=analogRead(A0)*(5.0/1023.0)*100.0;
  if(c<18) on=true; else if(c>22) on=false;
  digitalWrite(9,on); delay(50);
}
