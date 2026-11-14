void setup(){Serial.begin(9600);}
void loop(){
  float mv = analogRead(A3) * (5000.0 / 1023.0);
  float kpa = mv / 4.0;
  Serial.print("kPa: "); Serial.println(kpa);
  delay(1000);
}
