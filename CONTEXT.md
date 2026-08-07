# Paperbridge

Paperbridge is a protocol and device platform that lets people, applications,
and AI agents send secure, scheduled physical output to connected printers.

## Language

**Physical Inbox**:
An owner’s connected printer experience, where physical output arrives without
the owner needing to open an application.
_Avoid_: Printer, feed, notification queue

**Owner**:
The person who pairs and manages a physical inbox and controls who may send to
it.
_Avoid_: Administrator, steward

**Sender**:
An owner, invited person, application, or AI agent permitted to submit physical
output to a physical inbox.
_Avoid_: Host, client, contributor

**Recipient**:
The person for whom a particular piece of physical output is intended. This is
usually the physical inbox owner.
_Avoid_: Sender, printer

**Invite**:
A directional grant allowing a sender to submit output to one physical inbox.
It does not grant reciprocal access.
_Avoid_: Pairing, friendship

**Host**:
The computer that submits commands and printing work to a Paperbridge device.
_Avoid_: Client, controller

**Device**:
The Paperbridge appliance that receives host commands and delivers output to a
printer.
_Avoid_: Bridge, controller, printer

**Printer**:
The thermal printer that receives rendered output from a device.
_Avoid_: Device

**Printer Endpoint**:
The configured network destination of a printer.
_Avoid_: Device endpoint, serial port

**Serial RPC Request**:
A host command correlated by a request ID. It is transport work, not a print job.
_Avoid_: Job

**Semantic Print Job**:
A versioned request describing printable meaning as bounded receipt blocks rather
than printer-specific bytes.
_Avoid_: Payload, raw job, RPC request

**Durable Semantic Job**:
A semantic print job with a Host-held lifecycle record and a Device execution
receipt that survive restart. It is not a broker queue or proof that paper
emerged.
_Avoid_: Retained message, exactly-once print

**Delivery Attempt**:
The bounded interval after a Host commits a job for dispatch and before the
Device records a terminal result. It can become an Unknown Delivery Result.
_Avoid_: Retry, printing attempt

**Manual Reconciliation**:
An Owner's recorded resolution of an Unknown Delivery Result. It may close the
job or create a separately authorized replacement; it does not re-dispatch the
old job.
_Avoid_: Automatic retry, duplicate suppression

**Job Result**:
A versioned terminal device report correlated to a semantic print job by
`job_id`. It may report delivered to printer, rejected, or failed; it never
claims paper emerged.
_Avoid_: Ack, event, printed receipt

**Unknown Delivery Result**:
The application stopped waiting before a correlated job result arrived. It is
not job expiry, printer failure, or permission to submit the job again.
_Avoid_: Failed, expired, retryable

**Block**:
A bounded content unit within a semantic print job, such as text, feed, rule, QR,
or cut.
_Avoid_: Command, payload

**Bring-up Test**:
An explicit diagnostic action used to prove one part of the hardware path. It is
not a semantic print job or a production workflow.
_Avoid_: Print job

**Render**:
Convert semantic printing work into printer-specific output.
_Avoid_: Print, deliver

**Reachable**:
A printer endpoint accepted a connection from the device.
_Avoid_: Delivered, printed

**Deliver**:
Send all rendered output successfully to the printer-facing connection.
_Avoid_: Print

**Delivered to Printer**:
The device accepted that all rendered output was written to the printer-facing
connection. It does not claim that paper emerged.
_Avoid_: Printed, completed

**Printed**:
Physical output confirmed by reliable printer status. Paperbridge does not claim
this state until that confirmation exists.
_Avoid_: Delivered to printer
