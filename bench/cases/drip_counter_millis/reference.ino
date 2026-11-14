const int OUT=8;
unsigned long next=0;
void setup(){pinMode(OUT,OUTPUT); Serial.begin(9600); next=millis()+800;}
void loop(){
  unsigned long now=millis();
  if((long)(now-next)>=0){
    next=now+800;
    digitalWrite(OUT,HIGH);
    Serial.println("drip");
    delay(50);
    digitalWrite(OUT,LOW);
  }
}
