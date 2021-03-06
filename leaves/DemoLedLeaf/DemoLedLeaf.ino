#include <Device.h>
#include <Leaf.h>
#include <ESP8266WiFi.h>
#include <ESP8266WiFiMulti.h>
#include <ArduinoOTA.h>
#include <elapsedMillis.h>


ESP8266WiFiMulti WiFiMulti;
const short int BUILTIN_LED1 = 2; //GPIO2


Leaf leaf("demo_led", "1.0.1", "a6527c60-62aa-4c0f-a76d-144f52c52927", "pass");
BooleanDevice led_device("led_on", false, device_mode::OUT);

void setup() {
  WiFiMulti.addAP("user", "pass");

  while(WiFiMulti.run() != WL_CONNECTED) {
    delay(100);
  }
  Serial.println("Connected to wifi");
  ArduinoOTA.setPort(8266);

  ArduinoOTA.onStart([]() {
    Serial.println("Start");
  });
  ArduinoOTA.onEnd([]() {
    Serial.println("\nEnd");
  });
  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
    Serial.printf("Progress: %u%%\r", (progress / (total / 100)));
  });
  ArduinoOTA.onError([](ota_error_t error) {
    Serial.printf("Error[%u]: ", error);
    if (error == OTA_AUTH_ERROR) Serial.println("Auth Failed");
    else if (error == OTA_BEGIN_ERROR) Serial.println("Begin Failed");
    else if (error == OTA_CONNECT_ERROR) Serial.println("Connect Failed");
    else if (error == OTA_RECEIVE_ERROR) Serial.println("Receive Failed");
    else if (error == OTA_END_ERROR) Serial.println("End Failed");
  });
  ArduinoOTA.setHostname("LED-Leaf");
  ArduinoOTA.begin();

  // Hostname defaults to esp8266-[ChipID]
  leaf.connect("192.168.1.95", 8000, "/hub/");
  leaf.register_device(led_device);
  led_device.on_change = handle_change;
  pinMode(BUILTIN_LED1, OUTPUT); // Initialize the BUILTIN_LED1 pin as an output
  digitalWrite(BUILTIN_LED1, HIGH);
}

void loop() {
  ArduinoOTA.handle();
  leaf.update();
}

void handle_change(Device& device) {
  boolean newValue = ((BooleanDevice&) device).get_value();
  if(newValue == 1) {
    digitalWrite(BUILTIN_LED1, LOW);
  } else {
    digitalWrite(BUILTIN_LED1, HIGH);
  }
}

