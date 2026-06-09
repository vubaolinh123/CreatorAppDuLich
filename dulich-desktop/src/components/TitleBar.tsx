/**
 * TitleBar.tsx — Custom Window Title Bar
 * DuLichApp Desktop v0.1.0
 * Height: 42px | data-tauri-drag-region | Custom window controls
 */

import React, { useCallback } from 'react';
import { useActiveCreator } from '../stores/appStore';

/* ---- Tauri API with browser fallback ---- */
async function tauriMinimize(): Promise<void> {
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    await getCurrentWindow().minimize();
  } catch {
    /* browser dev mode — no-op */
  }
}

async function tauriMaximize(): Promise<void> {
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    const win = getCurrentWindow();
    const isMax = await win.isMaximized();
    if (isMax) {
      await win.unmaximize();
    } else {
      await win.maximize();
    }
  } catch {
    /* browser dev mode — no-op */
  }
}

async function tauriClose(): Promise<void> {
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    await getCurrentWindow().close();
  } catch {
    /* browser dev mode — no-op */
  }
}

/* ============================================================
   COMPONENT
   ============================================================ */
const TitleBar: React.FC = () => {
  const activeCreator = useActiveCreator();

  const handleMinimize = useCallback(() => void tauriMinimize(), []);
  const handleMaximize = useCallback(() => void tauriMaximize(), []);
  const handleClose    = useCallback(() => void tauriClose(), []);

  return (
    <div className="titlebar" style={styles.titlebar}>
      {/* Drag Region (invisible, covers most of the bar) */}
      <div
        className="titlebar-drag"
        data-tauri-drag-region
        style={styles.dragRegion}
      />

      {/* Brand / Logo */}
      <div className="titlebar-brand" style={styles.brand}>
        <span style={styles.logoIcon}>🌴</span>
        <span className="gradient-text" style={styles.logoText}>
          DuLichApp
        </span>
        <span className="titlebar-version" style={styles.version}>v0.1.0</span>
      </div>

      {/* Active Creator — Center */}
      {activeCreator && (
        <div className="titlebar-user" style={styles.userInfo}>
          <span style={styles.userAvatar}>{activeCreator.avatar}</span>
          <div className="titlebar-user-dot" style={styles.userDot} />
          <span style={styles.userName}>{activeCreator.name}</span>
        </div>
      )}

      {/* Window Controls */}
      <div className="titlebar-controls" style={styles.controls}>
        {/* Minimize */}
        <button
          className="titlebar-btn"
          style={styles.winBtn}
          onClick={handleMinimize}
          title="Thu nhỏ"
          tabIndex={-1}
        >
          <MinimizeIcon />
        </button>

        {/* Maximize / Restore */}
        <button
          className="titlebar-btn"
          style={styles.winBtn}
          onClick={handleMaximize}
          title="Phóng to / Thu nhỏ"
          tabIndex={-1}
        >
          <MaximizeIcon />
        </button>

        {/* Close */}
        <button
          className="titlebar-btn titlebar-btn-close"
          style={{ ...styles.winBtn, ...styles.closeBtn }}
          onClick={handleClose}
          title="Đóng"
          tabIndex={-1}
        >
          <CloseIcon />
        </button>
      </div>
    </div>
  );
};

/* ============================================================
   SVG ICONS
   ============================================================ */
const MinimizeIcon: React.FC = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
    <line x1="1" y1="5" x2="9" y2="5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const MaximizeIcon: React.FC = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
    <rect x="1.5" y="1.5" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
  </svg>
);

const CloseIcon: React.FC = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
    <line x1="1.5" y1="1.5" x2="8.5" y2="8.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="8.5" y1="1.5" x2="1.5" y2="8.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

/* ============================================================
   INLINE STYLES
   ============================================================ */
const styles: Record<string, React.CSSProperties> = {
  titlebar: {
    height: '42px',
    background: '#111111',
    borderBottom: '1px solid #1e1e1e',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 8px 0 12px',
    flexShrink: 0,
    position: 'relative',
    zIndex: 50,
  },
  dragRegion: {
    position: 'absolute',
    inset: 0,
    right: '100px',
    cursor: 'default',
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    position: 'relative',
    zIndex: 1,
    pointerEvents: 'none',
  },
  logoIcon: {
    fontSize: '16px',
    lineHeight: 1,
  },
  logoText: {
    fontSize: '13px',
    fontWeight: 800,
    letterSpacing: '-0.03em',
    background: 'linear-gradient(135deg, #a78bfa 0%, #60a5fa 60%, #22d3ee 100%)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
  },
  version: {
    fontSize: '9px',
    fontWeight: 600,
    color: '#606060',
    background: '#1a1a1a',
    border: '1px solid #2a2a2a',
    borderRadius: '999px',
    padding: '1px 6px',
    letterSpacing: '0.03em',
    WebkitTextFillColor: '#606060',
  },
  userInfo: {
    position: 'absolute',
    left: '50%',
    transform: 'translateX(-50%)',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    pointerEvents: 'none',
    zIndex: 1,
  },
  userAvatar: {
    fontSize: '13px',
    lineHeight: 1,
  },
  userDot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    background: '#10b981',
    boxShadow: '0 0 6px rgba(16, 185, 129, 0.6)',
    flexShrink: 0,
  },
  userName: {
    fontSize: '11px',
    color: '#606060',
    fontWeight: 500,
    maxWidth: '180px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  controls: {
    display: 'flex',
    alignItems: 'center',
    gap: '2px',
    position: 'relative',
    zIndex: 1,
  },
  winBtn: {
    width: '30px',
    height: '24px',
    borderRadius: '5px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: 'none',
    background: 'transparent',
    cursor: 'pointer',
    color: '#606060',
    transition: 'background 0.15s ease, color 0.15s ease',
  },
  closeBtn: {
    marginLeft: '2px',
  },
};

export default TitleBar;
