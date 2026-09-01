import { type JSX, useEffect, useState } from "react";

import "./App.css";
import { apiRequest } from "./api";

type ConnectionState = "checking" | "connected" | "error";
type HealthResponse = {
  status: string;
};

function showConnectionStatus(
  connectionState: ConnectionState,
  errorMsg: string,
): JSX.Element {
  switch (connectionState) {
    case "checking":
      return <p role="status">Checking connection...</p>;
    case "connected":
      return (
        <p className="status-success" role="status">
          Backend reachable.
        </p>
      );
    case "error":
      return (
        <p className="status-error" role="alert">
          Cannot connect: {errorMsg}
        </p>
      );
  }
}

function App() {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("checking");

  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    async function checkConnection() {
      try {
        const response = await apiRequest<HealthResponse>("/health");
        if (response.status === "ok") {
          setConnectionState("connected");
        } else {
          setErrorMsg("The API reported that it is unavailable.");
          setConnectionState("error");
        }
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "An unknown error occurred";
        setErrorMsg(message);
        setConnectionState("error");
      }
    }
    void checkConnection();
  }, []);

  return (
    <main className="app-shell">
      <header className="page-header">
        <p className="eyebrow">Personal finance</p>
        <h1>Finance tracker</h1>
        <p>Record income and spending in one place.</p>
      </header>

      <section className="panel" aria-labelledby="connection-heading">
        <h2 id="connection-heading">Backend connection status</h2>
        {showConnectionStatus(connectionState, errorMsg)}
      </section>
    </main>
  );
}

export default App;
