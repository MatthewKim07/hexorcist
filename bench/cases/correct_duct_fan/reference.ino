bool on=false; int onC=0; int offC=0;
void setup(){pinMode(5,OUTPUT);}
void loop(){
  float c=analogRead(A1)*(5.0/1023.0)*100.0;
  if(c>=35.0) onC++; else onC=0;
  if(c<=32.0) offC++; else offC=0;
  if(onC>=4) on=true;
  if(offC>=4) on=false;
  digitalWrite(5,on); delay(50);
}
