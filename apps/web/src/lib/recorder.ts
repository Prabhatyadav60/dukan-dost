export const MAX_RECORD_MS = 30_000;
/** Shorter presses are taps, not speech. */
export const MIN_RECORD_MS = 500;

export function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined;
  for (const t of ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/ogg', 'audio/aac']) {
    if (MediaRecorder.isTypeSupported(t)) return t;
  }
  return undefined;
}

export function extensionFor(mime: string): string {
  if (mime.includes('mp4')) return 'm4a';
  if (mime.includes('aac')) return 'aac';
  if (mime.includes('ogg')) return 'ogg';
  return 'webm';
}
