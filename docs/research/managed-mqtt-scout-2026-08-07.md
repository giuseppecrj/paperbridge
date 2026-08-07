# Managed MQTT scout for Paperbridge

Research date: 2026-08-07  
Status: documentation facts from official primary sources. Not a physical verification of any cloud broker on the purchased ESP32-S3-ETH.

## Requirements (Paperbridge)

| Requirement | Source in repo |
| --- | --- |
| One ESP32 device on MicroPython 1.28 | `docs/research/source-register.md`, `AGENTS.md` |
| MQTT 3.1.1, QoS 1, non-retained jobs and results | `docs/architecture.md`, `docs/protocol.md` |
| Prepared MQTT jobs ≤ 65,536 bytes | `docs/protocol.md`, `docs/security.md` |
| Device opens outbound connection (no inbound port) | current `mqtt_adapter.py` client model |
| No durable cloud replay required | one-boot job ledger only; QoS redelivery handled on device |
| Eventual production security (TLS, auth) | `docs/security.md` (MQTT/TLS not implemented yet) |
| Prefer existing `umqtt.simple` path | `firmware/micropython/src/mqtt_adapter.py` imports `umqtt.simple.MQTTClient` with username/password, no TLS today |

## Client baseline (device)

- Current factory builds `MQTTClient(client_id, host, port=…, user=…, password=…, keepalive=…)` with no `ssl` argument.
- Upstream `umqtt.simple` supports MQTT 3.1.1, QoS 0/1, username/password, and TLS via `ssl=` / `ssl_params=` (or an `SSLContext`). It does not support QoS 2.  
  Source: <https://github.com/micropython/micropython-lib/blob/master/micropython/umqtt.simple/README.rst>  
  Source: <https://github.com/micropython/micropython-lib/blob/master/micropython/umqtt.simple/umqtt/simple.py>
- MicroPython 1.28 `ssl` supports `SSLContext`, `CERT_REQUIRED`, `load_verify_locations` / `cadata`, `server_hostname` (SNI), and client cert chains. `CERT_REQUIRED` needs a correct device clock.  
  Source: <https://docs.micropython.org/en/v1.28.0/library/ssl.html>
- Repo risk already recorded: MQTT/TLS may exhaust or fragment ESP32 memory (`README.md`).

---

## Comparison matrix

| Criterion | AWS IoT Core | HiveMQ Cloud | EMQX Cloud | Azure Event Grid MQTT (extra) |
| --- | --- | --- | --- | --- |
| MQTT 3.1.1 / QoS 1 | Yes (QoS 0/1) | Yes (3.1/3.1.1/5; Serverless lists MQTT over TLS) | Yes (3.1.1 via umqtt guide) | Yes (3.1.1 and 5; QoS 0/1) |
| Max publish payload | **128 KB** (hard) | Not published as a Cloud free-tier hard limit; self-managed default max packet is large; billing normalizes at **5 KB** | Serverless **1 MB** | **512 KB** |
| Fits 65,536-byte jobs | Yes | Likely yes; confirm on chosen plan | Yes | Yes |
| Device outbound client | Yes | Yes | Yes | Yes |
| Non-retained app traffic | App-controlled; retained messages exist as a separate feature | App-controlled | App-controlled; retained quotas exist but optional | App-controlled; retain limited; MQTT 3.1.1 retain/QoS2 publish fails |
| Default device auth | **X.509 client cert** on 8883/443 | Serverless: **username/password** + TLS; client certs on Starter+ | Serverless: **username/password** + **TLS required** | **Cert / Entra JWT / OAuth JWT / webhook** — no plain password auth |
| TLS required | Yes (TLS 1.2/1.3) | Yes for Cloud | Yes for Serverless (8883) | Yes (TLS 1.2/1.3, 8883) |
| Free / cheap entry | 12-month Free Tier: 2.25M connection minutes, 500k messages (legacy-style free tier still documented; new accounts also get Free Tier credits) | Serverless free: 100 connections, 10 GB/month | Serverless free quota: **1M session-minutes** + **1 GB traffic** + 1M rule actions / month; spend limit can pin to free | 1M MQTT operations free/month (metered); throughput units billed |
| Production price shape | Connectivity + messages in **5 KB** slices (65 KB ≈ 13 metered msgs) + optional rules | Starter ≈ **$0.34/hour** + **$0.80/million** normalized messages | After free: **$2 / M session-minutes**, **$0.15 / GB**; Dedicated Flex from ~**$0.32/hour** | Throughput unit hours + operations (64 KB units) |
| Ops burden for one device | High: things, policies, certs or custom auth Lambda, IoT endpoint | Low–medium: console credentials; Starter adds RBAC/certs | Low: console user/pass + CA download | High: namespace, TUs, cert/JWT identity model |
| umqtt.simple without major firmware work | **No** — mTLS or custom-auth path | **Mostly yes** — TLS + user/pass | **Mostly yes** — official ESP32 MicroPython guide | **No** — no username/password device path |

---

## Option notes

### 1. AWS IoT Core

**Fit for message size and protocol**

- MQTT payload limit is **128 KB**; connect/publish larger than that is rejected.  
  Source: <https://docs.aws.amazon.com/general/latest/gr/iot-core.html#message-broker-limits>
- MQTT over TLS with X.509 client certificates on port **8883** (or 443 with ALPN).  
  Source: <https://docs.aws.amazon.com/iot/latest/developerguide/protocols.html>
- QoS 0 and 1 only (matches Paperbridge).

**Auth / TLS**

- Default device path is **mutual TLS with X.509 client certificates**, not the username/password model used today.  
  Source: <https://docs.aws.amazon.com/iot/latest/developerguide/x509-client-certs.html>  
  Source: <https://docs.aws.amazon.com/iot/latest/developerguide/protocols.html>
- Custom authentication exists but is an extra authorizer (Lambda) and endpoint configuration path, not a drop-in Mosquitto substitute.

**Pricing**

- Free Tier (documented): 2,250,000 connection minutes, 500,000 messages, plus shadow/registry/rules allowances for 12 months from account creation; new Free Tier credit program also documented from 2025-07-15.  
  Source: <https://aws.amazon.com/iot-core/pricing/>
- Connectivity example rate: **$0.08 per million connection minutes** (region-dependent examples on the pricing page).
- Messaging metered in **5 KB** increments; an 8 KB message counts as two. A max Paperbridge job (~64 KB payload) meters as **13** messages in + **13** out if delivered once.  
  Source: <https://aws.amazon.com/iot-core/pricing/>

**MicroPython**

- AWS has an official MicroPython getting-started blog, but it is cert-centric and not a trivial `umqtt` username/password swap.  
  Source: <https://aws.amazon.com/blogs/iot/using-micropython-to-get-started-with-aws-iot-core/>
- Device work: client key/cert on flash, TLS wrap, policy/thing provisioning, and likely more RAM than plain TCP Mosquitto.

**Verdict:** Protocol and 65 KB size fit. Auth model and ops surface are the wrong size for one-device private bring-up. Defer until multi-device AWS-centric production is a real requirement.

### 2. HiveMQ Cloud

**Fit**

- Serverless free: **100 connections**, **10 GB/month**, shared broker, MQTT 3.1 / 3.1.1 / 5, MQTT over TLS/SSL, basic credentials and basic authorization. No uptime SLA.  
  Source: <https://www.hivemq.com/pricing/fully-managed/>  
  Source: <https://docs.hivemq.com/hivemq-cloud/quick-start-guide.html>
- Starter: from **$0.34/hour** + **$0.80 per million** normalized messages; 10k connections; client certificates, JWT, advanced RBAC; 99.95% SLA.  
  Source: <https://www.hivemq.com/pricing/fully-managed/>  
  Source: <https://docs.hivemq.com/hivemq-platform/connect/access-management-options-per-cloud-plan.html>
- Message billing normalizes at **5 KB** (topic + headers + payload). A 65 KB job is many normalized messages; still fine at low volume.  
  Source: <https://hivemq.atlassian.net/wiki/spaces/HCSP/pages/2539421729/What+counts+as+a+single+message>
- Cloud documentation does not publish a Serverless hard max payload as clearly as EMQX/AWS; self-managed HiveMQ defaults allow a very large max packet size. Treat max-size acceptance of 65 KB as a **spike check**, not a documented free-tier guarantee.

**Auth**

- Serverless: username/password only among the compared methods.  
- Starter+: username/password **or** client certs **or** JWT (one method active at a time on Starter).  
  Source: <https://docs.hivemq.com/hivemq-platform/connect/access-management-options-per-cloud-plan.html>

**MicroPython**

- Same `umqtt.simple` TLS + user/pass pattern as any TLS broker. No first-party ESP32 MicroPython guide as strong as EMQX’s.

**Verdict:** Good free sandbox and solid MQTT product. Starter production cost is high for one always-on device (~$245/month base before messages). Use as a free TLS sandbox alternative; not the cheapest production path.

### 3. EMQX Cloud

**Fit**

- Serverless max **message size 1 MB**, max concurrent connections 1000, max publish TPS per client **10/s**, TLS 1.2/1.3, no anonymous access.  
  Source: <https://docs.emqx.com/en/cloud/latest/create/restriction.html>
- Free monthly quota: **1 million session minutes**, **1 GB traffic**, **1 million rule actions**; overage **$2 / M session-minutes**, **$0.15 / GB**. Spend limit can freeze at free.  
  Source: <https://docs.emqx.com/en/cloud/latest/price/pricing.html>
- One always-connected device ≈ 43,200 session-minutes / 30-day month — well inside free session quota. Traffic is the tighter free limit (1 GB); a few dozen max-size jobs/day stay modest.
- Dedicated Flex starts near **$0.32/hour** for small tiers + egress — only needed if Serverless limits or tenancy become insufficient.  
  Source: <https://docs.emqx.com/en/cloud/latest/price/pricing.html>

**Auth / TLS**

- Serverless: **TLS only** (port **8883**), download deployment CA, configure username/password under Access Control.  
  Source: <https://docs.emqx.com/en/cloud/latest/connect_to_deployments/esp32_with_micropython.html>  
  Source: <https://docs.emqx.com/en/cloud/latest/deployments/port_guide_serverless.html>
- Official ESP32 + MicroPython + `umqtt` guide shows:

  ```python
  MQTTClient(..., ssl=True, ssl_params={
      "cert_reqs": ssl.CERT_REQUIRED,
      "cadata": cadata,
      "server_hostname": SERVER,  # required for Serverless SNI multi-tenancy
  })
  ```

  Source: <https://docs.emqx.com/en/cloud/latest/connect_to_deployments/esp32_with_micropython.html>

**MicroPython work vs current firmware**

- Keep username/password and QoS 1 subscribe/publish.
- Add: TLS wrap, CA on device, SNI/`server_hostname`, port 8883, and a valid RTC/NTP for `CERT_REQUIRED`.
- No client certificate required for Serverless.
- Not zero firmware change, but the **smallest** change among production-minded managed options.

**Verdict:** Best match for Paperbridge’s current one-device, user/pass, QoS 1, 65 KB, outbound-client model.

### 4. Azure Event Grid MQTT (clearly better?)

Evaluated as the main “other managed MQTT” cloud offering with first-party docs.

- Max MQTT message size **512 KB**; QoS 0/1; MQTT 3.1.1 and 5; TLS 1.2/1.3 on **8883**.  
  Source: <https://learn.microsoft.com/en-us/azure/event-grid/quotas-limits>  
  Source: <https://learn.microsoft.com/en-us/azure/event-grid/mqtt-support>
- Auth modes: **certificates, Microsoft Entra JWT, OAuth 2.0 JWT, custom webhook** — not simple broker username/password.  
  Source: <https://learn.microsoft.com/en-us/azure/event-grid/mqtt-client-authentication>
- Capacity is **throughput-unit** based; MQTT ops free allowance exists but the identity model is heavier than Mosquitto/EMQX Serverless for one ESP32.  
  Source: <https://azure.microsoft.com/en-us/pricing/details/event-grid/>

**Verdict:** Capable broker, wrong auth model for minimal `umqtt` migration. Not better for Paperbridge’s current constraints.

---

## Smallest credible choice

**EMQX Cloud Serverless**

Reasons:

1. **1 MB** message limit covers prepared **65,536-byte** jobs with margin.
2. **Username/password + TLS** matches the existing adapter shape; only TLS/SNI/CA/clock must be added.
3. Official **ESP32 MicroPython umqtt** connection guide reduces integration guesswork.
4. Free quota is enough for one always-on device and low job volume; spend limit can hard-cap cost.
5. No durable cloud queue is required; non-retained QoS 1 stays an application choice.
6. Ops burden is console credentials + CA, not cert fleets or custom authorizers.

**Runner-up:** HiveMQ Cloud Serverless for free TLS experiments if EMQX region/product fit fails.  
**Defer:** AWS IoT Core and Azure Event Grid until multi-cloud identity or AWS/Azure platform lock-in is an explicit product requirement.

---

## Firmware / host gap to EMQX Serverless

| Gap | Severity | Notes |
| --- | --- | --- |
| `MQTTClient(..., ssl=…)` not wired in `mqtt_adapter.py` | Required | umqtt supports it; Paperbridge factory does not pass it yet |
| CA cert on device + `CERT_REQUIRED` | Required | EMQX Serverless documents CA download |
| `server_hostname` / SNI | Required | Documented as mandatory for EMQX Serverless multi-tenancy |
| Device time (NTP/RTC) | Required for verify | MicroPython docs: `CERT_REQUIRED` needs correct time |
| RAM for TLS + 65 KB job | **Spike** | Repo already flags MQTT/TLS memory risk on ESP32 |
| Host API publisher TLS to same broker | Small | `apps/api` already speaks MQTT; point it at cloud endpoint with TLS |
| Production cert rotation / unique per-device creds | Later | Serverless auth entries exist; not needed for first spike |

---

## Physical spike blockers (must prove on hardware)

Do not treat documentation as pass. Required spike on the purchased ESP32-S3-ETH + MicroPython 1.28:

1. **TLS connect** to EMQX Serverless (or HiveMQ Serverless) with `umqtt.simple`, CA verify, and SNI — without OOM or watchdog reset.
2. **QoS 1 subscribe** on `print-jobs` / probe topics and **non-retained QoS 1 publish** of results.
3. **Large payload**: publish/receive a prepared job near **65,536 bytes** over TLS; measure free RAM before/after.
4. **Clock**: confirm NTP (or other time set) so `CERT_REQUIRED` does not fail intermittently.
5. **Reconnect**: clean-session reconnect after Wi-Fi drop; confirm no retained surprise and device ledger still suppresses duplicate `job_id` on QoS redelivery.
6. **Coexistence**: W5500 direct printer path remains usable while Wi-Fi MQTT TLS session is up (Paperbridge dual-plane constraint).

If step 1 or 3 fails on device RAM, options are: smaller jobs only, alternate lightweight TLS client, or keep local Mosquitto until ESP-IDF/other runtime.

---

## Recommendation

| Stage | Choice |
| --- | --- |
| Next managed experiment | **EMQX Cloud Serverless** |
| Free alternate sandbox | HiveMQ Cloud Serverless |
| Not yet | AWS IoT Core (mTLS/custom auth + ops weight) |
| Not yet | Azure Event Grid MQTT (no simple password auth) |
| Production later | Re-evaluate EMQX Dedicated vs AWS only after multi-device security, SLA, and region needs are real |

**Do not replace local Mosquitto in the private v1 path until the physical TLS spike passes.** Managed MQTT is a control-plane hosting choice, not a change to semantic job contracts.

---

## Primary sources

- AWS IoT Core quotas: <https://docs.aws.amazon.com/general/latest/gr/iot-core.html>
- AWS IoT protocols / ports / auth: <https://docs.aws.amazon.com/iot/latest/developerguide/protocols.html>
- AWS IoT pricing: <https://aws.amazon.com/iot-core/pricing/>
- AWS MicroPython blog: <https://aws.amazon.com/blogs/iot/using-micropython-to-get-started-with-aws-iot-core/>
- HiveMQ Cloud pricing: <https://www.hivemq.com/pricing/fully-managed/>
- HiveMQ Cloud quick start: <https://docs.hivemq.com/hivemq-cloud/quick-start-guide.html>
- HiveMQ auth by plan: <https://docs.hivemq.com/hivemq-platform/connect/access-management-options-per-cloud-plan.html>
- HiveMQ message normalization: <https://hivemq.atlassian.net/wiki/spaces/HCSP/pages/2539421729/What+counts+as+a+single+message>
- EMQX Cloud pricing: <https://docs.emqx.com/en/cloud/latest/price/pricing.html>
- EMQX Cloud quotas: <https://docs.emqx.com/en/cloud/latest/create/restriction.html>
- EMQX ESP32 MicroPython guide: <https://docs.emqx.com/en/cloud/latest/connect_to_deployments/esp32_with_micropython.html>
- EMQX Serverless ports: <https://docs.emqx.com/en/cloud/latest/deployments/port_guide_serverless.html>
- Azure Event Grid MQTT quotas: <https://learn.microsoft.com/en-us/azure/event-grid/quotas-limits>
- Azure Event Grid MQTT features: <https://learn.microsoft.com/en-us/azure/event-grid/mqtt-support>
- Azure Event Grid MQTT auth: <https://learn.microsoft.com/en-us/azure/event-grid/mqtt-client-authentication>
- Azure Event Grid pricing: <https://azure.microsoft.com/en-us/pricing/details/event-grid/>
- umqtt.simple: <https://github.com/micropython/micropython-lib/tree/master/micropython/umqtt.simple>
- MicroPython 1.28 ssl: <https://docs.micropython.org/en/v1.28.0/library/ssl.html>
