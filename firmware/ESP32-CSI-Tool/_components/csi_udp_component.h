#ifndef ESP32_CSI_UDP_COMPONENT_H
#define ESP32_CSI_UDP_COMPONENT_H

/*
 * CSI verisini seri port yerine (veya seri porta ek olarak) UDP ile bir
 * sunucuya gönderir. 2026-08-24'te eklendi.
 *
 * NEDEN: Kartları USB kablosuna bağlı tutmak zorunda kalmamak için. Kablo
 * kısıtı yüzünden iki kartı odanın uçlarına koyamıyorduk ve algılama hacmi
 * bir masa üstü kadar kalıyordu - bu da otur/ayakta ile yürüme ayrımını
 * fiziksel olarak imkansız hale getiriyordu.
 *
 * TASARIM:
 *  - CSI geri çağırımı (callback) WiFi görevinde çalışıyor; orada ağ işlemi
 *    yapmak sistemi bloklar. Bu yüzden satırlar bir KUYRUĞA konuyor, ayrı bir
 *    görev kuyruktan alıp gönderiyor. Kuyruk dolarsa satır DÜŞÜRÜLÜR
 *    (bloklamaktansa veri kaybetmek yeğdir - kaybı sayıyoruz).
 *  - Sunucunun IP'si ELLE AYARLANMIYOR. Sunucu ağa yayın (broadcast) paketi
 *    atıyor, biz o paketin geldiği adresi sunucu adresi olarak öğreniyoruz.
 *    Böylece laptop IP'si değiştiğinde firmware'i yeniden yüklemek gerekmiyor.
 *    Ayrıca bu gelen paketler CSI üretimini de tetikliyor (CSI, ALINAN
 *    çerçevelerden üretilir) - yani keşif ve örnekleme hızı aynı mekanizma.
 */

#include <string.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_log.h"

#define CSI_UDP_PORT 2223
#define CSI_UDP_LINE_MAX 1000
#define CSI_UDP_QUEUE_LEN 24

typedef struct {
    uint16_t len;
    char buf[CSI_UDP_LINE_MAX];
} csi_udp_line_t;

static QueueHandle_t csi_udp_queue = NULL;
static int csi_udp_sock = -1;
static struct sockaddr_in csi_udp_server;
static volatile bool csi_udp_server_known = false;
static volatile uint32_t csi_udp_dropped = 0;
static volatile uint32_t csi_udp_sent = 0;
static const char *CSI_UDP_TAG = "csi_udp";

/* CSI geri çağırımından çağrılır. ASLA bloklamaz. */
static inline void csi_udp_enqueue(const char *s, size_t len) {
    if (csi_udp_queue == NULL) return;
    if (len >= CSI_UDP_LINE_MAX) len = CSI_UDP_LINE_MAX - 1;

    csi_udp_line_t item;
    item.len = (uint16_t) len;
    memcpy(item.buf, s, len);
    item.buf[len] = '\0';

    /* timeout=0: kuyruk doluysa bekleme, düşür. */
    if (xQueueSend(csi_udp_queue, &item, 0) != pdTRUE) {
        csi_udp_dropped++;
    }
}

/* Sunucudan gelen paketleri dinler; hem sunucu adresini öğrenir hem de bu
 * paketlerin alınması CSI üretimini tetikler. */
static void csi_udp_rx_task(void *arg) {
    char buf[128];
    struct sockaddr_in from;
    socklen_t from_len = sizeof(from);
    while (1) {
        int n = recvfrom(csi_udp_sock, buf, sizeof(buf), 0,
                         (struct sockaddr *) &from, &from_len);
        if (n <= 0) {
            vTaskDelay(10 / portTICK_PERIOD_MS);
            continue;
        }
        /* Sunucu adresi değiştiyse güncelle (laptop yeniden bağlanmış olabilir) */
        if (!csi_udp_server_known ||
            csi_udp_server.sin_addr.s_addr != from.sin_addr.s_addr) {
            csi_udp_server.sin_family = AF_INET;
            csi_udp_server.sin_port = htons(CSI_UDP_PORT);
            csi_udp_server.sin_addr = from.sin_addr;
            csi_udp_server_known = true;
            ESP_LOGI(CSI_UDP_TAG, "Sunucu bulundu: %s", inet_ntoa(from.sin_addr));
        }
    }
}

static void csi_udp_tx_task(void *arg) {
    csi_udp_line_t item;
    while (1) {
        if (xQueueReceive(csi_udp_queue, &item, portMAX_DELAY) != pdTRUE) continue;
        if (!csi_udp_server_known) continue;  /* sunucu daha bulunmadı, at */
        int r = sendto(csi_udp_sock, item.buf, item.len, 0,
                       (const struct sockaddr *) &csi_udp_server,
                       sizeof(csi_udp_server));
        if (r < 0) {
            csi_udp_dropped++;
            vTaskDelay(1);
        } else {
            csi_udp_sent++;
        }
    }
}

/* Ne kadar veri gitti / düştü - seri porttan izlemek için */
static void csi_udp_stats_task(void *arg) {
    while (1) {
        vTaskDelay(10000 / portTICK_PERIOD_MS);
        ESP_LOGI(CSI_UDP_TAG, "gonderilen=%u dusen=%u sunucu=%s",
                 csi_udp_sent, csi_udp_dropped,
                 csi_udp_server_known ? inet_ntoa(csi_udp_server.sin_addr) : "yok");
    }
}

static void csi_udp_init() {
    csi_udp_queue = xQueueCreate(CSI_UDP_QUEUE_LEN, sizeof(csi_udp_line_t));
    if (csi_udp_queue == NULL) {
        ESP_LOGE(CSI_UDP_TAG, "kuyruk olusturulamadi");
        return;
    }

    csi_udp_sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (csi_udp_sock < 0) {
        ESP_LOGE(CSI_UDP_TAG, "soket olusturulamadi");
        return;
    }

    /* Sunucunun yayın paketlerini alabilmek için porta bağlan */
    struct sockaddr_in local = {};
    local.sin_family = AF_INET;
    local.sin_port = htons(CSI_UDP_PORT);
    local.sin_addr.s_addr = htonl(INADDR_ANY);
    if (bind(csi_udp_sock, (struct sockaddr *) &local, sizeof(local)) < 0) {
        ESP_LOGE(CSI_UDP_TAG, "bind basarisiz");
    }

    xTaskCreatePinnedToCore(&csi_udp_rx_task, "csi_udp_rx", 4096, NULL, 5, NULL, 0);
    xTaskCreatePinnedToCore(&csi_udp_tx_task, "csi_udp_tx", 4096, NULL, 5, NULL, 0);
    xTaskCreatePinnedToCore(&csi_udp_stats_task, "csi_udp_stats", 3072, NULL, 1, NULL, 0);
    ESP_LOGI(CSI_UDP_TAG, "UDP CSI cikisi hazir (port %d), sunucu keşfi bekleniyor",
             CSI_UDP_PORT);
}

#endif //ESP32_CSI_UDP_COMPONENT_H
