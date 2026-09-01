import "./App.css";

function App() {
  return (
    <main className="app-shell">
      <header className="page-header">
        <p className="eyebrow">Personal finance</p>
        <h1>Finance tracker</h1>
        <p>Record income and spending in one place.</p>
      </header>

      <section className="panel" aria-labelledby="connection-heading">
        <h2 id="connection-heading">Backend connection status</h2>
        <p>Connection check not started.</p>
      </section>
    </main>
  );
}

export default App;
