void setup(){Serial.begin(9600);}
void loop(){
  float v=analogRead(A0)*(5.0/1023.0);
  Serial.print("Temp: "); Serial.println((v-0.5)*100.0);
  delay(1000);
}
