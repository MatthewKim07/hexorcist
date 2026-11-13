import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// Faces use font-display: optional, so one that is not ready at first paint is skipped for this visit, never swapped in.
// The root is empty until React mounts, so waiting a moment here costs nothing visible.
const FACES = ['400 1em "Geist Sans"', '500 1em "Geist Sans"', '600 1em "Geist Sans"', '400 1em "Geist Mono"', '500 1em "Geist Mono"'];
const fonts = document.fonts ? Promise.all(FACES.map((f) => document.fonts.load(f))) : Promise.resolve();
const cap = new Promise((resolve) => setTimeout(resolve, 1200));

Promise.race([fonts, cap])
  .catch(() => undefined)
  .then(() => {
    ReactDOM.createRoot(document.getElementById("root")!).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    );
  });
