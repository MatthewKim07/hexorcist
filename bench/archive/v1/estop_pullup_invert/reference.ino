void setup(){pinMode(3,INPUT_PULLUP);pinMode(5,OUTPUT);}
void loop(){ digitalWrite(5, digitalRead(3)==LOW ? LOW : HIGH); }
