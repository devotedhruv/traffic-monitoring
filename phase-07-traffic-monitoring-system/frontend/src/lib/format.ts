export const formatSpeed = (speed: number) =>
  new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 }).format(speed);

export const formatDateTime = (date: string | Date) =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium"
  }).format(new Date(date));

export const formatTime = (date: string | Date) =>
  new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(new Date(date));

export const titleCase = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();

export const cx = (...classes: Array<string | false | null | undefined>) =>
  classes.filter(Boolean).join(" ");
