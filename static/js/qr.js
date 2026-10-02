// Разбор строки из QR-кода чека: t=20240315T1430&s=1234.56&fn=...&i=...&fp=...&n=1
(function () {
  const DATE_RE = /^(\d{4})-?(\d{2})-?(\d{2})T(\d{2}):?(\d{2})(?::?\d{2})?$/;

  function parseDate(raw) {
    const match = DATE_RE.exec(raw);
    if (!match) return null;
    const [, year, month, day, hour, minute] = match;
    if (+month < 1 || +month > 12 || +day < 1 || +day > 31) return null;
    if (+hour > 23 || +minute > 59) return null;
    // Секунды отбрасываем: поле формы принимает время с точностью до минуты.
    return `${year}-${month}-${day}T${hour}:${minute}`;
  }

  function parseAmount(raw) {
    const value = raw.replace(",", ".");
    return /^\d+(\.\d+)?$/.test(value) ? value : null;
  }

  const digits = (raw) => (/^\d+$/.test(raw) ? raw : null);

  const FIELDS = [
    { name: "fn", key: "fn", label: "ФН", parse: digits },
    { name: "fd", key: "i", label: "ФД", parse: digits },
    { name: "fp", key: "fp", label: "ФП", parse: digits },
    { name: "purchased_at", key: "t", label: "дата покупки", parse: parseDate },
    { name: "amount", key: "s", label: "сумма", parse: parseAmount },
  ];

  // Принимает и голую строку параметров, и ссылку вида https://…?t=…&s=…
  window.parseReceiptQr = function (text) {
    const query = text.trim().replace(/^[^?=]*\?/, "");
    const params = new URLSearchParams(query);
    const values = {};
    const missing = [];
    FIELDS.forEach(({ name, key, label, parse }) => {
      const raw = (params.get(key) || "").trim();
      const value = raw ? parse(raw) : null;
      if (value === null) missing.push(label);
      else values[name] = value;
    });
    return { values, missing };
  };
})();
