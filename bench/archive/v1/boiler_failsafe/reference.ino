bool fire=false; int fc=0;
void setup(){pinMode(6,OUTPUT);}
void loop(){
  float t=analogRead(A1)*(5.0/1023.0)*100.0;
  bool fault=t<5||t>120;
  fc=fault?fc+1:0;
  if(fc>=3) fire=false;
  else if(t<70) fire=true;
  else if(t>75) fire=false;
  digitalWrite(6,fire); delay(40);
}
