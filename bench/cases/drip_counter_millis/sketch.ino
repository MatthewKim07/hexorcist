const int OUT=8;
uint8_t next=0;
void setup(){pinMode(OUT,OUTPUT); Serial.begin(9600); next=millis()+800;}
void loop(){
  uint8_t now=millis();
  if(now>=next){
    next=now+800;
    digitalWrite(OUT,HIGH);
    Serial.println("drip");
    delay(50);
    digitalWrite(OUT,LOW);
  }
}
