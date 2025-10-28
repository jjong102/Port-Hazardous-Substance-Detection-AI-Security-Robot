#include<SoftwareSerial.h>
#include<TinyGPS++.h>
TinyGPSPlus  loc;
SoftwareSerial gps(11,12);

void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);//
  pinMode(A0,INPUT);
  pinMode(A1,INPUT);
  pinMode(A2,INPUT);
  gps.begin(9600);//
}

void loop() {
  // put your main code here, to run repeatedly:
  while(gps.available()){
    loc.encode(gps.read());
  }
  analogRead(A0);
  int vpin = analogRead(A0);
  analogRead(A1);
  int Npin = analogRead(A1);
  analogRead(A2);
  int cpin = analogRead(A2);
  float vppm = vpin/1023.0 * 5.0;
  float nppm = Npin/1023.0 * 5.0;
  float cppm = cpin/1023.0 * 5.0;
  Serial.print("VOCs=");Serial.print(vppm);
  Serial.print(",NH3=");Serial.print(nppm);
  Serial.print(",CO=");Serial.print(cppm);
  Serial.print(",GPS=");Serial.print(loc.location.lat(),6);
  Serial.print(",");Serial.println(loc.location.lng(),6);
  delay(100);
}
