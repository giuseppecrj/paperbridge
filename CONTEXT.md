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

**Job Submission**:
A versioned application request containing receipt content and Host-side
instructions such as Publication Consent. The Host creates the job identity,
selects the authorized Device, records the creation time, and sends only the
resulting semantic print job across the Device protocol.
_Avoid_: Semantic print job, payload, RPC request

**Digital Receipt**:
A digital facsimile generated from the canonical prepared semantic print job. It
represents intended receipt content and is not evidence that paper emerged.
_Avoid_: Scan, physical receipt, proof of printing

**Ephemera Publication**:
A public feed entry created automatically for a consented semantic print job only
after its job result is delivered to printer. It contains a digital receipt and
honest delivery information; it does not claim that paper emerged. Its visibility
may be hidden without changing the semantic print job or job result.
_Avoid_: Print, printed receipt, job

**Publication Consent**:
A sender's per-job grant allowing a digital receipt to become an Ephemera
publication when the physical inbox owner has enabled Ephemera. It may be an
explicit Job Submission choice or resolved from that sender's publication policy.
With neither, the job remains private. It does not grant permission to submit
output or prove that the recipient approved the content itself.
_Avoid_: Invite, print authorization, recipient consent

**Publication Policy**:
A sender's standing preference used when a Job Submission omits its per-job
publication choice. It applies only to that sender, still requires the physical
inbox owner's Ephemera enablement, and may be overridden per job to publish or
remain private.
_Avoid_: Inbox-wide default, Invite, mandatory publication

**Publication Attempt**:
A bounded attempt to create an Ephemera publication after a job is delivered to
printer. Its outcome is separate from the job result. Failure does not change
the delivery outcome or authorize another semantic print job; publication may be
retried independently and idempotently.
_Avoid_: Delivery attempt, print retry, job result

**Publication Outcome**:
The application report for requested Ephemera publication: not requested, not
eligible, published, or failed. It remains separate from the job result, and a
failed publication outcome never makes physical delivery retryable.
_Avoid_: Job result, delivery status, print failure

**Submission Outcome**:
The application report after a job submission is accepted. It carries either an
unchanged job result or an unknown delivery result alongside the separate
publication outcome. Successfully reporting this outcome does not mean delivery
succeeded or paper emerged.
_Avoid_: Job result, combined success, completed

**Publication Withdrawal**:
Permanent removal of an Ephemera publication's receipt content after publication
consent is withdrawn. A minimal job identity tombstone remains so an idempotent
publication retry cannot restore it. It is distinct from a reversible hide.
_Avoid_: Hide, deletion retry, print cancellation

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
