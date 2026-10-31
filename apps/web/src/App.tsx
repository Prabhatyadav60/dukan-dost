import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { ToastProvider } from './components/Toast';
import Assistant from './routes/Assistant';
import CustomerDetail from './routes/CustomerDetail';
import Forecast from './routes/Forecast';
import Home from './routes/Home';
import Login from './routes/Login';
import Onboarding from './routes/Onboarding';
import Pay from './routes/Pay';
import Scan from './routes/Scan';
import Udhaar from './routes/Udhaar';
import { RequireAuth, SessionProvider } from './session';

export default function App() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <ToastProvider>
          <div className="device">
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/pay/:linkId" element={<Pay />} />
              <Route element={<RequireAuth needConsent={false} />}>
                <Route path="/onboarding" element={<Onboarding />} />
              </Route>
              <Route element={<RequireAuth />}>
                <Route element={<AppShell />}>
                  <Route index element={<Home />} />
                  <Route path="/assistant" element={<Assistant />} />
                  <Route path="/udhaar" element={<Udhaar />} />
                  <Route path="/udhaar/:id" element={<CustomerDetail />} />
                  <Route path="/forecast" element={<Forecast />} />
                  <Route path="/scan" element={<Scan />} />
                </Route>
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </ToastProvider>
      </SessionProvider>
    </BrowserRouter>
  );
}
