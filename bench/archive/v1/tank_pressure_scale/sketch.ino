void setup(){Serial.begin(9600);}
void loop(){
  // forgot 5V span
  float kpa = analogRead(A3) * 4.0;
  Serial.print("kPa: "); Serial.println(kpa);
  delay(1000);
}
