#!/usr/bin/env python3
"""Materialize bench/cases/ once. Not used at score time. Freeze cases after validate."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "cases"


def w(case_id: str, *, sketch: str, reference: str, spec: str, pins: list, truth: list, checks: dict) -> None:
    d = ROOT / case_id
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "sketch.ino").write_text(sketch if sketch.endswith("\n") else sketch + "\n")
    (d / "reference.ino").write_text(reference if reference.endswith("\n") else reference + "\n")
    (d / "spec.md").write_text(spec if spec.endswith("\n") else spec + "\n")
    (d / "pins.json").write_text(json.dumps(pins, indent=2) + "\n")
    (d / "truth.json").write_text(json.dumps(truth, indent=2) + "\n")
    (d / "checks.json").write_text(json.dumps(checks, indent=2) + "\n")


def main() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)

    # ---------- missing_hysteresis ----------
    w(
        "duct_fan_hyst",
        pins=[{"pin": "A1", "role": "Duct air temperature", "type": "analog_input", "scale": "10 mV/°C"},
              {"pin": "D5", "role": "Exhaust fan", "type": "digital_output"}],
        spec="Exhaust fan on D5. LM35-style sensor on A1 (10 mV/°C). Turn the fan ON when temperature is at or above 35 °C and OFF when at or below 32 °C. Do not chatter near the threshold.",
        sketch="""// Duct exhaust — missing hysteresis
const int SENSE = A1;
const int FAN = 5;
const float ON_C = 35.0;
bool on = false;
void setup()
{
    pinMode(FAN, OUTPUT);
}
void loop()
{
    float c = analogRead(SENSE) * (5.0 / 1023.0) * 100.0;
    on = c >= ON_C;
    digitalWrite(FAN, on ? HIGH : LOW);
    delay(50);
}
""",
        reference="""// Duct exhaust with hysteresis
const int SENSE = A1;
const int FAN = 5;
const float ON_C = 35.0;
const float OFF_C = 32.0;
bool on = false;
void setup()
{
    pinMode(FAN, OUTPUT);
}
void loop()
{
    float c = analogRead(SENSE) * (5.0 / 1023.0) * 100.0;
    if (c >= ON_C)
    {
        on = true;
    }
    else if (c <= OFF_C)
    {
        on = false;
    }
    digitalWrite(FAN, on ? HIGH : LOW);
    delay(50);
}
""",
        truth=[{"id": "b1", "category": "missing_hysteresis", "description": "Fan toggles at a single threshold with no off band", "check_ids": ["a_chatter"]}],
        checks={
            "assertions": [
                {"id": "a_follow", "type": "output_follows", "pin": "D5", "high_when": {"pin": "A1", "op": ">=", "value": 35}, "low_when": {"pin": "A1", "op": "<=", "value": 32}, "within_ms": 500, "description": "Fan on >=35 C, off <=32 C"},
                {"id": "a_chatter", "type": "max_toggles", "pin": "D5", "max_toggles": 2, "window_ms": 5000, "description": "Fan must not chatter"},
            ],
            "scenarios": [
                {"id": "s_hover", "name": "Hover at 35 C with noise", "seed": 3, "duration_ms": 8000,
                 "analog": [{"pin": "A1", "segments": [{"t_ms": 0, "mv": 350}], "noise_mv": 35, "spikes": []}],
                 "digital": [], "floating": []},
                {"id": "s_hot", "name": "Steady hot 40 C", "seed": 1, "duration_ms": 4000,
                 "analog": [{"pin": "A1", "segments": [{"t_ms": 0, "mv": 400}], "noise_mv": 5, "spikes": []}],
                 "digital": [], "floating": []},
            ],
        },
    )

    w(
        "sump_pump_hyst",
        pins=[{"pin": "A2", "role": "Water level", "type": "analog_input", "scale": "10 mV/cm"},
              {"pin": "D6", "role": "Sump pump", "type": "digital_output"}],
        spec="Sump pump on D6. Level sensor on A2 at 10 mV per cm. Pump ON at or above 40 cm, OFF at or below 30 cm. Avoid short-cycling near the trip point.",
        sketch="""const byte LVL = A2;
const byte PUMP = 6;
void setup() { pinMode(PUMP, OUTPUT); }
void loop()
{
    float cm = analogRead(LVL) * (5.0 / 1023.0) * 100.0;
    digitalWrite(PUMP, cm >= 40.0 ? HIGH : LOW);
    delay(40);
}
""",
        reference="""const byte LVL = A2;
const byte PUMP = 6;
bool pumping = false;
void setup() { pinMode(PUMP, OUTPUT); }
void loop()
{
    float cm = analogRead(LVL) * (5.0 / 1023.0) * 100.0;
    if (cm >= 40.0) pumping = true;
    else if (cm <= 30.0) pumping = false;
    digitalWrite(PUMP, pumping ? HIGH : LOW);
    delay(40);
}
""",
        truth=[{"id": "b1", "category": "missing_hysteresis", "description": "Pump uses one trip level and chatters with noise", "check_ids": ["a_chatter"]}],
        checks={
            "assertions": [
                {"id": "a_follow", "type": "output_follows", "pin": "D6", "high_when": {"pin": "A2", "op": ">=", "value": 40}, "low_when": {"pin": "A2", "op": "<=", "value": 30}, "within_ms": 500, "description": "Pump band 40/30 cm"},
                {"id": "a_chatter", "type": "max_toggles", "pin": "D6", "max_toggles": 2, "window_ms": 5000, "description": "No short cycle"},
            ],
            "scenarios": [
                {"id": "s_edge", "name": "Hover 40 cm noise", "seed": 9, "duration_ms": 8000,
                 "analog": [{"pin": "A2", "segments": [{"t_ms": 0, "mv": 400}], "noise_mv": 40, "spikes": []}],
                 "digital": [], "floating": []},
            ],
        },
    )

    # ---------- missing_debounce ----------
    def debounce_case(cid: str, btn: str, led: str, settle: int, sketch_buggy: str, sketch_fix: str) -> None:
        bpin = btn if btn.startswith("D") else f"D{btn}"
        lpin = led if led.startswith("D") else f"D{led}"
        bn, ln = int(bpin[1:]), int(lpin[1:])
        w(
            cid,
            pins=[{"pin": bpin, "role": "Momentary button to GND", "type": "digital_input", "active_low": True},
                  {"pin": lpin, "role": "Status LED", "type": "digital_output"}],
            spec=f"Button on {bpin} with INPUT_PULLUP (pressed = LOW). Each settled press toggles the LED on {lpin}. Debounce contact bounce; one press → one toggle.",
            sketch=sketch_buggy.format(bn=bn, ln=ln),
            reference=sketch_fix.format(bn=bn, ln=ln, settle=settle),
            truth=[{"id": "b1", "category": "missing_debounce", "description": "Bounce causes multiple LED toggles per press", "check_ids": ["a_tpp"]}],
            checks={
                "assertions": [
                    {"id": "a_tpp", "type": "toggle_per_press", "input_pin": bpin, "output_pin": lpin, "active_level": 0, "settle_ms": settle, "within_ms": 150, "description": "One toggle per settled press"},
                    {"id": "a_burst", "type": "max_toggles", "pin": lpin, "max_toggles": 1, "window_ms": 80, "description": "No burst toggles"},
                ],
                "scenarios": [
                    {"id": "s_bounce", "name": "Bouncy presses", "seed": 2, "duration_ms": 6000,
                     "analog": [], "floating": [],
                     "digital": [{"pin": bpin, "initial": 1, "events": [
                         {"t_ms": 500, "value": 0, "bounce_ms": 20, "bounce_count": 10},
                         {"t_ms": 900, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                         {"t_ms": 2000, "value": 0, "bounce_ms": 18, "bounce_count": 8},
                         {"t_ms": 2400, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                         {"t_ms": 3500, "value": 0, "bounce_ms": 22, "bounce_count": 12},
                         {"t_ms": 4000, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                     ]}]},
                ],
            },
        )

    debounce_case(
        "cabin_latch_debounce", "D3", "D8", 40,
        """// Cabin lamp latch — no debounce
const int BTN = {bn};
const int LAMP = {ln};
bool lit = false;
int prev = HIGH;
void setup()
{{
    pinMode(BTN, INPUT_PULLUP);
    pinMode(LAMP, OUTPUT);
}}
void loop()
{{
    int v = digitalRead(BTN);
    if (prev == HIGH && v == LOW)
    {{
        lit = !lit;
        digitalWrite(LAMP, lit ? HIGH : LOW);
    }}
    prev = v;
}}
""",
        """const int BTN = {bn};
const int LAMP = {ln};
const unsigned long DEBOUNCE_MS = {settle};
bool lit = false;
int stable = HIGH;
int last = HIGH;
unsigned long changed = 0;
void setup()
{{
    pinMode(BTN, INPUT_PULLUP);
    pinMode(LAMP, OUTPUT);
}}
void loop()
{{
    int v = digitalRead(BTN);
    if (v != last)
    {{
        changed = millis();
        last = v;
    }}
    if (millis() - changed >= DEBOUNCE_MS && v != stable)
    {{
        stable = v;
        if (stable == LOW)
        {{
            lit = !lit;
            digitalWrite(LAMP, lit ? HIGH : LOW);
        }}
    }}
}}
""",
    )

    debounce_case(
        "panel_key_debounce", "D4", "D10", 50,
        """const uint8_t KEY = {bn};
const uint8_t LED = {ln};
bool state = false;
uint8_t was = HIGH;
void setup() {{ pinMode(KEY, INPUT_PULLUP); pinMode(LED, OUTPUT); }}
void loop()
{{
    uint8_t now = digitalRead(KEY);
    if (was == HIGH && now == LOW) {{ state = !state; digitalWrite(LED, state); }}
    was = now;
}}
""",
        """const uint8_t KEY = {bn};
const uint8_t LED = {ln};
const unsigned long DB = {settle};
bool state = false;
uint8_t stable = HIGH, last = HIGH;
unsigned long t0 = 0;
void setup() {{ pinMode(KEY, INPUT_PULLUP); pinMode(LED, OUTPUT); }}
void loop()
{{
    uint8_t now = digitalRead(KEY);
    if (now != last) {{ t0 = millis(); last = now; }}
    if (millis() - t0 >= DB && now != stable)
    {{
        stable = now;
        if (stable == LOW) {{ state = !state; digitalWrite(LED, state); }}
    }}
}}
""",
    )

    # ---------- wrong_unit_scaling ----------
    w(
        "brine_ph_scale",
        pins=[{"pin": "A0", "role": "pH probe (linearized)", "type": "analog_input", "scale": "500 mV/pH + 0 mV"}],
        spec="Print the pH once per second as `pH: <value>`. Sensor on A0 uses 500 mV per pH unit (0 mV = pH 0). Accuracy within 0.2 pH.",
        sketch="""// Wrong: treats raw ADC as pH
void setup() { Serial.begin(9600); }
void loop()
{
    int raw = analogRead(A0);
    float ph = raw / 100.0;
    Serial.print("pH: ");
    Serial.println(ph);
    delay(1000);
}
""",
        reference="""void setup() { Serial.begin(9600); }
void loop()
{
    int raw = analogRead(A0);
    float mv = raw * (5000.0 / 1023.0);
    float ph = mv / 500.0;
    Serial.print("pH: ");
    Serial.println(ph);
    delay(1000);
}
""",
        truth=[{"id": "b1", "category": "wrong_unit_scaling", "description": "Prints raw/100 instead of mV/500 as pH", "check_ids": ["a_val"]}],
        checks={
            "assertions": [
                {"id": "a_period", "type": "serial_period", "pattern": "^pH: ", "period_ms": 1000, "tolerance_ms": 120, "description": "One line per second"},
                {"id": "a_val", "type": "serial_value_matches", "pattern": "pH: (-?[0-9.]+)", "input_pin": "A0", "tolerance": 0.2, "max_lag_ms": 400, "description": "Printed pH matches sensor"},
            ],
            "scenarios": [
                {"id": "s_ph7", "name": "pH 7 steady", "seed": 1, "duration_ms": 5000,
                 "analog": [{"pin": "A0", "segments": [{"t_ms": 0, "mv": 3500}], "noise_mv": 5, "spikes": []}],
                 "digital": [], "floating": []},
            ],
        },
    )

    w(
        "tank_pressure_scale",
        pins=[{"pin": "A3", "role": "Pressure transducer", "type": "analog_input", "scale": "4 mV/kPa"}],
        spec="Log pressure each second as `kPa: <n>`. A3 is 4 mV per kPa. Within 2 kPa.",
        sketch="""void setup(){Serial.begin(9600);}
void loop(){
  // forgot 5V span
  float kpa = analogRead(A3) * 4.0;
  Serial.print("kPa: "); Serial.println(kpa);
  delay(1000);
}
""",
        reference="""void setup(){Serial.begin(9600);}
void loop(){
  float mv = analogRead(A3) * (5000.0 / 1023.0);
  float kpa = mv / 4.0;
  Serial.print("kPa: "); Serial.println(kpa);
  delay(1000);
}
""",
        truth=[{"id": "b1", "category": "wrong_unit_scaling", "description": "Multiplies raw ADC by 4 instead of converting mV", "check_ids": ["a_val"]}],
        checks={
            "assertions": [
                {"id": "a_period", "type": "serial_period", "pattern": "^kPa: ", "period_ms": 1000, "tolerance_ms": 120, "description": "1 Hz log"},
                {"id": "a_val", "type": "serial_value_matches", "pattern": "kPa: (-?[0-9.]+)", "input_pin": "A3", "tolerance": 2.0, "max_lag_ms": 400, "description": "kPa matches transducer"},
            ],
            "scenarios": [
                {"id": "s_100", "name": "100 kPa", "seed": 4, "duration_ms": 5000,
                 "analog": [{"pin": "A3", "segments": [{"t_ms": 0, "mv": 400}], "noise_mv": 2, "spikes": []}],
                 "digital": [], "floating": []},
            ],
        },
    )

    # ---------- blocking_delay ----------
    w(
        "kiln_siren_block",
        pins=[{"pin": "D2", "role": "Panic button", "type": "digital_input", "active_low": True},
              {"pin": "D9", "role": "Siren", "type": "digital_output"}],
        spec="INPUT_PULLUP panic on D2. Each settled press starts a 2.0 s siren pulse on D9. Must stay responsive (heartbeat via siren activity); do not use blocking delay that ignores presses.",
        sketch="""const int BTN=2; const int SIREN=9;
void setup(){ pinMode(BTN,INPUT_PULLUP); pinMode(SIREN,OUTPUT); }
void loop(){
  if(digitalRead(BTN)==LOW){
    digitalWrite(SIREN,HIGH);
    delay(2000);
    digitalWrite(SIREN,LOW);
  }
}
""",
        reference="""const int BTN=2; const int SIREN=9;
const unsigned long PULSE=2000;
const unsigned long DB=30;
bool siren=false; unsigned long t0=0;
int stable=HIGH,last=HIGH; unsigned long ch=0;
void setup(){ pinMode(BTN,INPUT_PULLUP); pinMode(SIREN,OUTPUT); }
void loop(){
  int v=digitalRead(BTN);
  if(v!=last){ ch=millis(); last=v; }
  if(millis()-ch>=DB && v!=stable){
    stable=v;
    if(stable==LOW && !siren){ siren=true; t0=millis(); digitalWrite(SIREN,HIGH); }
  }
  if(siren && millis()-t0>=PULSE){ siren=false; digitalWrite(SIREN,LOW); }
}
""",
        truth=[{"id": "b1", "category": "blocking_delay", "description": "delay(2000) blocks and drops presses / stalls responsiveness", "check_ids": ["a_resp"]}],
        checks={
            "assertions": [
                {"id": "a_pulse", "type": "timed_pulse", "pin": "D9", "trigger": {"pin": "D2", "op": "==", "value": 0}, "duration_ms": 2000, "within_ms": 150, "during_pulse": "ignore", "min_trigger_ms": 40, "description": "2 s siren on press"},
                {"id": "a_resp", "type": "responsive", "max_gap_ms": 900, "start_ms": 200, "description": "Must not freeze for long stretches"},
            ],
            "scenarios": [
                {"id": "s_rapid", "name": "Rapid presses during siren", "seed": 5, "duration_ms": 8000,
                 "analog": [], "floating": [],
                 "digital": [{"pin": "D2", "initial": 1, "events": [
                     {"t_ms": 300, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 500, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 800, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 1000, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 2500, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 2700, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                 ]}]},
            ],
        },
    )

    w(
        "gate_alarm_block",
        pins=[{"pin": "D7", "role": "Gate contact", "type": "digital_input", "active_low": True},
              {"pin": "D11", "role": "Beeper", "type": "digital_output"}],
        spec="Gate contact D7 INPUT_PULLUP. Opening (LOW) sounds beeper D11 for 1500 ms. Remain responsive; no long blocking delays.",
        sketch="""#define GATE 7
#define BEEP 11
void setup(){pinMode(GATE,INPUT_PULLUP);pinMode(BEEP,OUTPUT);}
void loop(){
  static int prev=HIGH;
  int now=digitalRead(GATE);
  if(prev==HIGH && now==LOW){
    digitalWrite(BEEP,HIGH);
    delay(1500);
    digitalWrite(BEEP,LOW);
  }
  prev=now;
}
""",
        reference="""#define GATE 7
#define BEEP 11
unsigned long until=0;
int stable=HIGH,last=HIGH; unsigned long ch=0;
void setup(){pinMode(GATE,INPUT_PULLUP);pinMode(BEEP,OUTPUT);}
void loop(){
  int now=digitalRead(GATE);
  if(now!=last){ch=millis();last=now;}
  if(millis()-ch>=25 && now!=stable){
    stable=now;
    if(stable==LOW){digitalWrite(BEEP,HIGH); until=millis()+1500;}
  }
  if(until && millis()>=until){digitalWrite(BEEP,LOW); until=0;}
}
""",
        truth=[{"id": "b1", "category": "blocking_delay", "description": "Blocking delay(1500) freezes the loop", "check_ids": ["a_resp"]}],
        checks={
            "assertions": [
                {"id": "a_pulse", "type": "timed_pulse", "pin": "D11", "trigger": {"pin": "D7", "op": "==", "value": 0}, "duration_ms": 1500, "within_ms": 150, "during_pulse": "ignore", "min_trigger_ms": 30, "description": "1.5 s beep"},
                {"id": "a_resp", "type": "responsive", "max_gap_ms": 800, "start_ms": 100, "description": "Stay responsive"},
            ],
            "scenarios": [
                {"id": "s_open", "name": "Open then chatter contacts", "seed": 6, "duration_ms": 7000,
                 "analog": [], "floating": [],
                 "digital": [{"pin": "D7", "initial": 1, "events": [
                     {"t_ms": 400, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 600, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 900, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 1100, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                 ]}]},
            ],
        },
    )

    print("partial write done — continuing in part 2")
    # Mark that part1 ran; part2 appended below in same function

    _part2()
    print(f"wrote {len(list(ROOT.iterdir()))} cases to {ROOT}")


def _part2() -> None:
    # ---------- millis_rollover (uint8_t timer) ----------
    w(
        "beacon_millis_wrap",
        pins=[{"pin": "D12", "role": "Beacon LED", "type": "digital_output"}],
        spec="Blink D12: 500 ms on, 500 ms off, forever. Period must stay 1000 ms ±100 ms. Print `tick` each rising edge.",
        sketch="""// uint8_t millis slice wraps, blink runs too fast
const int LED=12;
uint8_t last=0;
bool on=false;
void setup(){ pinMode(LED,OUTPUT); Serial.begin(9600); last=millis(); }
void loop(){
  uint8_t now = millis();
  if((uint8_t)(now-last) >= 500){
    last=now;
    on=!on;
    digitalWrite(LED,on?HIGH:LOW);
    if(on) Serial.println("tick");
  }
}
""",
        reference="""const int LED=12;
unsigned long last=0;
bool on=false;
void setup(){ pinMode(LED,OUTPUT); Serial.begin(9600); last=millis(); }
void loop(){
  unsigned long now=millis();
  if(now-last >= 500){
    last=now;
    on=!on;
    digitalWrite(LED,on?HIGH:LOW);
    if(on) Serial.println("tick");
  }
}
""",
        truth=[{"id": "b1", "category": "millis_rollover", "description": "uint8_t millis delta wraps and blinks too often", "check_ids": ["a_period"]}],
        checks={
            "assertions": [
                {"id": "a_period", "type": "serial_period", "pattern": "^tick$", "period_ms": 1000, "tolerance_ms": 120, "description": "Rising edge every 1 s"},
                {"id": "a_max", "type": "max_toggles", "pin": "D12", "max_toggles": 3, "window_ms": 1500, "description": "Not faster than ~1 Hz edges"},
            ],
            "scenarios": [
                {"id": "s_blink", "name": "Idle blink", "seed": 1, "duration_ms": 6000,
                 "analog": [], "digital": [], "floating": []},
            ],
        },
    )

    w(
        "drip_counter_millis",
        pins=[{"pin": "D8", "role": "Drip pulse out", "type": "digital_output"}],
        spec="Emit a 50 ms HIGH pulse on D8 every 800 ms. Print `drip` at each pulse start. Period 800 ms ±100.",
        sketch="""const int OUT=8;
uint8_t next=0;
void setup(){pinMode(OUT,OUTPUT); Serial.begin(9600); next=millis()+800;}
void loop(){
  uint8_t now=millis();
  if(now>=next){
    next=now+800;
    digitalWrite(OUT,HIGH);
    Serial.println("drip");
    delay(50);
    digitalWrite(OUT,LOW);
  }
}
""",
        reference="""const int OUT=8;
unsigned long next=0;
void setup(){pinMode(OUT,OUTPUT); Serial.begin(9600); next=millis()+800;}
void loop(){
  unsigned long now=millis();
  if((long)(now-next)>=0){
    next=now+800;
    digitalWrite(OUT,HIGH);
    Serial.println("drip");
    delay(50);
    digitalWrite(OUT,LOW);
  }
}
""",
        truth=[{"id": "b1", "category": "millis_rollover", "description": "uint8_t schedule wraps, drip rate wrong", "check_ids": ["a_period"]}],
        checks={
            "assertions": [
                {"id": "a_period", "type": "serial_period", "pattern": "^drip$", "period_ms": 800, "tolerance_ms": 120, "description": "drip every 800 ms"},
            ],
            "scenarios": [
                {"id": "s_run", "name": "Run", "seed": 2, "duration_ms": 5000, "analog": [], "digital": [], "floating": []},
            ],
        },
    )

    # ---------- integer_overflow ----------
    w(
        "mix_tank_int_ovf",
        pins=[{"pin": "A4", "role": "Concentration sensor", "type": "analog_input", "scale": "10 mV/%"}],
        spec="Average the last readings and print `pct: <n>` once per second. A4 is 10 mV per percent. Within 3%.",
        sketch="""// int (16-bit on AVR) accumulator overflows
int sum=0; int n=0;
void setup(){Serial.begin(9600);}
void loop(){
  sum += analogRead(A4);
  n++;
  if(n>=40){
    int avg=sum/n;
    float pct = avg * (5.0/1023.0)*100.0;
    Serial.print("pct: "); Serial.println(pct);
    sum=0; n=0;
  }
  delay(25);
}
""",
        reference="""long sum=0; int n=0;
void setup(){Serial.begin(9600);}
void loop(){
  sum += analogRead(A4);
  n++;
  if(n>=40){
    float avg = sum / (float)n;
    float pct = avg * (5.0/1023.0)*100.0;
    Serial.print("pct: "); Serial.println(pct);
    sum=0; n=0;
  }
  delay(25);
}
""",
        truth=[{"id": "b1", "category": "integer_overflow", "description": "int sum of ADC samples overflows", "check_ids": ["a_val"]}],
        checks={
            "assertions": [
                {"id": "a_period", "type": "serial_period", "pattern": "^pct: ", "period_ms": 1000, "tolerance_ms": 150, "description": "1 Hz"},
                {"id": "a_val", "type": "serial_value_matches", "pattern": "pct: (-?[0-9.]+)", "input_pin": "A4", "tolerance": 3.0, "max_lag_ms": 500, "description": "percent correct"},
            ],
            "scenarios": [
                {"id": "s_hi", "name": "High concentration", "seed": 1, "duration_ms": 5000,
                 "analog": [{"pin": "A4", "segments": [{"t_ms": 0, "mv": 900}], "noise_mv": 5, "spikes": []}],
                 "digital": [], "floating": []},
            ],
        },
    )

    w(
        "heater_duty_ovf",
        pins=[{"pin": "A0", "role": "Room temperature", "type": "analog_input", "scale": "10 mV/°C"},
              {"pin": "D9", "role": "Heater enable", "type": "digital_output"}],
        spec="Heater on D9 must be ON when temperature on A0 is below 18 °C and OFF when above 22 °C.",
        sketch="""// intermediate int overflow: analogRead*5000 exceeds 16-bit int
const int HEAT=9;
bool on=false;
void setup(){pinMode(HEAT,OUTPUT);}
void loop(){
  int mv = analogRead(A0) * 5000 / 1023;
  float c = mv / 10.0;
  if(c < 18.0) on=true;
  else if(c > 22.0) on=false;
  digitalWrite(HEAT, on?HIGH:LOW);
  delay(50);
}
""",
        reference="""const int HEAT=9;
bool on=false;
void setup(){pinMode(HEAT,OUTPUT);}
void loop(){
  long mv = analogRead(A0) * 5000L / 1023;
  float c = mv / 10.0;
  if(c < 18.0) on=true;
  else if(c > 22.0) on=false;
  digitalWrite(HEAT, on?HIGH:LOW);
  delay(50);
}
""",
        truth=[{"id": "b1", "category": "integer_overflow", "description": "analogRead*5000 overflows 16-bit int before divide", "check_ids": ["a_follow"]}],
        checks={
            "assertions": [
                {"id": "a_follow", "type": "output_follows", "pin": "D9", "high_when": {"pin": "A0", "op": "<", "value": 18}, "low_when": {"pin": "A0", "op": ">", "value": 22}, "within_ms": 600, "description": "Heat below 18, off above 22"},
            ],
            "scenarios": [
                {"id": "s_cold", "name": "Cold 10 C", "seed": 1, "duration_ms": 4000,
                 "analog": [{"pin": "A0", "segments": [{"t_ms": 0, "mv": 100}], "noise_mv": 2, "spikes": []}],
                 "digital": [], "floating": []},
                {"id": "s_hot", "name": "Hot 30 C", "seed": 2, "duration_ms": 4000,
                 "analog": [{"pin": "A0", "segments": [{"t_ms": 0, "mv": 300}], "noise_mv": 2, "spikes": []}],
                 "digital": [], "floating": []},
            ],
        },
    )

    # ---------- inverted_pullup ----------
    w(
        "limit_switch_invert",
        pins=[{"pin": "D2", "role": "Limit switch to GND", "type": "digital_input", "active_low": True},
              {"pin": "D13", "role": "Motor enable", "type": "digital_output"}],
        spec="Limit switch on D2 with INPUT_PULLUP (pressed/active = LOW). Motor enable on D13 must be LOW (disabled) while the limit is active, and HIGH otherwise.",
        sketch="""// inverted: treats HIGH as pressed
void setup(){pinMode(2,INPUT_PULLUP); pinMode(13,OUTPUT);}
void loop(){
  bool hit = digitalRead(2)==HIGH;
  digitalWrite(13, hit ? LOW : HIGH);
}
""",
        reference="""void setup(){pinMode(2,INPUT_PULLUP); pinMode(13,OUTPUT);}
void loop(){
  bool hit = digitalRead(2)==LOW;
  digitalWrite(13, hit ? LOW : HIGH);
}
""",
        truth=[{"id": "b1", "category": "inverted_pullup", "description": "Treats pull-up HIGH as active limit", "check_ids": ["a_follow"]}],
        checks={
            "assertions": [
                {"id": "a_follow", "type": "output_follows", "pin": "D13", "low_when": {"pin": "D2", "op": "==", "value": 0}, "high_when": {"pin": "D2", "op": "==", "value": 1}, "within_ms": 100, "description": "Motor off while limit LOW"},
            ],
            "scenarios": [
                {"id": "s_hit", "name": "Press and release", "seed": 1, "duration_ms": 5000,
                 "analog": [], "floating": [],
                 "digital": [{"pin": "D2", "initial": 1, "events": [
                     {"t_ms": 800, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 2500, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                 ]}]},
            ],
        },
    )

    w(
        "estop_pullup_invert",
        pins=[{"pin": "D3", "role": "E-stop to GND", "type": "digital_input", "active_low": True},
              {"pin": "D5", "role": "Contactor", "type": "digital_output"}],
        spec="E-stop on D3 INPUT_PULLUP, active LOW. Contactor D5 must drop LOW when e-stop is held, and run HIGH when released.",
        sketch="""void setup(){pinMode(3,INPUT_PULLUP);pinMode(5,OUTPUT);}
void loop(){ digitalWrite(5, digitalRead(3)==HIGH ? LOW : HIGH); }
""",
        reference="""void setup(){pinMode(3,INPUT_PULLUP);pinMode(5,OUTPUT);}
void loop(){ digitalWrite(5, digitalRead(3)==LOW ? LOW : HIGH); }
""",
        truth=[{"id": "b1", "category": "inverted_pullup", "description": "E-stop polarity inverted vs pull-up wiring", "check_ids": ["a_follow"]}],
        checks={
            "assertions": [
                {"id": "a_follow", "type": "output_follows", "pin": "D5", "low_when": {"pin": "D3", "op": "==", "value": 0}, "high_when": {"pin": "D3", "op": "==", "value": 1}, "within_ms": 100, "description": "Contactor follows e-stop"},
            ],
            "scenarios": [
                {"id": "s_stop", "name": "E-stop hold", "seed": 3, "duration_ms": 4000,
                 "analog": [], "floating": [],
                 "digital": [{"pin": "D3", "initial": 1, "events": [
                     {"t_ms": 500, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 3000, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                 ]}]},
            ],
        },
    )

    # ---------- missing_failsafe ----------
    w(
        "fridge_failsafe",
        pins=[{"pin": "A3", "role": "Cabinet temperature", "type": "analog_input", "scale": "10 mV/°C"},
              {"pin": "D7", "role": "Compressor", "type": "digital_output"}],
        spec="Compressor D7 ON when A3 >= 8 °C, OFF when <= 4 °C. If the sensor is disconnected/floating or reads below 0 °C or above 60 °C, force compressor OFF within 500 ms.",
        sketch="""bool cool=false;
void setup(){pinMode(7,OUTPUT);}
void loop(){
  float c=analogRead(A3)*(5.0/1023.0)*100.0;
  if(c>=8) cool=true;
  else if(c<=4) cool=false;
  digitalWrite(7, cool?HIGH:LOW);
  delay(50);
}
""",
        reference="""bool cool=false;
void setup(){pinMode(7,OUTPUT);}
void loop(){
  float c=analogRead(A3)*(5.0/1023.0)*100.0;
  if(c<0 || c>60){ cool=false; }
  else if(c>=8) cool=true;
  else if(c<=4) cool=false;
  digitalWrite(7, cool?HIGH:LOW);
  delay(50);
}
""",
        truth=[{"id": "b1", "category": "missing_failsafe", "description": "No safe-OFF on floating/out-of-range probe", "check_ids": ["a_fault"]}],
        checks={
            "assertions": [
                {"id": "a_follow", "type": "output_follows", "pin": "D7", "high_when": {"pin": "A3", "op": ">=", "value": 8}, "low_when": {"pin": "A3", "op": "<=", "value": 4}, "within_ms": 500, "description": "Cooling band"},
                {"id": "a_fault", "type": "safe_state_on_fault", "floating_pin": "A3", "output_pin": "D7", "safe_value": 0, "within_ms": 500, "description": "Float forces OFF"},
            ],
            "scenarios": [
                {"id": "s_warm", "name": "Warm then float", "seed": 2, "duration_ms": 8000,
                 "analog": [{"pin": "A3", "segments": [{"t_ms": 0, "mv": 120}, {"t_ms": 2000, "mv": 120}], "noise_mv": 5, "spikes": []}],
                 "digital": [], "floating": [{"pin": "A3", "from_ms": 3000, "to_ms": 7000}]},
            ],
        },
    )

    w(
        "boiler_failsafe",
        pins=[{"pin": "A1", "role": "Boiler temperature", "type": "analog_input", "scale": "10 mV/°C"},
              {"pin": "D6", "role": "Gas valve", "type": "digital_output"}],
        spec="Gas valve D6 ON below 70 °C, OFF above 75 °C. Floating or >120 °C or <5 °C must close the valve (LOW).",
        sketch="""bool fire=false;
void setup(){pinMode(6,OUTPUT);}
void loop(){
  float t=analogRead(A1)*(5.0/1023.0)*100.0;
  if(t<70) fire=true; else if(t>75) fire=false;
  digitalWrite(6,fire);
  delay(40);
}
""",
        reference="""bool fire=false;
void setup(){pinMode(6,OUTPUT);}
void loop(){
  float t=analogRead(A1)*(5.0/1023.0)*100.0;
  if(t<5 || t>120){ fire=false; }
  else if(t<70) fire=true;
  else if(t>75) fire=false;
  digitalWrite(6,fire);
  delay(40);
}
""",
        truth=[{"id": "b1", "category": "missing_failsafe", "description": "Valve stays open on sensor fault", "check_ids": ["a_fault"]}],
        checks={
            "assertions": [
                {"id": "a_follow", "type": "output_follows", "pin": "D6", "high_when": {"pin": "A1", "op": "<", "value": 70}, "low_when": {"pin": "A1", "op": ">", "value": 75}, "within_ms": 500, "description": "Heat band"},
                {"id": "a_fault", "type": "safe_state_on_fault", "fault_when": {"pin": "A1", "op": ">", "value": 120}, "output_pin": "D6", "safe_value": 0, "within_ms": 500, "description": "Overrange closes valve"},
            ],
            "scenarios": [
                {"id": "s_runaway", "name": "Normal then overrange", "seed": 4, "duration_ms": 7000,
                 "analog": [{"pin": "A1", "segments": [{"t_ms": 0, "mv": 600}, {"t_ms": 2500, "mv": 1300}], "noise_mv": 5, "spikes": []}],
                 "digital": [], "floating": []},
            ],
        },
    )

    # ---------- off_by_one_timing / timed pulse ----------
    w(
        "blink_offbyone",
        pins=[{"pin": "D4", "role": "Indicator", "type": "digital_output"}],
        spec="On a rising edge of an internal 3.0 s one-shot started at t=0 from reset, hold D4 HIGH for exactly 3000 ms ±150 then LOW. Print `go` when the pulse starts.",
        sketch="""// pulse only 2000 ms
bool done=false;
void setup(){pinMode(4,OUTPUT); Serial.begin(9600); digitalWrite(4,HIGH); Serial.println("go");}
void loop(){
  if(!done && millis()>=2000){ digitalWrite(4,LOW); done=true; }
}
""",
        reference="""bool done=false;
void setup(){pinMode(4,OUTPUT); Serial.begin(9600); digitalWrite(4,HIGH); Serial.println("go");}
void loop(){
  if(!done && millis()>=3000){ digitalWrite(4,LOW); done=true; }
}
""",
        truth=[{"id": "b1", "category": "off_by_one_timing", "description": "Pulse ends at 2 s instead of 3 s", "check_ids": ["a_pulse"]}],
        checks={
            "assertions": [
                {"id": "a_pulse", "type": "timed_pulse", "pin": "D4", "trigger": {"pin": "D4", "op": "==", "value": 1}, "duration_ms": 3000, "tolerance_ms": 200, "within_ms": 50, "during_pulse": "ignore", "min_trigger_ms": 0, "description": "3 s high pulse from start"},
            ],
            "scenarios": [
                {"id": "s_boot", "name": "Boot pulse", "seed": 1, "duration_ms": 5000, "analog": [], "digital": [], "floating": []},
            ],
        },
    )

    # timed_pulse with trigger on D4==1 at start is weird because D4 is output. Better use a digital input trigger.
    # Fix blink_offbyone to use button trigger instead - rewrite:
    shutil.rmtree(ROOT / "blink_offbyone", ignore_errors=True)
    w(
        "blink_offbyone",
        pins=[{"pin": "D2", "role": "Start button", "type": "digital_input", "active_low": True},
              {"pin": "D4", "role": "Indicator", "type": "digital_output"}],
        spec="Each settled press of D2 (INPUT_PULLUP) starts a 3000 ms HIGH pulse on D4. Presses during the pulse are ignored.",
        sketch="""int prev=HIGH; bool on=false; unsigned long t0=0;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(4,OUTPUT);}
void loop(){
  int v=digitalRead(2);
  if(prev==HIGH && v==LOW && !on){ on=true; t0=millis(); digitalWrite(4,HIGH); }
  if(on && millis()-t0>=2000){ on=false; digitalWrite(4,LOW); }
  prev=v;
}
""",
        reference="""int stable=HIGH,last=HIGH; unsigned long ch=0; bool on=false; unsigned long t0=0;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(4,OUTPUT);}
void loop(){
  int v=digitalRead(2);
  if(v!=last){ch=millis();last=v;}
  if(millis()-ch>=30 && v!=stable){
    stable=v;
    if(stable==LOW && !on){ on=true; t0=millis(); digitalWrite(4,HIGH); }
  }
  if(on && millis()-t0>=3000){ on=false; digitalWrite(4,LOW); }
}
""",
        truth=[{"id": "b1", "category": "off_by_one_timing", "description": "Pulse length 2000 ms instead of 3000 ms", "check_ids": ["a_pulse"]}],
        checks={
            "assertions": [
                {"id": "a_pulse", "type": "timed_pulse", "pin": "D4", "trigger": {"pin": "D2", "op": "==", "value": 0}, "duration_ms": 3000, "tolerance_ms": 200, "within_ms": 120, "during_pulse": "ignore", "min_trigger_ms": 40, "description": "3 s pulse"},
            ],
            "scenarios": [
                {"id": "s_press", "name": "Single press", "seed": 1, "duration_ms": 6000,
                 "analog": [], "floating": [],
                 "digital": [{"pin": "D2", "initial": 1, "events": [
                     {"t_ms": 400, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 700, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                 ]}]},
            ],
        },
    )

    w(
        "hold_offbyone",
        pins=[{"pin": "D3", "role": "Hold button", "type": "digital_input", "active_low": True},
              {"pin": "D8", "role": "Armed LED", "type": "digital_output"}],
        spec="Arm LED D8 turns HIGH only after D3 has been held LOW continuously for 500 ms. Release turns it off immediately.",
        sketch="""// requires 600 ms by mistake
unsigned long down=0; bool held=false;
void setup(){pinMode(3,INPUT_PULLUP);pinMode(8,OUTPUT);}
void loop(){
  if(digitalRead(3)==LOW){
    if(!held){ held=true; down=millis(); }
    digitalWrite(8, millis()-down>=600 ? HIGH : LOW);
  } else { held=false; digitalWrite(8,LOW); }
}
""",
        reference="""unsigned long down=0; bool held=false;
void setup(){pinMode(3,INPUT_PULLUP);pinMode(8,OUTPUT);}
void loop(){
  if(digitalRead(3)==LOW){
    if(!held){ held=true; down=millis(); }
    digitalWrite(8, millis()-down>=500 ? HIGH : LOW);
  } else { held=false; digitalWrite(8,LOW); }
}
""",
        truth=[{"id": "b1", "category": "off_by_one_timing", "description": "Arm delay is 600 ms instead of 500 ms", "check_ids": ["a_follow"]}],
        checks={
            "assertions": [
                {"id": "a_follow", "type": "output_follows", "pin": "D8", "high_when": {"pin": "D3", "op": "==", "value": 0}, "low_when": {"pin": "D3", "op": "==", "value": 1}, "within_ms": 550, "description": "Armed after ~500 ms hold"},
            ],
            "scenarios": [
                {"id": "s_hold", "name": "Hold 800 ms", "seed": 1, "duration_ms": 4000,
                 "analog": [], "floating": [],
                 "digital": [{"pin": "D3", "initial": 1, "events": [
                     {"t_ms": 300, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 1100, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                 ]}]},
            ],
        },
    )

    # ---------- stuck_state_machine ----------
    w(
        "washer_stuck_sm",
        pins=[{"pin": "A0", "role": "Water level", "type": "analog_input", "scale": "10 mV/cm"},
              {"pin": "D9", "role": "Fill valve", "type": "digital_output"},
              {"pin": "D10", "role": "Drum motor", "type": "digital_output"}],
        spec="States: IDLE (both off), FILL (valve D9 on until level >= 25 cm), RUN (motor D10 on for wash while level stays >= 20 cm), then IDLE. Must leave RUN when level drops below 20 cm.",
        sketch="""enum {IDLE,FILL,RUN} st=IDLE;
void setup(){pinMode(9,OUTPUT);pinMode(10,OUTPUT);}
void loop(){
  float cm=analogRead(A0)*(5.0/1023.0)*100.0;
  if(st==IDLE && cm<10){ st=FILL; }
  if(st==FILL && cm>=25){ st=RUN; }
  // bug: never leaves RUN
  digitalWrite(9, st==FILL);
  digitalWrite(10, st==RUN);
  delay(40);
}
""",
        reference="""enum {IDLE,FILL,RUN} st=IDLE;
void setup(){pinMode(9,OUTPUT);pinMode(10,OUTPUT);}
void loop(){
  float cm=analogRead(A0)*(5.0/1023.0)*100.0;
  if(st==IDLE && cm<10) st=FILL;
  else if(st==FILL && cm>=25) st=RUN;
  else if(st==RUN && cm<20) st=IDLE;
  digitalWrite(9, st==FILL);
  digitalWrite(10, st==RUN);
  delay(40);
}
""",
        truth=[{"id": "b1", "category": "stuck_state_machine", "description": "RUN state never exits when level drops", "check_ids": ["a_motor"]}],
        checks={
            "assertions": [
                {"id": "a_motor", "type": "output_follows", "pin": "D10", "low_when": {"pin": "A0", "op": "<", "value": 20}, "within_ms": 600, "description": "Motor off below 20 cm"},
                {"id": "a_valve", "type": "output_follows", "pin": "D9", "high_when": {"pin": "A0", "op": "<", "value": 10}, "within_ms": 800, "description": "Fill when empty (loose)"},
            ],
            "scenarios": [
                {"id": "s_cycle", "name": "Fill then drain", "seed": 7, "duration_ms": 10000,
                 "analog": [{"pin": "A0", "segments": [
                     {"t_ms": 0, "mv": 50}, {"t_ms": 1500, "mv": 280}, {"t_ms": 4000, "mv": 280}, {"t_ms": 5500, "mv": 100}
                 ], "noise_mv": 5, "spikes": []}],
                 "digital": [], "floating": []},
            ],
        },
    )

    w(
        "lock_stuck_sm",
        pins=[{"pin": "D2", "role": "Request button", "type": "digital_input", "active_low": True},
              {"pin": "D3", "role": "Door closed sense", "type": "digital_input", "active_low": True},
              {"pin": "D9", "role": "Lock solenoid", "type": "digital_output"}],
        spec="Lock D9 engages (HIGH) when request D2 is pressed while door D3 is closed (LOW). Unlock when door opens (D3 HIGH). Must not stay locked after door opens.",
        sketch="""bool locked=false;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(3,INPUT_PULLUP);pinMode(9,OUTPUT);}
void loop(){
  if(digitalRead(2)==LOW && digitalRead(3)==LOW) locked=true;
  // bug: never clears
  digitalWrite(9, locked);
}
""",
        reference="""bool locked=false;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(3,INPUT_PULLUP);pinMode(9,OUTPUT);}
void loop(){
  if(digitalRead(2)==LOW && digitalRead(3)==LOW) locked=true;
  if(digitalRead(3)==HIGH) locked=false;
  digitalWrite(9, locked);
}
""",
        truth=[{"id": "b1", "category": "stuck_state_machine", "description": "Lock latches forever after first engage", "check_ids": ["a_unlock"]}],
        checks={
            "assertions": [
                {"id": "a_unlock", "type": "output_follows", "pin": "D9", "low_when": {"pin": "D3", "op": "==", "value": 1}, "within_ms": 200, "description": "Unlocked when door open"},
            ],
            "scenarios": [
                {"id": "s_lock", "name": "Lock then open door", "seed": 1, "duration_ms": 6000,
                 "analog": [], "floating": [],
                 "digital": [
                     {"pin": "D3", "initial": 0, "events": [
                         {"t_ms": 3000, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                     ]},
                     {"pin": "D2", "initial": 1, "events": [
                         {"t_ms": 500, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                         {"t_ms": 800, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                     ]},
                 ]},
            ],
        },
    )

    # ---------- wrong_pin ----------
    w(
        "wrongpin_led",
        pins=[{"pin": "D2", "role": "Button", "type": "digital_input", "active_low": True},
              {"pin": "D13", "role": "User LED", "type": "digital_output"}],
        spec="Button D2 INPUT_PULLUP lights the user LED on D13 while pressed (active LOW → LED HIGH).",
        sketch="""void setup(){pinMode(2,INPUT_PULLUP);pinMode(12,OUTPUT);} // wrong pin 12
void loop(){ digitalWrite(12, digitalRead(2)==LOW ? HIGH : LOW); }
""",
        reference="""void setup(){pinMode(2,INPUT_PULLUP);pinMode(13,OUTPUT);}
void loop(){ digitalWrite(13, digitalRead(2)==LOW ? HIGH : LOW); }
""",
        truth=[{"id": "b1", "category": "wrong_pin", "description": "Drives D12 instead of D13", "check_ids": ["a_follow"]}],
        checks={
            "assertions": [
                {"id": "a_follow", "type": "output_follows", "pin": "D13", "high_when": {"pin": "D2", "op": "==", "value": 0}, "low_when": {"pin": "D2", "op": "==", "value": 1}, "within_ms": 100, "description": "D13 follows button"},
            ],
            "scenarios": [
                {"id": "s_press", "name": "Press", "seed": 1, "duration_ms": 4000,
                 "analog": [], "floating": [],
                 "digital": [{"pin": "D2", "initial": 1, "events": [
                     {"t_ms": 500, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 2000, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                 ]}]},
            ],
        },
    )

    w(
        "wrongpin_relay",
        pins=[{"pin": "A0", "role": "Light sensor", "type": "analog_input", "scale": "1 mV/unit"},
              {"pin": "D8", "role": "Lamp relay", "type": "digital_output"}],
        spec="Relay D8 ON when A0 reading (mV as units) is below 400, OFF above 600.",
        sketch="""bool on=false;
void setup(){pinMode(7,OUTPUT);} // wrong
void loop(){
  float u=analogRead(A0)*(5000.0/1023.0);
  if(u<400) on=true; else if(u>600) on=false;
  digitalWrite(7,on);
  delay(30);
}
""",
        reference="""bool on=false;
void setup(){pinMode(8,OUTPUT);}
void loop(){
  float u=analogRead(A0)*(5000.0/1023.0);
  if(u<400) on=true; else if(u>600) on=false;
  digitalWrite(8,on);
  delay(30);
}
""",
        truth=[{"id": "b1", "category": "wrong_pin", "description": "Relay wired in code to D7 not D8", "check_ids": ["a_follow"]}],
        checks={
            "assertions": [
                {"id": "a_follow", "type": "output_follows", "pin": "D8", "high_when": {"pin": "A0", "op": "<", "value": 400}, "low_when": {"pin": "A0", "op": ">", "value": 600}, "within_ms": 400, "description": "Relay follows light"},
            ],
            "scenarios": [
                {"id": "s_dark", "name": "Dark", "seed": 1, "duration_ms": 4000,
                 "analog": [{"pin": "A0", "segments": [{"t_ms": 0, "mv": 200}], "noise_mv": 5, "spikes": []}],
                 "digital": [], "floating": []},
                {"id": "s_bright", "name": "Bright", "seed": 2, "duration_ms": 4000,
                 "analog": [{"pin": "A0", "segments": [{"t_ms": 0, "mv": 800}], "noise_mv": 5, "spikes": []}],
                 "digital": [], "floating": []},
            ],
        },
    )

    # ---------- serial_format ----------
    w(
        "serial_fmt_temp",
        pins=[{"pin": "A0", "role": "TMP36", "type": "analog_input", "scale": "10 mV/°C + 500 mV"}],
        spec="Every second print exactly `Temp: <celsius>` with a space after the colon. TMP36 on A0 (10 mV/°C, 500 mV offset). Within 1.5 °C.",
        sketch="""void setup(){Serial.begin(9600);}
void loop(){
  float v=analogRead(A0)*(5.0/1023.0);
  float c=(v-0.5)*100.0;
  Serial.print("temp="); // wrong format
  Serial.println(c);
  delay(1000);
}
""",
        reference="""void setup(){Serial.begin(9600);}
void loop(){
  float v=analogRead(A0)*(5.0/1023.0);
  float c=(v-0.5)*100.0;
  Serial.print("Temp: ");
  Serial.println(c);
  delay(1000);
}
""",
        truth=[{"id": "b1", "category": "serial_format", "description": "Wrong serial prefix temp= instead of Temp: ", "check_ids": ["a_period"]}],
        checks={
            "assertions": [
                {"id": "a_period", "type": "serial_period", "pattern": "^Temp: ", "period_ms": 1000, "tolerance_ms": 120, "description": "Temp: lines"},
                {"id": "a_val", "type": "serial_value_matches", "pattern": "Temp: (-?[0-9.]+)", "input_pin": "A0", "tolerance": 1.5, "max_lag_ms": 400, "description": "Value OK"},
            ],
            "scenarios": [
                {"id": "s_room", "name": "Room temp", "seed": 1, "duration_ms": 5000,
                 "analog": [{"pin": "A0", "segments": [{"t_ms": 0, "mv": 750}], "noise_mv": 5, "spikes": []}],
                 "digital": [], "floating": []},
            ],
        },
    )

    w(
        "serial_fmt_rpm",
        pins=[{"pin": "A5", "role": "Tach voltage", "type": "analog_input", "scale": "1 mV/rpm"}],
        spec="Print `RPM:<n>` (no space) once per second. A5 is 1 mV per rpm. Within 50 rpm.",
        sketch="""void setup(){Serial.begin(9600);}
void loop(){
  float rpm=analogRead(A5)*(5000.0/1023.0);
  Serial.print("rpm: "); // wrong case/space
  Serial.println(rpm);
  delay(1000);
}
""",
        reference="""void setup(){Serial.begin(9600);}
void loop(){
  float rpm=analogRead(A5)*(5000.0/1023.0);
  Serial.print("RPM:");
  Serial.println(rpm);
  delay(1000);
}
""",
        truth=[{"id": "b1", "category": "serial_format", "description": "Prints rpm: with space instead of RPM:", "check_ids": ["a_period"]}],
        checks={
            "assertions": [
                {"id": "a_period", "type": "serial_period", "pattern": "^RPM:", "period_ms": 1000, "tolerance_ms": 120, "description": "RPM: lines"},
                {"id": "a_val", "type": "serial_value_matches", "pattern": "RPM:(-?[0-9.]+)", "input_pin": "A5", "tolerance": 50, "max_lag_ms": 400, "description": "rpm value"},
            ],
            "scenarios": [
                {"id": "s_spin", "name": "1200 rpm", "seed": 1, "duration_ms": 5000,
                 "analog": [{"pin": "A5", "segments": [{"t_ms": 0, "mv": 1200}], "noise_mv": 10, "spikes": []}],
                 "digital": [], "floating": []},
            ],
        },
    )

    # ---------- timed_pulse length ----------
    w(
        "pulse_too_short",
        pins=[{"pin": "D2", "role": "Trigger", "type": "digital_input", "active_low": True},
              {"pin": "D8", "role": "Solenoid", "type": "digital_output"}],
        spec="Press D2 starts a 2500 ms solenoid pulse on D8. Ignore retriggers during the pulse.",
        sketch="""bool on=false; unsigned long t0; int prev=HIGH;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(8,OUTPUT);}
void loop(){
  int v=digitalRead(2);
  if(prev==HIGH && v==LOW && !on){on=true;t0=millis();digitalWrite(8,HIGH);}
  if(on && millis()-t0>=1000){on=false;digitalWrite(8,LOW);}
  prev=v;
}
""",
        reference="""bool on=false; unsigned long t0; int stable=HIGH,last=HIGH; unsigned long ch=0;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(8,OUTPUT);}
void loop(){
  int v=digitalRead(2);
  if(v!=last){ch=millis();last=v;}
  if(millis()-ch>=25 && v!=stable){ stable=v; if(stable==LOW && !on){on=true;t0=millis();digitalWrite(8,HIGH);} }
  if(on && millis()-t0>=2500){on=false;digitalWrite(8,LOW);}
}
""",
        truth=[{"id": "b1", "category": "timed_pulse_length", "description": "Solenoid pulse is 1 s not 2.5 s", "check_ids": ["a_pulse"]}],
        checks={
            "assertions": [
                {"id": "a_pulse", "type": "timed_pulse", "pin": "D8", "trigger": {"pin": "D2", "op": "==", "value": 0}, "duration_ms": 2500, "tolerance_ms": 200, "within_ms": 120, "during_pulse": "ignore", "min_trigger_ms": 30, "description": "2.5 s pulse"},
            ],
            "scenarios": [
                {"id": "s1", "name": "Press", "seed": 1, "duration_ms": 5000,
                 "analog": [], "floating": [],
                 "digital": [{"pin": "D2", "initial": 1, "events": [
                     {"t_ms": 300, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 600, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                 ]}]},
            ],
        },
    )

    w(
        "pulse_too_long",
        pins=[{"pin": "D4", "role": "Trigger", "type": "digital_input", "active_low": True},
              {"pin": "D9", "role": "Injector", "type": "digital_output"}],
        spec="D4 press → D9 HIGH for 800 ms only.",
        sketch="""bool on=false; unsigned long t0; int prev=HIGH;
void setup(){pinMode(4,INPUT_PULLUP);pinMode(9,OUTPUT);}
void loop(){
  int v=digitalRead(4);
  if(prev==HIGH && v==LOW && !on){on=true;t0=millis();digitalWrite(9,HIGH);}
  if(on && millis()-t0>=2000){on=false;digitalWrite(9,LOW);}
  prev=v;
}
""",
        reference="""bool on=false; unsigned long t0; int stable=HIGH,last=HIGH; unsigned long ch=0;
void setup(){pinMode(4,INPUT_PULLUP);pinMode(9,OUTPUT);}
void loop(){
  int v=digitalRead(4);
  if(v!=last){ch=millis();last=v;}
  if(millis()-ch>=25 && v!=stable){ stable=v; if(stable==LOW && !on){on=true;t0=millis();digitalWrite(9,HIGH);} }
  if(on && millis()-t0>=800){on=false;digitalWrite(9,LOW);}
}
""",
        truth=[{"id": "b1", "category": "timed_pulse_length", "description": "Injector pulse 2 s instead of 800 ms", "check_ids": ["a_pulse"]}],
        checks={
            "assertions": [
                {"id": "a_pulse", "type": "timed_pulse", "pin": "D9", "trigger": {"pin": "D4", "op": "==", "value": 0}, "duration_ms": 800, "tolerance_ms": 150, "within_ms": 120, "during_pulse": "ignore", "min_trigger_ms": 30, "description": "800 ms pulse"},
            ],
            "scenarios": [
                {"id": "s1", "name": "Press", "seed": 2, "duration_ms": 4000,
                 "analog": [], "floating": [],
                 "digital": [{"pin": "D4", "initial": 1, "events": [
                     {"t_ms": 200, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 500, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                 ]}]},
            ],
        },
    )

    # ---------- missing volatile (ISR) ----------
    w(
        "volatile_isr_count",
        pins=[{"pin": "D2", "role": "Pulse input INT0", "type": "digital_input", "active_low": True},
              {"pin": "D13", "role": "Activity LED", "type": "digital_output"}],
        spec="Count falling edges on D2 via interrupt. Light D13 while the count since reset is odd. Count must update from the ISR (use volatile).",
        sketch="""int edges=0; // missing volatile
void onEdge(){ edges++; }
void setup(){
  pinMode(2,INPUT_PULLUP);
  pinMode(13,OUTPUT);
  attachInterrupt(digitalPinToInterrupt(2), onEdge, FALLING);
}
void loop(){ digitalWrite(13, (edges & 1) ? HIGH : LOW); }
""",
        reference="""volatile int edges=0;
void onEdge(){ edges++; }
void setup(){
  pinMode(2,INPUT_PULLUP);
  pinMode(13,OUTPUT);
  attachInterrupt(digitalPinToInterrupt(2), onEdge, FALLING);
}
void loop(){ digitalWrite(13, (edges & 1) ? HIGH : LOW); }
""",
        truth=[{"id": "b1", "category": "missing_volatile", "description": "ISR counter not volatile; LED may ignore edges", "check_ids": ["a_follow"]}],
        checks={
            "assertions": [
                {"id": "a_follow", "type": "output_follows", "pin": "D13", "mode": "edge", "high_when": {"pin": "D2", "op": "==", "value": 0}, "within_ms": 200, "min_trigger_ms": 20, "description": "LED reacts to edges"},
            ],
            "scenarios": [
                {"id": "s_edges", "name": "Several edges", "seed": 1, "duration_ms": 5000,
                 "analog": [], "floating": [],
                 "digital": [{"pin": "D2", "initial": 1, "events": [
                     {"t_ms": 400, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 600, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 1200, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 1400, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 2000, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 2200, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                 ]}]},
            ],
        },
    )

    w(
        "volatile_isr_flag",
        pins=[{"pin": "D3", "role": "INT1 alarm in", "type": "digital_input", "active_low": True},
              {"pin": "D8", "role": "Latch LED", "type": "digital_output"}],
        spec="On falling edge of D3, latch D8 HIGH until reset (never clears in this sketch). Flag set in ISR must be volatile.",
        sketch="""bool tripped=false; // missing volatile
void isr(){ tripped=true; }
void setup(){ pinMode(3,INPUT_PULLUP); pinMode(8,OUTPUT); attachInterrupt(digitalPinToInterrupt(3), isr, FALLING); }
void loop(){ digitalWrite(8, tripped?HIGH:LOW); }
""",
        reference="""volatile bool tripped=false;
void isr(){ tripped=true; }
void setup(){ pinMode(3,INPUT_PULLUP); pinMode(8,OUTPUT); attachInterrupt(digitalPinToInterrupt(3), isr, FALLING); }
void loop(){ digitalWrite(8, tripped?HIGH:LOW); }
""",
        truth=[{"id": "b1", "category": "missing_volatile", "description": "ISR flag not volatile so latch may never set", "check_ids": ["a_edge"]}],
        checks={
            "assertions": [
                {"id": "a_edge", "type": "output_follows", "pin": "D8", "mode": "edge", "high_when": {"pin": "D3", "op": "==", "value": 0}, "within_ms": 200, "min_trigger_ms": 20, "description": "Latches on edge"},
            ],
            "scenarios": [
                {"id": "s1", "name": "Trip", "seed": 1, "duration_ms": 4000,
                 "analog": [], "floating": [],
                 "digital": [{"pin": "D3", "initial": 1, "events": [
                     {"t_ms": 800, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 1200, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                 ]}]},
            ],
        },
    )

    # ---------- dual-bug cases ----------
    w(
        "dual_hyst_failsafe",
        pins=[{"pin": "A2", "role": "Greenhouse temp", "type": "analog_input", "scale": "10 mV/°C"},
              {"pin": "D9", "role": "Vent fan", "type": "digital_output"}],
        spec="Vent fan D9 ON at >=28 °C, OFF at <=24 °C. Floating sensor or temp >100 °C or <0 °C must force fan ON (fail-safe cool).",
        sketch="""bool on=false;
void setup(){pinMode(9,OUTPUT);}
void loop(){
  float c=analogRead(A2)*(5.0/1023.0)*100.0;
  on = c>=28; // no hyst, no failsafe
  digitalWrite(9,on);
  delay(50);
}
""",
        reference="""bool on=false;
void setup(){pinMode(9,OUTPUT);}
void loop(){
  float c=analogRead(A2)*(5.0/1023.0)*100.0;
  if(c<0 || c>100){ on=true; }
  else if(c>=28) on=true;
  else if(c<=24) on=false;
  digitalWrite(9,on);
  delay(50);
}
""",
        truth=[
            {"id": "b1", "category": "missing_hysteresis", "description": "Single threshold causes chatter", "check_ids": ["a_chatter"]},
            {"id": "b2", "category": "missing_failsafe", "description": "No fail-safe on floating probe", "check_ids": ["a_fault"]},
        ],
        checks={
            "assertions": [
                {"id": "a_follow", "type": "output_follows", "pin": "D9", "high_when": {"pin": "A2", "op": ">=", "value": 28}, "low_when": {"pin": "A2", "op": "<=", "value": 24}, "within_ms": 500, "description": "Band"},
                {"id": "a_chatter", "type": "max_toggles", "pin": "D9", "max_toggles": 2, "window_ms": 5000, "description": "No chatter"},
                {"id": "a_fault", "type": "safe_state_on_fault", "floating_pin": "A2", "output_pin": "D9", "safe_value": 1, "within_ms": 600, "description": "Float → fan ON"},
            ],
            "scenarios": [
                {"id": "s_hover", "name": "Hover 28", "seed": 3, "duration_ms": 8000,
                 "analog": [{"pin": "A2", "segments": [{"t_ms": 0, "mv": 280}], "noise_mv": 30, "spikes": []}],
                 "digital": [], "floating": []},
                {"id": "s_float", "name": "Then float", "seed": 4, "duration_ms": 8000,
                 "analog": [{"pin": "A2", "segments": [{"t_ms": 0, "mv": 200}], "noise_mv": 5, "spikes": []}],
                 "digital": [], "floating": [{"pin": "A2", "from_ms": 2500, "to_ms": 7000}]},
            ],
        },
    )

    w(
        "dual_debounce_invert",
        pins=[{"pin": "D2", "role": "Toggle button", "type": "digital_input", "active_low": True},
              {"pin": "D13", "role": "Lamp", "type": "digital_output"}],
        spec="D2 INPUT_PULLUP toggles D13 once per settled press (active LOW). Debounce required.",
        sketch="""bool lit=false; int prev=HIGH;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(13,OUTPUT);}
void loop(){
  int v=digitalRead(2);
  // inverted edge sense + no debounce
  if(prev==LOW && v==HIGH){ lit=!lit; digitalWrite(13,lit); }
  prev=v;
}
""",
        reference="""bool lit=false; int stable=HIGH,last=HIGH; unsigned long ch=0;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(13,OUTPUT);}
void loop(){
  int v=digitalRead(2);
  if(v!=last){ch=millis();last=v;}
  if(millis()-ch>=40 && v!=stable){
    stable=v;
    if(stable==LOW){ lit=!lit; digitalWrite(13,lit); }
  }
}
""",
        truth=[
            {"id": "b1", "category": "inverted_pullup", "description": "Toggles on release edge instead of press", "check_ids": ["a_tpp"]},
            {"id": "b2", "category": "missing_debounce", "description": "No debounce on the button", "check_ids": ["a_tpp"]},
        ],
        checks={
            "assertions": [
                {"id": "a_tpp", "type": "toggle_per_press", "input_pin": "D2", "output_pin": "D13", "active_level": 0, "settle_ms": 40, "within_ms": 150, "description": "One toggle per press"},
            ],
            "scenarios": [
                {"id": "s_bounce", "name": "Bouncy presses", "seed": 2, "duration_ms": 6000,
                 "analog": [], "floating": [],
                 "digital": [{"pin": "D2", "initial": 1, "events": [
                     {"t_ms": 400, "value": 0, "bounce_ms": 18, "bounce_count": 8},
                     {"t_ms": 800, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                     {"t_ms": 2000, "value": 0, "bounce_ms": 20, "bounce_count": 10},
                     {"t_ms": 2500, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                 ]}]},
            ],
        },
    )

    w(
        "dual_block_scale",
        pins=[{"pin": "A0", "role": "Flow sensor", "type": "analog_input", "scale": "2 mV/Lph"},
              {"pin": "D8", "role": "Alarm LED", "type": "digital_output"}],
        spec="If flow (A0, 2 mV per L/h) is below 100 L/h, light D8. Print `flow: <Lph>` every 500 ms. Stay responsive (no multi-second delay).",
        sketch="""void setup(){Serial.begin(9600);pinMode(8,OUTPUT);}
void loop(){
  float flow = analogRead(A0); // wrong scale
  digitalWrite(8, flow < 100 ? HIGH : LOW);
  Serial.print("flow: "); Serial.println(flow);
  delay(2000); // blocking
}
""",
        reference="""void setup(){Serial.begin(9600);pinMode(8,OUTPUT);}
void loop(){
  float mv=analogRead(A0)*(5000.0/1023.0);
  float flow=mv/2.0;
  digitalWrite(8, flow < 100 ? HIGH : LOW);
  Serial.print("flow: "); Serial.println(flow);
  delay(500);
}
""",
        truth=[
            {"id": "b1", "category": "wrong_unit_scaling", "description": "Uses raw ADC as L/h", "check_ids": ["a_val"]},
            {"id": "b2", "category": "blocking_delay", "description": "delay(2000) stalls the loop", "check_ids": ["a_resp"]},
        ],
        checks={
            "assertions": [
                {"id": "a_period", "type": "serial_period", "pattern": "^flow: ", "period_ms": 500, "tolerance_ms": 120, "description": "2 Hz log"},
                {"id": "a_val", "type": "serial_value_matches", "pattern": "flow: (-?[0-9.]+)", "input_pin": "A0", "tolerance": 10, "max_lag_ms": 400, "description": "flow value"},
                {"id": "a_resp", "type": "responsive", "max_gap_ms": 900, "start_ms": 100, "description": "Responsive"},
            ],
            "scenarios": [
                {"id": "s_flow", "name": "Steady flow", "seed": 1, "duration_ms": 5000,
                 "analog": [{"pin": "A0", "segments": [{"t_ms": 0, "mv": 300}], "noise_mv": 5, "spikes": []}],
                 "digital": [], "floating": []},
            ],
        },
    )

    # ---------- correct cases ----------
    def correct(cid: str, pins: list, spec: str, sketch: str, checks: dict) -> None:
        w(cid, pins=pins, spec=spec, sketch=sketch, reference=sketch, truth=[], checks=checks)

    correct(
        "correct_duct_fan",
        [{"pin": "A1", "role": "Duct temp", "type": "analog_input", "scale": "10 mV/°C"},
         {"pin": "D5", "role": "Fan", "type": "digital_output"}],
        "Fan D5 ON >= 35 °C, OFF <= 32 °C with hysteresis.",
        """bool on=false;
void setup(){pinMode(5,OUTPUT);}
void loop(){
  float c=analogRead(A1)*(5.0/1023.0)*100.0;
  if(c>=35) on=true; else if(c<=32) on=false;
  digitalWrite(5,on); delay(50);
}
""",
        {"assertions": [
            {"id": "a_follow", "type": "output_follows", "pin": "D5", "high_when": {"pin": "A1", "op": ">=", "value": 35}, "low_when": {"pin": "A1", "op": "<=", "value": 32}, "within_ms": 500, "description": "band"},
            {"id": "a_chatter", "type": "max_toggles", "pin": "D5", "max_toggles": 2, "window_ms": 5000, "description": "stable"},
        ], "scenarios": [
            {"id": "s_hover", "name": "Hover", "seed": 3, "duration_ms": 8000,
             "analog": [{"pin": "A1", "segments": [{"t_ms": 0, "mv": 350}], "noise_mv": 35, "spikes": []}],
             "digital": [], "floating": []},
        ]},
    )

    correct(
        "correct_cabin_latch",
        [{"pin": "D3", "role": "Button", "type": "digital_input", "active_low": True},
         {"pin": "D8", "role": "Lamp", "type": "digital_output"}],
        "Debounced toggle lamp on D8 from D3 pull-up button.",
        """bool lit=false; int stable=HIGH,last=HIGH; unsigned long ch=0;
void setup(){pinMode(3,INPUT_PULLUP);pinMode(8,OUTPUT);}
void loop(){
  int v=digitalRead(3);
  if(v!=last){ch=millis();last=v;}
  if(millis()-ch>=40 && v!=stable){ stable=v; if(stable==LOW){lit=!lit;digitalWrite(8,lit);} }
}
""",
        {"assertions": [
            {"id": "a_tpp", "type": "toggle_per_press", "input_pin": "D3", "output_pin": "D8", "active_level": 0, "settle_ms": 40, "within_ms": 150, "description": "one toggle"},
        ], "scenarios": [
            {"id": "s_bounce", "name": "Bounce", "seed": 2, "duration_ms": 6000,
             "analog": [], "floating": [],
             "digital": [{"pin": "D3", "initial": 1, "events": [
                 {"t_ms": 500, "value": 0, "bounce_ms": 20, "bounce_count": 10},
                 {"t_ms": 900, "value": 1, "bounce_ms": 0, "bounce_count": 0},
                 {"t_ms": 2000, "value": 0, "bounce_ms": 18, "bounce_count": 8},
                 {"t_ms": 2400, "value": 1, "bounce_ms": 0, "bounce_count": 0},
             ]}]},
        ]},
    )

    correct(
        "correct_brine_ph",
        [{"pin": "A0", "role": "pH", "type": "analog_input", "scale": "500 mV/pH"}],
        "Print `pH: <v>` each second. 500 mV/pH.",
        """void setup(){Serial.begin(9600);}
void loop(){
  float mv=analogRead(A0)*(5000.0/1023.0);
  Serial.print("pH: "); Serial.println(mv/500.0);
  delay(1000);
}
""",
        {"assertions": [
            {"id": "a_period", "type": "serial_period", "pattern": "^pH: ", "period_ms": 1000, "tolerance_ms": 120, "description": "1 Hz"},
            {"id": "a_val", "type": "serial_value_matches", "pattern": "pH: (-?[0-9.]+)", "input_pin": "A0", "tolerance": 0.2, "max_lag_ms": 400, "description": "value"},
        ], "scenarios": [
            {"id": "s", "name": "pH7", "seed": 1, "duration_ms": 5000,
             "analog": [{"pin": "A0", "segments": [{"t_ms": 0, "mv": 3500}], "noise_mv": 5, "spikes": []}],
             "digital": [], "floating": []},
        ]},
    )

    correct(
        "correct_fridge",
        [{"pin": "A3", "role": "Temp", "type": "analog_input", "scale": "10 mV/°C"},
         {"pin": "D7", "role": "Compressor", "type": "digital_output"}],
        "Compressor ON >=8 °C, OFF <=4 °C; floating → OFF.",
        """bool cool=false;
void setup(){pinMode(7,OUTPUT);}
void loop(){
  float c=analogRead(A3)*(5.0/1023.0)*100.0;
  if(c<0||c>60) cool=false;
  else if(c>=8) cool=true;
  else if(c<=4) cool=false;
  digitalWrite(7,cool); delay(50);
}
""",
        {"assertions": [
            {"id": "a_follow", "type": "output_follows", "pin": "D7", "high_when": {"pin": "A3", "op": ">=", "value": 8}, "low_when": {"pin": "A3", "op": "<=", "value": 4}, "within_ms": 500, "description": "band"},
            {"id": "a_fault", "type": "safe_state_on_fault", "floating_pin": "A3", "output_pin": "D7", "safe_value": 0, "within_ms": 500, "description": "float off"},
        ], "scenarios": [
            {"id": "s", "name": "warm float", "seed": 2, "duration_ms": 8000,
             "analog": [{"pin": "A3", "segments": [{"t_ms": 0, "mv": 120}], "noise_mv": 5, "spikes": []}],
             "digital": [], "floating": [{"pin": "A3", "from_ms": 3000, "to_ms": 7000}]},
        ]},
    )

    correct(
        "correct_limit",
        [{"pin": "D2", "role": "Limit", "type": "digital_input", "active_low": True},
         {"pin": "D13", "role": "Motor", "type": "digital_output"}],
        "Motor D13 LOW while limit D2 active (LOW), else HIGH.",
        """void setup(){pinMode(2,INPUT_PULLUP);pinMode(13,OUTPUT);}
void loop(){ digitalWrite(13, digitalRead(2)==LOW ? LOW : HIGH); }
""",
        {"assertions": [
            {"id": "a_follow", "type": "output_follows", "pin": "D13", "low_when": {"pin": "D2", "op": "==", "value": 0}, "high_when": {"pin": "D2", "op": "==", "value": 1}, "within_ms": 100, "description": "ok"},
        ], "scenarios": [
            {"id": "s", "name": "hit", "seed": 1, "duration_ms": 4000,
             "analog": [], "floating": [],
             "digital": [{"pin": "D2", "initial": 1, "events": [
                 {"t_ms": 800, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                 {"t_ms": 2500, "value": 1, "bounce_ms": 0, "bounce_count": 0},
             ]}]},
        ]},
    )

    correct(
        "correct_pulse",
        [{"pin": "D2", "role": "Trigger", "type": "digital_input", "active_low": True},
         {"pin": "D8", "role": "Out", "type": "digital_output"}],
        "2.5 s pulse on D8 per D2 press.",
        """bool on=false; unsigned long t0; int stable=HIGH,last=HIGH; unsigned long ch=0;
void setup(){pinMode(2,INPUT_PULLUP);pinMode(8,OUTPUT);}
void loop(){
  int v=digitalRead(2);
  if(v!=last){ch=millis();last=v;}
  if(millis()-ch>=25 && v!=stable){ stable=v; if(stable==LOW && !on){on=true;t0=millis();digitalWrite(8,HIGH);} }
  if(on && millis()-t0>=2500){on=false;digitalWrite(8,LOW);}
}
""",
        {"assertions": [
            {"id": "a_pulse", "type": "timed_pulse", "pin": "D8", "trigger": {"pin": "D2", "op": "==", "value": 0}, "duration_ms": 2500, "tolerance_ms": 200, "within_ms": 120, "during_pulse": "ignore", "min_trigger_ms": 30, "description": "pulse"},
        ], "scenarios": [
            {"id": "s", "name": "press", "seed": 1, "duration_ms": 5000,
             "analog": [], "floating": [],
             "digital": [{"pin": "D2", "initial": 1, "events": [
                 {"t_ms": 300, "value": 0, "bounce_ms": 0, "bounce_count": 0},
                 {"t_ms": 600, "value": 1, "bounce_ms": 0, "bounce_count": 0},
             ]}]},
        ]},
    )

    correct(
        "correct_beacon",
        [{"pin": "D12", "role": "LED", "type": "digital_output"}],
        "Blink 500 ms on/off; print tick each rising edge.",
        """unsigned long last=0; bool on=false;
void setup(){pinMode(12,OUTPUT);Serial.begin(9600);last=millis();}
void loop(){
  if(millis()-last>=500){ last+=500; on=!on; digitalWrite(12,on); if(on) Serial.println("tick"); }
}
""",
        {"assertions": [
            {"id": "a_period", "type": "serial_period", "pattern": "^tick$", "period_ms": 1000, "tolerance_ms": 120, "description": "1 Hz"},
        ], "scenarios": [
            {"id": "s", "name": "blink", "seed": 1, "duration_ms": 6000, "analog": [], "digital": [], "floating": []},
        ]},
    )

    correct(
        "correct_washer",
        [{"pin": "A0", "role": "Level", "type": "analog_input", "scale": "10 mV/cm"},
         {"pin": "D9", "role": "Valve", "type": "digital_output"},
         {"pin": "D10", "role": "Motor", "type": "digital_output"}],
        "IDLE/FILL/RUN washer; leave RUN when level < 20 cm.",
        """enum {IDLE,FILL,RUN} st=IDLE;
void setup(){pinMode(9,OUTPUT);pinMode(10,OUTPUT);}
void loop(){
  float cm=analogRead(A0)*(5.0/1023.0)*100.0;
  if(st==IDLE && cm<10) st=FILL;
  else if(st==FILL && cm>=25) st=RUN;
  else if(st==RUN && cm<20) st=IDLE;
  digitalWrite(9, st==FILL); digitalWrite(10, st==RUN); delay(40);
}
""",
        {"assertions": [
            {"id": "a_motor", "type": "output_follows", "pin": "D10", "low_when": {"pin": "A0", "op": "<", "value": 20}, "within_ms": 600, "description": "motor off"},
        ], "scenarios": [
            {"id": "s", "name": "cycle", "seed": 7, "duration_ms": 10000,
             "analog": [{"pin": "A0", "segments": [
                 {"t_ms": 0, "mv": 50}, {"t_ms": 1500, "mv": 280}, {"t_ms": 4000, "mv": 280}, {"t_ms": 5500, "mv": 100}
             ], "noise_mv": 5, "spikes": []}],
             "digital": [], "floating": []},
        ]},
    )

    correct(
        "correct_serial_temp",
        [{"pin": "A0", "role": "TMP36", "type": "analog_input", "scale": "10 mV/°C + 500 mV"}],
        "Print Temp: each second.",
        """void setup(){Serial.begin(9600);}
void loop(){
  float v=analogRead(A0)*(5.0/1023.0);
  Serial.print("Temp: "); Serial.println((v-0.5)*100.0);
  delay(1000);
}
""",
        {"assertions": [
            {"id": "a_period", "type": "serial_period", "pattern": "^Temp: ", "period_ms": 1000, "tolerance_ms": 120, "description": "fmt"},
            {"id": "a_val", "type": "serial_value_matches", "pattern": "Temp: (-?[0-9.]+)", "input_pin": "A0", "tolerance": 1.5, "max_lag_ms": 400, "description": "val"},
        ], "scenarios": [
            {"id": "s", "name": "room", "seed": 1, "duration_ms": 5000,
             "analog": [{"pin": "A0", "segments": [{"t_ms": 0, "mv": 750}], "noise_mv": 5, "spikes": []}],
             "digital": [], "floating": []},
        ]},
    )

    correct(
        "correct_heater",
        [{"pin": "A0", "role": "Temp", "type": "analog_input", "scale": "10 mV/°C"},
         {"pin": "D9", "role": "Heater", "type": "digital_output"}],
        "Heat below 18 °C, off above 22 °C.",
        """bool on=false;
void setup(){pinMode(9,OUTPUT);}
void loop(){
  float c=analogRead(A0)*(5.0/1023.0)*100.0;
  if(c<18) on=true; else if(c>22) on=false;
  digitalWrite(9,on); delay(50);
}
""",
        {"assertions": [
            {"id": "a_follow", "type": "output_follows", "pin": "D9", "high_when": {"pin": "A0", "op": "<", "value": 18}, "low_when": {"pin": "A0", "op": ">", "value": 22}, "within_ms": 600, "description": "band"},
        ], "scenarios": [
            {"id": "s_cold", "name": "cold", "seed": 1, "duration_ms": 4000,
             "analog": [{"pin": "A0", "segments": [{"t_ms": 0, "mv": 100}], "noise_mv": 2, "spikes": []}],
             "digital": [], "floating": []},
            {"id": "s_hot", "name": "hot", "seed": 2, "duration_ms": 4000,
             "analog": [{"pin": "A0", "segments": [{"t_ms": 0, "mv": 300}], "noise_mv": 2, "spikes": []}],
             "digital": [], "floating": []},
        ]},
    )


if __name__ == "__main__":
    main()
