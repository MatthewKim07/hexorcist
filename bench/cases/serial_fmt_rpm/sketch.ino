void setup(){Serial.begin(9600);}
void loop(){
  float rpm=analogRead(A5)*(5000.0/1023.0);
  Serial.print("rpm: "); // wrong case/space
  Serial.println(rpm);
  delay(1000);
}
