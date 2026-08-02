import {
	Client,
	StreamableHTTPClientTransport,
} from "@modelcontextprotocol/client";

const endpoint = process.argv[2];
const content = JSON.parse(process.argv[3] ?? "null");
if (!endpoint) throw new Error("MCP endpoint URL is required");

const client = new Client(
	{ name: "paperbridge-integration", version: "1.0.0" },
	{ versionNegotiation: { mode: { pin: "2026-07-28" } } },
);
try {
	await client.connect(new StreamableHTTPClientTransport(new URL(endpoint)));
	const tools = (await client.listTools()).tools.map((tool) => tool.name);
	const result = await client.callTool({
		name: "paperbridge_print",
		arguments: { content },
	});
	process.stdout.write(`${JSON.stringify({ tools, result })}\n`);
} finally {
	await client.close();
}
