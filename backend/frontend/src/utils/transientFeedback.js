export const SUCCESS_FEEDBACK_MS = 3000;
export const ERROR_FEEDBACK_MS = 8000;

export function createFeedbackController(onChange, { setTimer = setTimeout, clearTimer = clearTimeout } = {}) {
  let timer = null;
  let version = 0;
  let active = true;
  const cancel = () => {
    version += 1;
    if (timer !== null) clearTimer(timer);
    timer = null;
  };
  const dismiss = () => {
    cancel();
    if (active) onChange(null);
  };
  return {
    show(message, kind = "error") {
      if (!active) return;
      cancel();
      if (!message) { onChange(null); return; }
      const token = version;
      onChange({ message, kind, id: token });
      timer = setTimer(() => {
        if (active && token === version) {
          timer = null;
          onChange(null);
        }
      }, kind === "success" ? SUCCESS_FEEDBACK_MS : ERROR_FEEDBACK_MS);
    },
    dismiss,
    activate() { active = true; },
    dispose() { active = false; cancel(); },
  };
}
