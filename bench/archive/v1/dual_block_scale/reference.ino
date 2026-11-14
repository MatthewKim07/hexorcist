void setup(){Serial.begin(9600);pinMode(8,OUTPUT);}
void loop(){
  float mv=analogRead(A0)*(5000.0/1023.0);
  float flow=mv/2.0;
  digitalWrite(8, flow < 100 ? HIGH : LOW);
  Serial.print("flow: "); Serial.println(flow);
  delay(500);
}
