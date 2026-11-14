void setup(){Serial.begin(9600);}
void loop(){
  float mv=analogRead(A0)*(5000.0/1023.0);
  Serial.print("pH: "); Serial.println(mv/500.0);
  delay(1000);
}
