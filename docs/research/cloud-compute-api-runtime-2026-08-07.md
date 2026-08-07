# Cloud compute options for the portable Paperbridge API/MCP service

Research performed 2026-08-07 against official product documentation and
pricing pages. These are documentation facts and indicative low-traffic cost
estimates, not a deployment decision, production SLA, or measured bill.

## Workload under study

`apps/api` is a portable Node.js TypeScript process that:

- serves private REST and Streamable HTTP MCP on one built-in Node HTTP server;
- holds a long-lived outbound MQTT client for publish and result subscription;
- waits up to about 15 seconds for correlated MQTT results;
- needs environment secrets (MQTT password and related config);
- needs restart/redeploy, logs, and health checks.

Source shape: `apps/api/README.md`, `apps/api/src/server.ts`.

Hard constraint for this report: a **persistent outbound MQTT subscription**
needs a process that stays up. Platforms that scale to zero stop CPU and drop
that socket. Scale-to-zero is therefore a poor fit unless the product later
drops the always-subscribed host MQTT client and accepts reconnect-on-request
semantics.

Fixed egress/IP is not required for the current private single-device path and
is noted only where a platform makes it cheap or optional.

## Decision summary

**Recommended fewest-operations path: Fly.io, one always-on small Machine.**

- Keep one Machine running (`auto_stop_machines = "off"` or
  `min_machines_running = 1`).
- Deploy the existing Node service as a Dockerfile or `fly launch` Node app.
- Put MQTT and API secrets in `fly secrets`.
- Add a simple HTTP health check and bind `0.0.0.0` on the platform port.
- Indicative idle cost: about **US$3–6/month** for `shared-cpu-1x` with
  512 MB–1 GB RAM in cheap regions, plus low egress and optional dedicated
  IPv4 (US$2/month).

**Close second: Railway Hobby always-on service** when Git-push UX and a
single dashboard matter more than the absolute lowest always-on floor.

**Do not use free/scale-to-zero tiers for this MQTT-bearing process.**

## Comparison matrix

| Platform | Always-on MQTT fit | Inbound MCP / long HTTP | Scale-to-zero impact | Secrets | Health / restart | Indicative low-traffic always-on cost | Ops weight |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Fly.io** | Good: leave Machine started | Good: ordinary HTTP service | Autostop drops MQTT; keep min 1 or disable autostop | `fly secrets` → env | Checks + Machine restarts; `fly deploy` | ~$3–6/mo small shared Machine | Low |
| **Railway** | Good while service is awake | Good: HTTP service | Serverless sleeps after ~10 min with **no outbound**; MQTT traffic usually prevents sleep, but sleep is still wrong for this design | Service variables / secrets | Deploy healthcheck only; not continuous | Hobby $5/mo includes usage; tiny always-on often stays near plan floor | Low |
| **Render** | Good on paid web service | Good: web service HTTP/2 + TLS | Free spins down after 15 min idle inbound; kills MQTT | Dashboard / Blueprint env | Continuous checks; auto-restart; zero-downtime deploy | Starter web service **$7/mo** | Low |
| **Google Cloud Run** | Only with min instances + instance-based billing | Stream/long request max **60 min**; default timeout 5 min | Default scale-to-zero drops MQTT | Secret Manager or env | Startup/liveness probes; managed revisions | Always-on CPU is relatively expensive (~tens of USD/mo for 1 vCPU) | Medium |
| **AWS App Runner** | Closed to new customers | N/A for new work | N/A | N/A | N/A | N/A | Skip |
| **AWS Lightsail containers** | Good: always billed while running | Good: HTTPS endpoint | No scale-to-zero; disable still bills | Service env | Managed container service; simpler than ECS | Micro from **~$7/mo** + 500 GB transfer quota | Low–medium |
| **AWS ECS Fargate** | Good | Good behind ALB/NLB | No free idle; task runs or not | Secrets Manager / SSM | ECS health checks, circuit breakers | Small task often ~$8–20/mo compute; ALB adds more if public HTTP | High |
| **Cloudflare Containers** | Possible but different model (Worker + Durable Object + container) | Request-routed through Worker; container can sleep | Default sleep-after; always-on MQTT means always billed | Workers/secrets bindings; repo already treats CF as future secret boundary | Rolling container deploys; DO lifecycle | Workers Paid $5 + container active time; always-on not the sweet spot | Medium–high for this app shape |

## Platform notes

### Fly.io (recommended)

- Machines bill while started; stopped Machines bill only rootfs storage
  (~US$0.15 per GB-month of image/rootfs), not CPU/RAM.
  Source: <https://fly.io/docs/about/pricing/>
- Small always-on example from published tables: `shared-cpu-1x` 512 MB about
  **US$3.32/month**, 1 GB about **US$5.92/month** (region-dependent tables on
  the same page).
- Autostop/autostart can stop idle Machines; for MQTT set
  `auto_stop_machines = "off"` or keep `min_machines_running = 1`.
  Source: <https://fly.io/docs/launch/autostop-autostart/>
- Secrets are encrypted in a vault and injected as env vars at Machine boot.
  Source: <https://fly.io/docs/apps/secrets/>
- Shared IPv4 is free; dedicated IPv4 is US$2/month; optional static egress IP
  about US$3.60/month if ever needed.
  Source: <https://fly.io/docs/about/pricing/>
- Public egress about US$0.02/GB North America/Europe on granular pricing.
  Source: same pricing page.

**Why fewest ops here:** one Dockerfile or Node build, one `fly.toml`, one
always-on Machine, secrets CLI, logs, and deploys without a second worker
process. Matches “single long-running Node process with HTTP + MQTT.”

### Railway

- Plans: Free, Hobby **US$5/month**, Pro **US$20/month**; subscription usage
  credit covers resource usage up to that amount.
  Source: <https://docs.railway.com/pricing/plans>
- Resource rates: RAM US$10/GB-month, CPU US$20/vCPU-month, egress US$0.05/GB.
  Source: same page.
- Serverless/app-sleep detects **outbound** silence for 10+ minutes; active
  MQTT would normally prevent sleep, but intentional always-on is clearer with
  Serverless off.
  Source: <https://docs.railway.com/reference/app-sleeping>
- Healthchecks gate zero-downtime deploy readiness only; they are **not**
  continuous liveness monitors.
  Source: <https://docs.railway.com/reference/healthchecks>
- Variables/secrets are first-class service config.
  Source: <https://docs.railway.com/reference/variables>

**Fit:** excellent developer UX; cost floor usually the Hobby plan for a tiny
always-on API. Slightly less explicit “VM stays up” model than Fly Machines.

### Render

- Paid web services are always-on processes with managed TLS and private
  networking.
  Source: <https://render.com/docs/web-services>
- Compute: Free 512 MB; **Starter US$7/month** 512 MB / 0.5 CPU; Standard
  US$25/month 2 GB / 1 CPU.
  Source: <https://render.com/pricing>
- Free web services spin down after **15 minutes** without inbound traffic and
  take about a minute to wake; local disk is lost on spin-down. Unsuitable for
  persistent MQTT.
  Source: <https://render.com/docs/free>
- Health checks run continuously; failed instances are drained and restarted.
  Source: <https://render.com/docs/health-checks>
- Env groups / secret files supported for configuration.
  Source: <https://render.com/docs/configure-environment-variables>

**Fit:** simple Git deploy and strong health/restart behavior. Minimum honest
cost for this workload is Starter at US$7/month, not Free.

### Google Cloud Run

- Default scales to zero when idle.
  Source: <https://cloud.google.com/run/docs/about-instance-autoscaling>
- Persistent background work needs **instance-based billing** (CPU always
  allocated) and usually **minimum instances ≥ 1**.
  Sources:
  <https://cloud.google.com/run/docs/configuring/billing-settings>,
  <https://docs.cloud.google.com/run/docs/configuring/min-instances>
- Request timeout default 5 minutes, max 60 minutes; long MCP streams must stay
  under that ceiling and clients must reconnect.
  Source: <https://cloud.google.com/run/docs/configuring/request-timeout>
- WebSockets/long connections are supported but still bound by request timeout.
  Source: <https://docs.cloud.google.com/run/docs/triggering/websockets>
- Instance-based pricing example (us-central1 list): about US$0.000018 per
  vCPU-second and US$0.000002 per GiB-second, with monthly free tiers.
  Source: <https://cloud.google.com/run/pricing>
- Rough always-on math for 1 vCPU + 0.5 GiB, 730 h: on the order of
  **US$45–50/month** before free tier/CUD, much higher than Fly/Railway/Render
  for this tiny API.

**Fit:** fine for request-only APIs; awkward and relatively costly for one
always-subscribed MQTT client. More GCP surface (project, IAM, Artifact
Registry, Secret Manager) than needed for a private MVP.

### AWS App Runner

- Closed to new customers; existing customers only.
  Source: <https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html>
- AWS points new work at Amazon ECS Express Mode / ECS on Fargate.

**Fit:** skip for new Paperbridge hosting.

### AWS Lightsail containers

- Managed container service with HTTPS endpoint; Linux Docker only.
  Source: <https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-containers.html>
- Billed while running or disabled; cheapest power about **US$7/month**
  (US$0.0094/hour) with 500 GB transfer quota per service.
  Source: same FAQ / <https://aws.amazon.com/lightsail/pricing/>
- Public registries or CLI-pushed images; less flexible private-registry story
  than ECR+ECS.

**Fit:** acceptable always-on simple host; usually no cost advantage over
Render Starter and less app-centric DX than Fly/Railway.

### AWS ECS on Fargate

- Pay for vCPU/memory from image pull until task stop; 1-minute minimum.
  Source: <https://aws.amazon.com/fargate/pricing/>
- No extra ECS control-plane fee; you still own networking, load balancing,
  secrets, logs, and deploy pipeline.
  Source: <https://aws.amazon.com/ecs/pricing/>
- Right for AWS-standard production estates; heavy for a single private API.

**Fit:** not the fewest-operations path.

### Cloudflare Containers (clear alternative, not best match)

- Containers run under Workers/Durable Objects; default story is on-demand
  start and sleep (`sleepAfter` in examples).
  Source: <https://developers.cloudflare.com/containers/>
- Billed while active; Workers Paid US$5/month includes limited container
  usage; egress separate.
  Source: <https://developers.cloudflare.com/containers/pricing/>
- Repo research already treats Cloudflare as a **future runtime secret
  boundary**, not the current Node API host
  (`docs/research/fnox-secrets-workflow.md`).

**Fit:** interesting if Paperbridge later redesigns around Workers; extra
moving parts for today’s “one Node process, HTTP + MQTT.”

## Scale-to-zero vs MQTT (read this first)

| Approach | Idle compute cost | MQTT subscription | MCP cold start | Verdict for current `apps/api` |
| --- | --- | --- | --- | --- |
| Scale to zero | Lowest | Dropped; must reconnect and resubscribe | Extra latency / possible 502 | Reject for current design |
| Min-1 / always-on | Small flat cost | Stable | None | **Required** |
| Split API (scale-to-zero) + MQTT worker (always-on) | Worker still always-on | Stable in worker | API may cold-start | More services, little savings |

For one private device and low traffic, a **single always-on tiny process** is
simpler and not materially more expensive than a split design.

## Secrets, logs, health, redeploy (common requirements)

| Need | Practical always-on choice |
| --- | --- |
| Secrets as env | Fly secrets, Railway variables, Render env, Cloud Run Secret Manager, AWS Secrets Manager/SSM |
| Logs | Platform log stream (all above); no extra broker required for MVP |
| Health | HTTP `/health` that can optionally require MQTT `waitUntilReady`; use platform checks where continuous (Render/Fly/Cloud Run/ECS). Railway check is deploy-time only |
| Redeploy | Git-integrated (Railway/Render) or `fly deploy` / container push; prefer SIGTERM-friendly shutdown already present in `server.ts` |
| Bind address | Must listen on `0.0.0.0` and `PORT` in cloud; current default `127.0.0.1` is localhost-only and must change for any public/private cloud URL |

## Indicative monthly cost band (low traffic, always-on)

Assumptions: one small Node process, little egress, no DB, no multi-region,
list prices as of research date, USD.

| Option | Ballpark |
| --- | --- |
| Fly `shared-cpu-1x` 512 MB–1 GB | **~$3–6** |
| Railway Hobby tiny service | **~$5** (plan floor if usage ≤ credit) |
| Render Starter web service | **~$7** |
| Lightsail container Micro ×1 | **~$7** |
| Cloud Run min=1, instance-based, ~1 vCPU | **~$40+** before discounts |
| ECS Fargate 0.25 vCPU / 0.5 GB + public LB | **~$10–30+** depending on LB |

Prices move; re-check the cited pricing URLs before purchase.

## Recommendation

1. **Ship on Fly.io with one always-on Machine** for the fewest moving parts and
   lowest honest always-on cost.
2. Keep MQTT and HTTP in the **same process** (already how `apps/api` works).
3. Do **not** enable scale-to-zero / free spin-down while the process owns the
   MQTT subscription.
4. Use platform secrets for `PAPERBRIDGE_MQTT_PASSWORD` and related values; keep
   Fnox/1Password as the local operator path only.
5. Choose Railway or Render only if their Git dashboard UX is worth ~US$2–4 more
   per month.
6. Avoid Cloud Run/ECS/App Runner for this private MVP unless there is already
   a hard requirement to live in GCP/AWS.

Non-goals deferred: multi-region HA, MQTT/TLS termination design, public auth,
fixed egress IP, and any Cloudflare Workers redesign.

## Primary sources

- Fly pricing: <https://fly.io/docs/about/pricing/>
- Fly autostop/autostart: <https://fly.io/docs/launch/autostop-autostart/>
- Fly secrets: <https://fly.io/docs/apps/secrets/>
- Railway plans: <https://docs.railway.com/pricing/plans>
- Railway serverless/sleep: <https://docs.railway.com/reference/app-sleeping>
- Railway healthchecks: <https://docs.railway.com/reference/healthchecks>
- Render pricing: <https://render.com/pricing>
- Render free limits: <https://render.com/docs/free>
- Render web services: <https://render.com/docs/web-services>
- Render health checks: <https://render.com/docs/health-checks>
- Cloud Run billing settings: <https://cloud.google.com/run/docs/configuring/billing-settings>
- Cloud Run min instances: <https://docs.cloud.google.com/run/docs/configuring/min-instances>
- Cloud Run pricing: <https://cloud.google.com/run/pricing>
- Cloud Run request timeout: <https://cloud.google.com/run/docs/configuring/request-timeout>
- Cloud Run WebSockets: <https://docs.cloud.google.com/run/docs/triggering/websockets>
- AWS App Runner closed to new customers: <https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html>
- App Runner pricing (legacy/reference): <https://aws.amazon.com/apprunner/pricing/>
- Lightsail containers FAQ: <https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-containers.html>
- Lightsail pricing: <https://aws.amazon.com/lightsail/pricing/>
- Fargate pricing: <https://aws.amazon.com/fargate/pricing/>
- Cloudflare Containers overview: <https://developers.cloudflare.com/containers/>
- Cloudflare Containers pricing: <https://developers.cloudflare.com/containers/pricing/>
