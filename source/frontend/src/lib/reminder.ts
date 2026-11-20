import { useEffect } from "react";

/** In-app daily reminder: shows a Windows notification at the chosen time while the app is open. */
export function useReminder(time: string | null | undefined) {
  useEffect(() => {
    if (!time || !("Notification" in window)) return;
    if (Notification.permission === "default") Notification.requestPermission();
    const check = () => {
      const now = new Date();
      const hhmm = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
      const today = now.toDateString();
      let last: string | null = null;
      try { last = localStorage.getItem("ema-reminded"); } catch { /* storage unavailable */ }
      if (hhmm >= time && last !== today && Notification.permission === "granted") {
        new Notification("English Mastery AI", { body: "Time for today's English session. Your plan is ready on the dashboard." });
        try { localStorage.setItem("ema-reminded", today); } catch { /* ignore */ }
      }
    };
    check();
    const t = setInterval(check, 60_000);
    return () => clearInterval(t);
  }, [time]);
}
