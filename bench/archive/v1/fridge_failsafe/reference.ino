bool cool=false; int faultC=0,onC=0,offC=0;
void setup(){pinMode(7,OUTPUT);}
void loop(){
  float c=analogRead(A3)*(5.0/1023.0)*100.0;
  bool fault=c<1||c>60;
  faultC=fault?faultC+1:0;
  if(!fault&&c>=8) onC++; else onC=0;
  if(!fault&&c<=4) offC++; else offC=0;
  if(faultC>=3) cool=false;
  else if(onC>=3) cool=true;
  else if(offC>=3) cool=false;
  digitalWrite(7,cool); delay(50);
}
