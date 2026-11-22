#include <Arduino.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <WiFi.h>
#include <vector>

#include "team_info.h"
#include "team_update.h"

const int address_count = 13; // total number of addresses in the list

const char* team_names[address_count] PROGMEM = {
  "debug test", // debug
  "RAAM", // 1
  "Matthew^2", // 5
  "IDC", // 7
  "Solidly Not Working", // 8
  "Overclocked", // 13
  "spam musubi", // 15
  "Blind leading the blind", // 18
  "KZR", // 19
  "Forklift Certified", // 21
  "Placeholder", // 22
  "Among Us Imposters", // 23
  "Crazy Turtles", // 28
};

const uint8_t address_list[address_count][6] PROGMEM = {
  {0xec, 0xe3, 0x34, 0x21, 0x8c, 0xa0}, // debug
  {0x80, 0xf3, 0xda, 0x41, 0x45, 0xe8}, // 1
  {0xd4, 0xe9, 0xf4, 0xb3, 0xce, 0xc0}, // 5
  {0x58, 0x2a, 0xbd, 0x70, 0xf9, 0x54}, // 7
  {0x80, 0xf3, 0xda, 0x42, 0xb1, 0x24}, // 8
  {0x70, 0x4b, 0xca, 0x90, 0x43, 0xd0}, // 13
  {0x80, 0xf3, 0xda, 0x41, 0x45, 0xa4}, // 15
  {0x80, 0xf3, 0xda, 0x40, 0xdb, 0x88}, // 18
  {0x80, 0xf3, 0xda, 0x42, 0x7e, 0x30}, // 19
  {0x58, 0x2a, 0xbd, 0x70, 0xa0, 0xd8}, // 21
  {0x80, 0xf3, 0xda, 0x40, 0xe3, 0x14}, // 22
  {0x80, 0xf3, 0xda, 0x41, 0x68, 0x00}, // 23
  {0xd4, 0xe9, 0xf4, 0xb3, 0x29, 0x34}, // 28
};



constexpr size_t MAX_ESPNOW_PAYLOAD = 250;
constexpr size_t TEAMS_PER_PACKET =
    (MAX_ESPNOW_PAYLOAD - HEADER_SIZE) / sizeof(TeamInfo);
static_assert(TEAMS_PER_PACKET > 0, "TeamInfo does not fit in ESP-NOW packet");

volatile bool send_finished = false;
volatile esp_now_send_status_t send_status = ESP_NOW_SEND_FAIL;

// ESP32 Arduino core 2.x callback signature.
void onDataSent(const uint8_t *mac, esp_now_send_status_t status) {
  send_status = status;
  send_finished = true;
}

bool broadcastPacket(const uint8_t *packet, size_t length) {
  if (length > MAX_ESPNOW_PAYLOAD) return false;

  send_finished = false;
  send_status = ESP_NOW_SEND_FAIL;
  if (esp_now_send(broadcast_address, packet, length) != ESP_OK) {
    Serial.println("ESP-NOW queue/send error");
    return false;
  }

  const uint32_t started = millis();
  while (!send_finished && millis() - started < 2000) {
    delay(1);
  }
  if (!send_finished) {
    Serial.println("ESP-NOW send callback timed out");
    return false;
  }
  if (send_status != ESP_NOW_SEND_SUCCESS) {
    Serial.println("ESP-NOW reported send failure");
    return false;
  }
  // Broadcast status is not confirmation that any receiver received the packet.
  delay(50);
  return true;
}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  // All controllers must use the same Wi-Fi channel.

  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }
  esp_now_register_send_cb(onDataSent);

  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, broadcast_address, 6);
  peer.channel = 0; // Current Wi-Fi channel
  peer.encrypt = false;
  if (esp_now_add_peer(&peer) != ESP_OK) {
    Serial.println("Could not add broadcast peer");
    return;
  }

  std::vector<TeamInfo> team_info_list;
  team_info_list.reserve(address_count);
  for (int i = 0; i < address_count; ++i) {
    team_info_list.emplace_back(team_names[i], address_list[i]);
  }

  const uint8_t clear_packet[HEADER_SIZE] = {
      const_header[0], const_header[1], type_clear};
  if (!broadcastPacket(clear_packet, sizeof(clear_packet))) {
    Serial.println("Clear broadcast failed; aborting update");
    return;
  }
  Serial.println("Clear broadcast sent");

  for (size_t offset = 0; offset < team_info_list.size(); offset += TEAMS_PER_PACKET) {
    const size_t count = min(TEAMS_PER_PACKET, team_info_list.size() - offset);
    uint8_t packet[MAX_ESPNOW_PAYLOAD] = {};
    packet[0] = const_header[0];
    packet[1] = const_header[1];
    packet[2] = type_new_team;
    memcpy(packet + HEADER_SIZE, team_info_list.data() + offset,
           count * sizeof(TeamInfo));
    const size_t length = HEADER_SIZE + count * sizeof(TeamInfo);
    if (!broadcastPacket(packet, length)) {
      Serial.println("Team broadcast failed; update incomplete");
      return;
    }
    Serial.printf("Broadcast %u team(s), %u bytes\n",
                  (unsigned)count, (unsigned)length);
  }
  Serial.println("Update broadcast complete (receiver delivery not verified)");
}

void loop() {
  // One-shot update on boot.
}
