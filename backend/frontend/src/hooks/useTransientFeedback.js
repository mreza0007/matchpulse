import { useEffect, useMemo, useState } from "react";
import { createFeedbackController } from "../utils/transientFeedback.js";

export function useTransientFeedback() {
  const [feedback, setFeedback] = useState(null);
  const controller = useMemo(() => createFeedbackController(setFeedback), []);
  useEffect(() => {
    controller.activate();
    return () => controller.dispose();
  }, [controller]);
  return [feedback, controller.show, controller.dismiss];
}
