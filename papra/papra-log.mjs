import { createInterface } from 'node:readline';

const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of lines) {
  if (line.startsWith('{')) {
    let record;
    try {
      record = JSON.parse(line);
    } catch {
      // Non-JSON output still gets a timestamp below.
    }
    if (typeof record?.timestamp === 'string') {
      console.log(line);
      continue;
    }
    if (typeof record?.timestampMs === 'number') {
      const timestamp = new Date(record.timestampMs);
      if (Number.isFinite(timestamp.getTime()) && !Object.hasOwn(record, 'timestamp')) {
        // Keep the original JSON fields byte-for-byte, including numeric values.
        console.log(`{"timestamp":"${timestamp.toISOString()}",${line.slice(1)}`);
        continue;
      }
    }
  }
  console.log(`[${new Date().toISOString()}] ${line}`);
}
