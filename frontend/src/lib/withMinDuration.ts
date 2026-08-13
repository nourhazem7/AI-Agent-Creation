/**
 * Ensures an async action's loading state is visible for at least `minMs`, even if it
 * actually resolves almost instantly (e.g. testing a local SQLite connection). Without
 * this, fast operations read as "sudden"/broken rather than as a real, trustworthy check.
 */
export async function withMinDuration<T>(promise: Promise<T>, minMs = 600): Promise<T> {
  const [result] = await Promise.all([promise, new Promise((resolve) => setTimeout(resolve, minMs))]);
  return result;
}
