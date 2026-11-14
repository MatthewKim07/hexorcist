// requires 600 ms by mistake
unsigned long down=0; bool held=false;
void setup(){pinMode(3,INPUT_PULLUP);pinMode(8,OUTPUT);}
void loop(){
  if(digitalRead(3)==LOW){
    if(!held){ held=true; down=millis(); }
    digitalWrite(8, millis()-down>=600 ? HIGH : LOW);
  } else { held=false; digitalWrite(8,LOW); }
}
