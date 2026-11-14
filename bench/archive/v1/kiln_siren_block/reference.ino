const int BTN=2; const int SIREN=9;
const unsigned long PULSE=2000; const unsigned long DB=30; const unsigned long HB=200;
bool siren=false; unsigned long t0=0, lastHb=0;
int stable=HIGH,last=HIGH; unsigned long ch=0;
void setup(){ pinMode(BTN,INPUT_PULLUP); pinMode(SIREN,OUTPUT); Serial.begin(9600); }
void loop(){
  int v=digitalRead(BTN);
  if(v!=last){ ch=millis(); last=v; }
  if(millis()-ch>=DB && v!=stable){
    stable=v;
    if(stable==LOW && !siren){ siren=true; t0=millis(); digitalWrite(SIREN,HIGH); }
  }
  if(siren && millis()-t0>=PULSE){ siren=false; digitalWrite(SIREN,LOW); }
  if(millis()-lastHb>=HB){ lastHb=millis(); Serial.println("hb"); }
}
