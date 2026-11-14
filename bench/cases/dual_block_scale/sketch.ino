void setup(){Serial.begin(9600);pinMode(8,OUTPUT);}
void loop(){
  float flow = analogRead(A0); // wrong scale
  digitalWrite(8, flow < 100 ? HIGH : LOW);
  Serial.print("flow: "); Serial.println(flow);
  delay(2000); // blocking
}
