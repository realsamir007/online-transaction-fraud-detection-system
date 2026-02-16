export function formatCurrency(amount: number, currency = "USD"): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) {
    return "Good morning";
  }
  if (hour < 18) {
    return "Good afternoon";
  }
  return "Good evening";
}

export function extractFirstName(email: string): string {
  const namePart = email.split("@")[0] || "User";
  const normalized = namePart.replace(/[._-]+/g, " ").trim();
  const firstToken = normalized.split(" ")[0] || "User";
  return firstToken.charAt(0).toUpperCase() + firstToken.slice(1);
}

export function riskBadgeClass(riskLevel: string | null): string {
  if (riskLevel === "HIGH") {
    return "risk-badge risk-badge-high";
  }
  if (riskLevel === "MEDIUM") {
    return "risk-badge risk-badge-medium";
  }
  if (riskLevel === "LOW") {
    return "risk-badge risk-badge-low";
  }
  return "risk-badge risk-badge-neutral";
}
