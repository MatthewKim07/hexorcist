void setup(){pinMode(2,INPUT_PULLUP); pinMode(13,OUTPUT);}
void loop(){
  bool hit = digitalRead(2)==LOW;
  digitalWrite(13, hit ? LOW : HIGH);
}
