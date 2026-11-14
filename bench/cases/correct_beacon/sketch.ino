unsigned long last=0; bool on=false;
void setup(){pinMode(12,OUTPUT);Serial.begin(9600);last=millis();}
void loop(){
  if(millis()-last>=500){ last+=500; on=!on; digitalWrite(12,on); if(on) Serial.println("tick"); }
}
