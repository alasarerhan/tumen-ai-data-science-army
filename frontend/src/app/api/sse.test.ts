import { describe, expect, it } from "vitest";
import { extractSsePayloads, getSseDataPayload, readSseStream } from "./sse";

describe("sse utils", () => {
  it("extracts payloads and preserves remainder", () => {
    const input = "data: one\n\ndata: two\n\npartial";
    const { payloads, remainder } = extractSsePayloads(input);
    expect(payloads).toEqual(["one", "two"]);
    expect(remainder).toBe("partial");
  });

  it("joins multiline data fields", () => {
    const block = "event: message\ndata: line 1\ndata: line 2";
    expect(getSseDataPayload(block)).toBe("line 1\nline 2");
  });

  it("reads chunked stream boundaries", async () => {
    const encoder = new TextEncoder();
    const chunks = ["data: {\"v\":1}\n\n", "data: {\"v\":2", "}\n\n"];
    const events: Array<{ v: number }> = [];

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    });

    await readSseStream({
      stream,
      parse: (raw) => JSON.parse(raw) as { v: number },
      onEvent: (event) => events.push(event),
    });

    expect(events).toEqual([{ v: 1 }, { v: 2 }]);
  });
});
