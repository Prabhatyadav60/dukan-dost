import { createContext, useContext, useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { api, getToken } from './api/client';
import type { Merchant } from './api/types';
import { Loading } from './components/States';

interface Session {
  merchant: Merchant | null;
  setMerchant: (m: Merchant | null) => void;
}

const Ctx = createContext<Session>({ merchant: null, setMerchant: () => {} });

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [merchant, setMerchant] = useState<Merchant | null>(null);
  return <Ctx.Provider value={{ merchant, setMerchant }}>{children}</Ctx.Provider>;
}

export const useSession = () => useContext(Ctx);

/** Requires a JWT; loads the merchant; sends to onboarding until consent is given. */
export function RequireAuth({ needConsent = true }: { needConsent?: boolean }) {
  const { merchant, setMerchant } = useSession();
  const loc = useLocation();
  const token = getToken();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (token && !merchant) api.me().then(setMerchant).catch(() => setFailed(true));
  }, [token, merchant, setMerchant]);

  if (!token || failed) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (!merchant) return <div className="screen"><Loading /></div>;
  if (needConsent && !merchant.consent_given) return <Navigate to="/onboarding" replace />;
  return <Outlet />;
}
