// lib/mqttClient.ts
import mqtt from 'mqtt';            // default export 불러오기
import type { MqttClient } from 'mqtt';

const client: MqttClient = mqtt.connect({  // mqtt.connect() 호출
  protocol: 'wss',
  host: process.env.NEXT_PUBLIC_IOT_ENDPOINT!,
  port: 443,
  path: '/mqtt',
});

export default client;
