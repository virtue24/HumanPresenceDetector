/*
   --------------------------------------------------------------
   Arduino relay controller for use with the Python ArduinoConnection
   --------------------------------------------------------------
   Commands (newline-terminated):
     PING                             → PONG
     LED ON / LED OFF                 → OK
     STATUS                           → READY
     RELAY_ON;<pin>;<delay_ms>;<dur>  → OK | BUSY | ERR
     Hi, are you arduino?             → This is Arduino
   --------------------------------------------------------------
   Set RELAYS_ACTIVE_LOW to true if your relay board is “low-level
   trigger” (coil energises when its input pin is LOW).
   -------------------------------------------------------------- */

#include <Arduino.h>

/* ---------- configuration ---------- */
const uint32_t BAUD = 9600;

/* Relay pins actually wired */
const int RELAY_PINS[] = {2, 3, 5, 7, 13};
const uint8_t NUM_RELAYS = sizeof(RELAY_PINS) / sizeof(RELAY_PINS[0]);

/* true  = active-LOW modules
   false = active-HIGH modules */
#define RELAYS_ACTIVE_LOW  true

/* ----------------------------------- */
const char *HANDSHAKE_Q = "Hi, are you arduino?";
const char *HANDSHAKE_A = "This is Arduino";
const uint8_t LED_PIN   = LED_BUILTIN;

/* millis-based schedules */
uint32_t relayOnAt [NUM_RELAYS] = {0};
uint32_t relayOffAt[NUM_RELAYS] = {0};

/* drive relay respecting active-low logic */
inline void setRelay(uint8_t idx, bool on)
{
  bool level = RELAYS_ACTIVE_LOW ? !on : on;
  digitalWrite(RELAY_PINS[idx], level);
}

/* read a CR/LF-terminated line */
bool readLine(String &out)
{
  while (Serial.available())
  {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') return true;
    out += c;
    if (out.length() > 120) out = "";          // overflow guard
  }
  return false;
}

/* ---------------- command handler ---------------- */
void handleCommand(const String &cmd)
{
  if (cmd.equalsIgnoreCase("PING"))
  {
    Serial.println("PONG");
  }
  else if (cmd.equalsIgnoreCase("LED ON"))
  {
    digitalWrite(LED_PIN, HIGH);  Serial.println("OK");
  }
  else if (cmd.equalsIgnoreCase("LED OFF"))
  {
    digitalWrite(LED_PIN, LOW);   Serial.println("OK");
  }
  else if (cmd.equalsIgnoreCase("STATUS"))
  {
    Serial.println("READY");
  }
  else if (cmd.equalsIgnoreCase(HANDSHAKE_Q))
  {
    Serial.println(HANDSHAKE_A);
  }
  else if (cmd.startsWith("RELAY_ON;"))         // RELAY_ON;pin;delay;dur
  {
    int p1 = cmd.indexOf(';');
    int p2 = cmd.indexOf(';', p1 + 1);
    int p3 = cmd.indexOf(';', p2 + 1);
    if (p1 < 0 || p2 < 0 || p3 < 0) { Serial.println("ERR"); return; }

    int  pin      = cmd.substring(p1 + 1, p2).toInt();
    long delayMs  = cmd.substring(p2 + 1, p3).toInt();
    long durMs    = cmd.substring(p3 + 1).toInt();

    bool found = false;
    for (uint8_t i = 0; i < NUM_RELAYS; ++i)
    {
      if (RELAY_PINS[i] == pin)
      {
        found = true;
        uint32_t now = millis();
        if (relayOffAt[i] > now)
        {
          Serial.println("BUSY");
        }
        else
        {
          relayOnAt[i]  = now + (uint32_t)delayMs;
          relayOffAt[i] = relayOnAt[i] + (uint32_t)durMs;
          Serial.println("OK");
        }
        break;
      }
    }
    if (!found) Serial.println("ERR");
  }
  else if (cmd.startsWith("RELAY_ON_OVERWRITE;"))   // RELAY_ON_OVERWRITE;pin;delay;dur
  {
    int p1 = cmd.indexOf(';');
    int p2 = cmd.indexOf(';', p1 + 1);
    int p3 = cmd.indexOf(';', p2 + 1);
    if (p1 < 0 || p2 < 0 || p3 < 0) { Serial.println("ERR"); return; }

    int  pin      = cmd.substring(p1 + 1, p2).toInt();
    long delayMs  = cmd.substring(p2 + 1, p3).toInt();
    long durMs    = cmd.substring(p3 + 1).toInt();

    bool found = false;
    for (uint8_t i = 0; i < NUM_RELAYS; ++i)
    {
      if (RELAY_PINS[i] == pin)
      {
        found = true;
        uint32_t now = millis();
        // No busy check - always overwrite
        relayOnAt[i]  = now + (uint32_t)delayMs;
        relayOffAt[i] = relayOnAt[i] + (uint32_t)durMs;
        Serial.println("OK");
        break;
      }
    }
    if (!found) Serial.println("ERR");
  }
  else
  {
    Serial.println("ERR");
  }
}

/* ------------------ setup ------------------ */
void setup()
{
  Serial.begin(BAUD);
  while (!Serial) { }                   // wait for USB CDC

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  for (uint8_t i = 0; i < NUM_RELAYS; ++i)
  {
    pinMode(RELAY_PINS[i], OUTPUT);
    setRelay(i, false);                 // ensure OFF at boot
  }
}

/* ------------------- loop ------------------- */
void loop()
{
  static String line = "";

  if (readLine(line))
  {
    line.trim();
    if (line.length() > 0) handleCommand(line);
    line = "";
  }

  /* non-blocking relay scheduler */
  uint32_t now = millis();
  for (uint8_t i = 0; i < NUM_RELAYS; ++i)
  {
    if (relayOnAt[i] && now >= relayOnAt[i])
    {
      setRelay(i, true);   relayOnAt[i] = 0;
    }
    if (relayOffAt[i] && now >= relayOffAt[i])
    {
      setRelay(i, false);  relayOffAt[i] = 0;
    }
  }
}
