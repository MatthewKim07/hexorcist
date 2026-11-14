void setup(){Serial.begin(9600);}
void loop(){
  float v=analogRead(A0)*(5.0/1023.0);
  float c=(v-0.5)*100.0;
  Serial.print("temp="); // wrong format
  Serial.println(c);
  delay(1000);
}
