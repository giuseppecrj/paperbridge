# Product

## Definition

Paperbridge is a protocol and device platform that lets people, applications,
and AI agents deliver secure, scheduled physical output to connected printers.

## Promise

**Send something real to someone far away.**

Paperbridge is a physical inbox for people and their agents.

The infrastructure definition explains what Paperbridge enables. The promise
explains why it matters.

## Target experience

A daughter gives her father a Paperbridge printer. He pairs it once using the app
and places it in his kitchen.

She can send him short notes from her phone. Her children occasionally send
drawings converted into printable patterns. His AI agent prints his appointments
and the weather each morning. On Sundays, the family’s shared agent prints a
weekly update containing photographs represented as QR codes, birthdays, and
messages from relatives.

He does not need to open an app to receive any of it.

One morning, the printer produces:

```text
GOOD MORNING, DAD

It will be sunny today.
High: 71°

10:30 — Doctor appointment
3:00 — Call with Giuseppe

Ava says:
“We found a new apartment.
Call us when you wake up.”

[QR: View photos]

Today’s fact:
Honey never spoils.
```

## Access model

A person pairs and owns their physical inbox. The owner can invite family,
friends, applications, and AI agents to send to it. An invite grants access in
one direction only: access to another person’s physical inbox requires a separate
invite from that owner.

This follows the familiar connected-frame model: each owner manages their own
device and its permitted senders.

## Product truths

- A physical inbox receives output without requiring the owner to open an
  application.
- Senders may be owners, invited people, applications, or AI agents.
- Output may be immediate or scheduled.
- The owner controls who may send to each physical inbox.
- Paper is the primary experience; links such as QR codes bridge to content that
  does not belong directly on thermal paper.
- The device must continue to describe transport honestly: delivery to a printer
  connection is not proof that paper emerged.

## Current boundary

The implemented private MVP path includes local USB semantic jobs, a bounded
`POST /api/jobs` application ingress, correlated MQTT v1 job delivery, the
no-output Wi-Fi/MQTT tracer, and the device's direct W5500 printer path. The
networked job path is host-/simulator-tested, not physically printed. MCP,
pairing, public delivery, sender authorization, scheduling, cloud services, and
the final recipient experience remain product work.
