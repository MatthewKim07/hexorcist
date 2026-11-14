bool lit=false; int prev=HIGH;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(13,OUTPUT);}
void loop(){
  int v=digitalRead(2);
  // inverted edge sense + no debounce
  if(prev==LOW && v==HIGH){ lit=!lit; digitalWrite(13,lit); }
  prev=v;
}
