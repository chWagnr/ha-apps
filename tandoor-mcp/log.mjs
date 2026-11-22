import { format } from 'node:util';

const writeError = console.error.bind(console);

export function timestampUpstreamLogs() {
  console.error = (...args) => writeError('[%s] %s', new Date().toISOString(), format(...args));
}

// ISO 8601 UTC timestamps are unambiguous across host/container time zones.
export function logInfo(message) {
  console.log(`[${new Date().toISOString()}] INFO ${message}`);
}

export function logError(message) {
  writeError(`[${new Date().toISOString()}] ERROR ${message}`);
}
