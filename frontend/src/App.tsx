import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import SecureGenerator from "./pages/SecureGenerator";
// If you already had a Home component, keep it. Here is a tiny placeholder:
function Home() {
  return (
    <div style={{ padding: 24 }}>
      <h2>SAFE-AI-FRAMEWORK</h2>
      <p>Welcome. Open the Secure Generator from the link below.</p>
      <Link to="/secure-generator">Go to Secure Generator →</Link>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/secure-generator" element={<SecureGenerator />} />
      </Routes>
    </BrowserRouter>
  );
}
