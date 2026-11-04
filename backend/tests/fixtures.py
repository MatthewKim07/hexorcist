"""Reference assertions and hand-written correct firmware for each preset.

These test the deterministic engine and pipeline without an LLM: the planted bug
must fail, and correct firmware must pass every scenario. If correct firmware
fails, the evaluator is being unfair, and the agent could never verify a fix.
"""

ASSERTIONS = {
    "thermostat": [
        {"type": "output_follows", "pin": "D9", "high_when": {"pin": "A0", "op": ">=", "value": 30}, "low_when": {"pin": "A0", "op": "<=", "value": 27}, "within_ms": 500, "description": "Fan on at 30 C, off at 27 C"},
        {"type": "max_toggles", "pin": "D9", "max_toggles": 2, "window_ms": 5000, "description": "Fan must not short-cycle"},
        {"type": "safe_state_on_fault", "fault_when": {"pin": "A0", "op": "<", "value": 2}, "output_pin": "D9", "safe_value": 1, "within_ms": 1000, "description": "Disconnected sensor forces fan on"},
        {"type": "safe_state_on_fault", "fault_when": {"pin": "A0", "op": ">", "value": 120}, "output_pin": "D9", "safe_value": 1, "within_ms": 1000, "description": "Out-of-range sensor forces fan on"},
    ],
    "button": [
        {"type": "toggle_per_press", "input_pin": "D2", "output_pin": "D13", "active_level": 0, "settle_ms": 50, "within_ms": 100, "description": "One toggle per press"},
        {"type": "max_toggles", "pin": "D13", "max_toggles": 1, "window_ms": 100, "description": "No double toggles"},
    ],
    "logger": [
        {"type": "serial_period", "pattern": "^Temp: ", "period_ms": 1000, "tolerance_ms": 100, "description": "One line per second"},
        {"type": "serial_value_matches", "pattern": "Temp: (-?[0-9.]+)", "input_pin": "A0", "tolerance": 1.0, "max_lag_ms": 300, "description": "Printed temperature is correct"},
    ],
    "alarm": [
        {"type": "output_follows", "pin": "D8", "high_when": {"pin": "D2", "op": "==", "value": 0}, "within_ms": 100, "mode": "edge", "description": "Press starts the siren within 100 ms"},
        {"type": "serial_period", "pattern": "^hb$", "period_ms": 500, "tolerance_ms": 100, "description": "Heartbeat every 500 ms"},
        {"type": "responsive", "max_gap_ms": 700, "description": "Never silent for more than 700 ms"},
    ],
}

CORRECT_FIRMWARE = {
    "thermostat": """// Thermostat fan controller
// LM35 temperature sensor on A0, fan driver on D9.
const int SENSOR_PIN = A0;
const int FAN_PIN = 9;
const float FAN_ON_C = 30.0;
const float FAN_OFF_C = 27.0;
const float FAULT_LOW_C = 2.0;
const float FAULT_HIGH_C = 120.0;
// A new state must persist before it counts, within the 500 ms and 1000 ms deadlines,
// so noise beyond the hysteresis band and one-sample glitches cannot switch the fan.
const int SWITCH_SAMPLES = 4;
const int FAULT_SAMPLES = 5;

bool fanOn = false;
int onCount = 0;
int offCount = 0;
int faultCount = 0;

void setup()
{
    pinMode(FAN_PIN, OUTPUT);
    Serial.begin(9600);
}

void loop()
{
    int raw = analogRead(SENSOR_PIN);
    float tempC = raw * (5.0 / 1023.0) * 100.0;
    bool outOfRange = tempC < FAULT_LOW_C || tempC > FAULT_HIGH_C;

    faultCount = outOfRange ? faultCount + 1 : 0;
    onCount = (!outOfRange && tempC >= FAN_ON_C) ? onCount + 1 : 0;
    offCount = (!outOfRange && tempC <= FAN_OFF_C) ? offCount + 1 : 0;

    if (faultCount >= FAULT_SAMPLES || onCount >= SWITCH_SAMPLES)
    {
        fanOn = true;
    }
    else if (offCount >= SWITCH_SAMPLES)
    {
        fanOn = false;
    }

    digitalWrite(FAN_PIN, fanOn ? HIGH : LOW);

    Serial.print("temp=");
    Serial.println(tempC);
    delay(100);
}
""",
    "button": """// Push button toggles an LED
// Button on D2 to ground, using the internal pull-up. LED on D13.
const int BUTTON_PIN = 2;
const int LED_PIN = 13;
const unsigned long DEBOUNCE_MS = 25;

int stableState = HIGH;
int lastReading = HIGH;
unsigned long lastChange = 0;
bool ledOn = false;

void setup()
{
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(LED_PIN, OUTPUT);
}

void loop()
{
    int reading = digitalRead(BUTTON_PIN);

    if (reading != lastReading)
    {
        lastChange = millis();
        lastReading = reading;
    }

    if (millis() - lastChange >= DEBOUNCE_MS && reading != stableState)
    {
        stableState = reading;
        if (stableState == LOW)
        {
            ledOn = !ledOn;
            digitalWrite(LED_PIN, ledOn ? HIGH : LOW);
        }
    }
}
""",
    "logger": """// Temperature logger
// TMP36 sensor on A0. Prints the temperature once per second.
const int SENSOR_PIN = A0;

void setup()
{
    Serial.begin(9600);
}

void loop()
{
    int raw = analogRead(SENSOR_PIN);
    float volts = raw * (5.0 / 1023.0);
    float tempC = (volts - 0.5) * 100.0;

    Serial.print("Temp: ");
    Serial.print(tempC);
    Serial.println(" C");
    delay(1000);
}
""",
    "alarm": """// Panic alarm
// Button on D2 to ground, siren on D8, heartbeat printed over serial.
const int BUTTON_PIN = 2;
const int SIREN_PIN = 8;
const unsigned long SIREN_MS = 3000;
const unsigned long HEARTBEAT_MS = 500;

bool sirenOn = false;
unsigned long sirenStart = 0;
unsigned long lastBeat = 0;

void setup()
{
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(SIREN_PIN, OUTPUT);
    Serial.begin(9600);
}

void loop()
{
    unsigned long now = millis();

    if (!sirenOn && digitalRead(BUTTON_PIN) == LOW)
    {
        sirenOn = true;
        sirenStart = now;
        digitalWrite(SIREN_PIN, HIGH);
    }

    if (sirenOn && now - sirenStart >= SIREN_MS)
    {
        sirenOn = false;
        digitalWrite(SIREN_PIN, LOW);
    }

    if (now - lastBeat >= HEARTBEAT_MS)
    {
        lastBeat += HEARTBEAT_MS;
        Serial.println("hb");
    }
}
""",
}
