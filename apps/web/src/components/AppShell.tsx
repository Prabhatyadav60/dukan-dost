import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import type { VoiceParseResponse } from '../api/types';
import { s } from '../strings';
import { ConfirmSheet } from './ConfirmSheet';
import { BookIcon, CameraIcon, ChartIcon, HomeIcon, KeyboardIcon } from './Icons';
import { MicButton } from './MicButton';
import { useToast } from './Toast';

type Phase =
  | { k: 'idle' }
  | { k: 'typing' }
  | { k: 'thinking' }
  | { k: 'confirm'; parsed: VoiceParseResponse | null; source: 'voice' | 'text' | 'manual' };

/** Bottom tab bar with the always-available mic, and the voice → confirm flow. */
export function AppShell() {
  const [phase, setPhase] = useState<Phase>({ k: 'idle' });
  const [text, setText] = useState('');
  const toast = useToast();
  const nav = useNavigate();

  async function parse(p: Promise<VoiceParseResponse>, source: 'voice' | 'text') {
    setPhase({ k: 'thinking' });
    try {
      setPhase({ k: 'confirm', parsed: await p, source });
    } catch (e) {
      if (e instanceof ApiError && e.code === 'ai_unavailable') {
        setPhase({ k: 'confirm', parsed: null, source: 'manual' });
      } else {
        toast(e instanceof ApiError && e.code !== 'network' ? s.voice.sttFailed : s.common.networkError);
        setPhase(source === 'text' ? { k: 'typing' } : { k: 'idle' });
      }
    }
  }

  return (
    <>
      <Outlet />
      <nav className="tabbar" aria-label="Main">
        <NavLink to="/" end><HomeIcon />{s.tabs.home}</NavLink>
        <NavLink to="/udhaar"><BookIcon />{s.tabs.udhaar}</NavLink>
        <div className="micwrap">
          <MicButton
            onAudio={(b, name) => parse(api.voiceParseAudio(b, name), 'voice')}
            onError={(m) => {
              toast(m);
              setPhase({ k: 'typing' });
            }}
          />
          <button className="kbd" aria-label="Likh kar bhejein" onClick={() => setPhase({ k: 'typing' })}><KeyboardIcon /></button>
        </div>
        <NavLink to="/forecast"><ChartIcon />{s.tabs.forecast}</NavLink>
        <NavLink to="/scan"><CameraIcon />{s.tabs.scan}</NavLink>
      </nav>

      {phase.k === 'typing' && (
        <div className="dim" onClick={() => setPhase({ k: 'idle' })}>
          <form
            className="sheet"
            onClick={(e) => e.stopPropagation()}
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim()) void parse(api.voiceParseText(text.trim()), 'text');
            }}
          >
            <div className="grab" />
            <div className="textrow">
              <input autoFocus maxLength={300} value={text} placeholder={s.voice.typePlaceholder} onChange={(e) => setText(e.target.value)} />
              <button className="btn small" disabled={!text.trim()}>{s.voice.send}</button>
            </div>
          </form>
        </div>
      )}
      {phase.k === 'thinking' && (
        <div className="dim"><div className="sheet" style={{ alignItems: 'center' }} role="status"><div className="grab" /><p className="sub">{s.voice.thinking}</p></div></div>
      )}
      {phase.k === 'confirm' && (
        <ConfirmSheet
          parsed={phase.parsed}
          source={phase.source}
          onClose={() => setPhase({ k: 'idle' })}
          onSaved={(m) => {
            setText('');
            setPhase({ k: 'idle' });
            toast(m);
            nav('/assistant');
          }}
        />
      )}
    </>
  );
}
