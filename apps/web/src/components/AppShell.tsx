import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { AssistantProvider, useAssistant } from '../assistant';
import { s } from '../strings';
import { BookIcon, CameraIcon, ChartIcon, HomeIcon, KeyboardIcon } from './Icons';
import { MicButton } from './MicButton';
import { useToast } from './Toast';

/** Bottom tab bar with the always-available mic. The voice/photo flows live in AssistantProvider. */
export function AppShell() {
  return (
    <AssistantProvider>
      <Outlet />
      <TabBar />
    </AssistantProvider>
  );
}

function TabBar() {
  const a = useAssistant();
  const toast = useToast();
  // the chat screen has its own composer mic; one mic per screen
  const inChat = useLocation().pathname === '/assistant';
  return (
    <nav className="tabbar" aria-label="Main">
      <NavLink to="/" end><HomeIcon />{s.tabs.home}</NavLink>
      <NavLink to="/udhaar"><BookIcon />{s.tabs.udhaar}</NavLink>
      <div className="micwrap">
        {!inChat && <MicButton
          onAudio={(b, name) => void a.submitAudio(b, name)}
          onError={(m) => {
            toast(m);
            a.openTyping();
          }}
        />}
        {!inChat && <button className="kbd" aria-label="Likh kar bhejein" onClick={a.openTyping}><KeyboardIcon /></button>}
      </div>
      <NavLink to="/forecast"><ChartIcon />{s.tabs.forecast}</NavLink>
      <NavLink to="/scan"><CameraIcon />{s.tabs.scan}</NavLink>
    </nav>
  );
}
