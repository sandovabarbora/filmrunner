import React from "react";
import ReactDOM from "react-dom/client";
import { EditorApp } from "./EditorApp";
import "@fontsource-variable/archivo/wdth.css";
import "../styles.css";
import "./editor.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <EditorApp />
  </React.StrictMode>,
);
