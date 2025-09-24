#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "꾹의 S24+";
const char* password = "qkrtjd123";

const char* HAZ_URL  = "http://43.202.250.26:5000/data/hazard";
const char* DATA_URL = "http://43.202.250.26:5000/data";

#define RXD1 10
#define TXD1 11

void setup() {
  Serial.begin(115200);
  Serial1.begin(9600, SERIAL_8N1, RXD1, TXD1);
  Serial1.setTimeout(2000);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
  Serial.println("WiFi 연결됨");
}

void loop() {
  if (!Serial1.available()) return;

  String data = Serial1.readStringUntil('\n');
  data.trim();
  Serial.println(data);

  int vocsIdx = data.indexOf("VOCs=");
  int nh3Idx  = data.indexOf("NH3=");
  int coIdx   = data.indexOf("CO=");
  int gpsIdx  = data.indexOf("GPS=");

  if (vocsIdx==-1 || nh3Idx==-1 || coIdx==-1 || gpsIdx==-1) return;

  String vocs = data.substring(vocsIdx + 5, nh3Idx - 1);
  String nh3  = data.substring(nh3Idx  + 4, coIdx  - 1);
  String co   = data.substring(coIdx   + 3, gpsIdx - 1);
  String gps  = data.substring(gpsIdx  + 4);
  gps.trim();

  // GPS "lat,lng" 추출 (마지막 글자 잘리지 않게!)
  int comma = gps.indexOf(',');
  if (comma < 0) return;
  String lat = gps.substring(0, comma);   // <- lngidx-1 아니고 comma까지 그대로
  String lng = gps.substring(comma + 1);
  lat.trim(); lng.trim();

  // 1) GPS 먼저 전송 (/data, type=GPS, value="lat,lng")
  postJson(DATA_URL, String("{\"type\":\"GPS\",\"value\":\"") + lat + "," + lng + "\"}");

  // 2) 센서값은 /data/hazard 로 전송 (lat/lng 반드시 포함)
  sendHaz("VOC", vocs, lat, lng);
  delay(300);
  sendHaz("NH3", nh3,  lat, lng);
  delay(300);
  sendHaz("CO",  co,   lat, lng);
  delay(300);
}

void sendHaz(const char* typ, String val, String lat, String lng) {
  val.trim();
  String body = String("{\"substance\":\"") + typ +
                "\",\"concentration\":\"" + val +
                "\",\"lat\":\"" + lat +
                "\",\"lng\":\"" + lng + "\"}";
  postJson(HAZ_URL, body);
}

void postJson(const char* url, const String& json) {
  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(json);
  Serial.printf("[POST %s] %d\n", url, code);
  http.end();
}