/**
 * Parse / format simple key-value text lines.
 *
 * Supported input:
 * - key=value
 * - key:value (optional)
 *
 * Empty lines are ignored. Whitespace around key/value is trimmed.
 */

export function parseKeyValueLines(
  text,
  {
    allowColon = true,
    invalidLineMessage = (line) => `格式错误: ${line}`,
    emptyKeyMessage = (line) => `键不能为空: ${line}`,
  } = {},
) {
  const map = {};
  const lines = String(text || '')
    .split(/\r?\n/)
    .map((line) => String(line).trim())
    .filter(Boolean);

  for (const line of lines) {
    const hasEq = line.includes('=');
    const hasColon = allowColon && line.includes(':');
    const separatorIndex = hasEq ? line.indexOf('=') : (hasColon ? line.indexOf(':') : -1);
    if (separatorIndex <= 0) {
      throw new Error(typeof invalidLineMessage === 'function' ? invalidLineMessage(line) : String(invalidLineMessage));
    }
    const key = line.slice(0, separatorIndex).trim();
    const value = line.slice(separatorIndex + 1).trim();
    if (!key) {
      throw new Error(typeof emptyKeyMessage === 'function' ? emptyKeyMessage(line) : String(emptyKeyMessage));
    }
    map[key] = value;
  }
  return map;
}

export function formatKeyValueLines(map) {
  return Object.entries(map || {})
    .map(([key, value]) => `${key}=${value}`)
    .join('\n');
}

