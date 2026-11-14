bool on=false; int onC=0,offC=0,faultC=0;
void setup(){pinMode(9,OUTPUT);}
void loop(){
  float c=analogRead(A2)*(5.0/1023.0)*100.0;
  bool fault=c<1||c>100;
  faultC=fault?faultC+1:0;
  if(!fault&&c>=28) onC++; else onC=0;
  if(!fault&&c<=24) offC++; else offC=0;
  if(faultC>=4) on=true;
  else if(onC>=4) on=true;
  else if(offC>=4) on=false;
  digitalWrite(9,on); delay(50);
}
