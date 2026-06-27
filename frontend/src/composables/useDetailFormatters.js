export function formatDetailText(value) {
  const text = String(value || '').trim();
  return text || '-';
}

export function formatDetailDate(value) {
  const text = String(value || '').trim();
  if (!text) return '-';
  const normalized = text.replace('T', ' ').replace('Z', '');
  return normalized.split('.')[0] || '-';
}

export function formatDetailBool(value) {
  return value ? '是' : '否';
}

export function splitDetailSummaryEntries(entries, primaryLabels) {
  const primary = [];
  const secondary = [];
  for (const entry of entries) {
    if (primaryLabels.has(entry.label)) primary.push(entry);
    else secondary.push(entry);
  }
  return { primary, secondary };
}
