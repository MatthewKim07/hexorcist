int sum=0; int n=0;
void setup(){Serial.begin(9600);}
void loop(){
  sum += analogRead(A4);
  n++;
  if(n>=80){
    int avg=sum/n;
    float pct = avg * (5.0/1023.0)*100.0;
    Serial.print("pct: "); Serial.println(pct);
    sum=0; n=0;
  }
  delay(12);
}
