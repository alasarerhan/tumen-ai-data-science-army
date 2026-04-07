export interface SseReadOptions<TEvent> {
  stream: ReadableStream<Uint8Array>;
  parse: (raw: string) => TEvent;
  onEvent: (event: TEvent) => void;
}

export interface SsePayloadExtraction {
  payloads: string[];
  remainder: string;
}

/**
 * Splits an SSE text buffer into complete event blocks and returns "data:" payloads.
 */
export function extractSsePayloads(buffer: string): SsePayloadExtraction {
  const blocks = buffer.split(/\r?\n\r?\n/);
  const remainder = blocks.pop() ?? "";
  const payloads: string[] = [];

  for (const block of blocks) {
    const payload = getSseDataPayload(block);
    if (payload !== null) {
      payloads.push(payload);
    }
  }

  return { payloads, remainder };
}

/**
 * Returns joined "data:" lines from a single SSE event block.
 */
export function getSseDataPayload(block: string): string | null {
  const dataLines = block
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.replace(/^data:\s*/, ""));

  if (dataLines.length === 0) return null;
  return dataLines.join("\n");
}

/**
 * Reads an SSE byte stream and emits parsed events.
 */
export async function readSseStream<TEvent>({
  stream,
  parse,
  onEvent,
}: SseReadOptions<TEvent>): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const { payloads, remainder } = extractSsePayloads(buffer);
    buffer = remainder;

    for (const payload of payloads) {
      onEvent(parse(payload));
    }
  }

  const finalText = decoder.decode();
  if (finalText) {
    buffer += finalText;
  }
  const trailing = getSseDataPayload(buffer);
  if (trailing !== null) {
    onEvent(parse(trailing));
  }
}
