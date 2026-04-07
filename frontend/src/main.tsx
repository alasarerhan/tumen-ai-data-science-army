import { createRoot } from "react-dom/client";
import App from "./app/App.tsx";
import { initSentry } from "./app/lib/sentry";
import { initWebVitals } from "./app/lib/web-vitals";
import "./styles/index.css";

initSentry();
initWebVitals();

createRoot(document.getElementById("root")!).render(<App />);
