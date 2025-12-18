export const formatDate = (val?: string | null, pattern = "yyyy-MM-dd HH:mm:ss") => {
  if (!val) return "-";
  let raw = val;
  if (typeof raw === "string") {
    const s = raw.trim();
    const hasTz = /([zZ]|[+-]\d{2}:?\d{2})$/.test(s);
    const looksLikeDateTime = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}/.test(s);
    if (looksLikeDateTime && !hasTz) {
      raw = s.replace(" ", "T");
    } else {
      raw = s;
    }
  }

  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return String(val);
  const pad = (n: number) => String(n).padStart(2, "0");
  const tokens: Record<string, string> = {
    yyyy: String(d.getFullYear()),
    MM: pad(d.getMonth() + 1),
    dd: pad(d.getDate()),
    HH: pad(d.getHours()),
    mm: pad(d.getMinutes()),
    ss: pad(d.getSeconds()),
  };
  return pattern.replace(/yyyy|MM|dd|HH|mm|ss/g, (k) => tokens[k]);
};
