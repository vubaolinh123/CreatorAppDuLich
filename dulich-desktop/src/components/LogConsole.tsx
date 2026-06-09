/**
 * LogConsole.tsx — Terminal-style Log Viewer
 * DuLichApp Desktop v0.1.0
 *
 * Color coding:
 *   info    → #60a5fa (blue-gray)
 *   success → #10b981 (green)
 *   warning → #f59e0b (amber)
 *   error   → #ef4444 (red)
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import type { LogLine } from '../stores/appStore';

/* ============================================================
   PROPS
   ============================================================ */
interface LogConsoleProps {
  logs: LogLine[];
  title?: string;
  maxHeight?: number | string;
  style?: React.CSSProperties;
  showClear?: boolean;
  onClear?: () => void;
}

/* ============================================================
   LEVEL CONFIG
   ============================================================ */
const LEVEL_CONFIG = {
  info: {
    label: 'INFO',
    labelColor: '#1e3a5f',
    labelBg: 'rgba(96,165,250,0.12)',
    textColor: '#a0a0a0',
    border: 'rgba(96,165,250,0.06)',
  },
  success: {
    label: ' OK ',
    labelColor: '#065f46',
    labelBg: 'rgba(16,185,129,0.12)',
    textColor: '#6ee7b7',
    border: 'rgba(16,185,129,0.08)',
  },
  warning: {
    label: 'WARN',
    labelColor: '#78350f',
    labelBg: 'rgba(245,158,11,0.12)',
    textColor: '#fbbf24',
    border: 'rgba(245,158,11,0.08)',
  },
  error: {
    label: ' ERR',
    labelColor: '#7f1d1d',
    labelBg: 'rgba(239,68,68,0.12)',
    textColor: '#fca5a5',
    border: 'rgba(239,68,68,0.08)',
  },
} as const;

const LEVEL_TEXT_COLOR: Record<string, string> = {
  info:    '#60a5fa',
  success: '#10b981',
  warning: '#f59e0b',
  error:   '#ef4444',
};

/* ============================================================
   COMPONENT
   ============================================================ */
const LogConsole: React.FC<LogConsoleProps> = ({
  logs,
  title = 'Terminal',
  maxHeight = 360,
  style,
  showClear = false,
  onClear,
}) => {
  const bodyRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState<'all' | LogLine['level']>('all');

  /* Auto-scroll when new logs arrive and autoScroll is on */
  useEffect(() => {
    if (autoScroll && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  /* Detect manual scroll up → disable auto-scroll */
  const handleScroll = useCallback(() => {
    const el = bodyRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 20;
    setAutoScroll(atBottom);
  }, []);

  const scrollToBottom = useCallback(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
      setAutoScroll(true);
    }
  }, []);

  const filteredLogs = filter === 'all' ? logs : logs.filter((l) => l.level === filter);

  return (
    <div style={{ ...styles.console, maxHeight, ...style }}>
      {/* Terminal Header — Mac-style dots */}
      <div style={styles.header}>
        <div style={styles.dots}>
          <span style={{ ...styles.dot, background: '#ff5f57' }} />
          <span style={{ ...styles.dot, background: '#ffbd2e' }} />
          <span style={{ ...styles.dot, background: '#28c840' }} />
        </div>

        <span style={styles.title}>{title}</span>

        <div style={styles.headerRight}>
          {/* Filter buttons */}
          <div style={styles.filterGroup}>
            {(['all', 'info', 'success', 'warning', 'error'] as const).map((lvl) => (
              <button
                key={lvl}
                style={{
                  ...styles.filterBtn,
                  ...(filter === lvl ? styles.filterBtnActive : {}),
                  ...(lvl !== 'all' ? { color: LEVEL_TEXT_COLOR[lvl] } : {}),
                }}
                onClick={() => setFilter(lvl)}
                title={`Lọc: ${lvl}`}
              >
                {lvl === 'all' ? 'All' : lvl.toUpperCase()}
              </button>
            ))}
          </div>

          {/* Auto-scroll indicator */}
          {!autoScroll && (
            <button
              style={styles.scrollBtn}
              onClick={scrollToBottom}
              title="Cuộn xuống cuối"
            >
              ↓ Mới nhất
            </button>
          )}

          {/* Clear button */}
          {showClear && onClear && (
            <button style={styles.clearBtn} onClick={onClear} title="Xóa logs">
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Log Body */}
      <div
        ref={bodyRef}
        style={styles.body}
        onScroll={handleScroll}
      >
        {filteredLogs.length === 0 ? (
          <div style={styles.empty}>
            <span style={styles.emptyCursor}>_</span>
            {logs.length === 0
              ? 'Chờ khởi chạy pipeline...'
              : 'Không có log phù hợp với bộ lọc'}
          </div>
        ) : (
          filteredLogs.map((log, i) => (
            <LogEntry key={log.id ?? i} log={log} />
          ))
        )}
      </div>

      {/* Footer — log count */}
      <div style={styles.footer}>
        <span style={styles.footerText}>
          {filteredLogs.length} dòng{filter !== 'all' ? ` (${filter})` : ''} / {logs.length} tổng
        </span>
        <span style={{ ...styles.footerDot, background: autoScroll ? '#10b981' : '#f59e0b' }} />
        <span style={styles.footerText}>
          {autoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
        </span>
      </div>
    </div>
  );
};

/* ============================================================
   LOG ENTRY
   ============================================================ */
interface LogEntryProps {
  log: LogLine;
}

const LogEntry: React.FC<LogEntryProps> = ({ log }) => {
  const cfg = LEVEL_CONFIG[log.level] ?? LEVEL_CONFIG.info;

  return (
    <div
      style={{
        ...styles.logLine,
        borderLeft: `2px solid ${cfg.border}`,
      }}
    >
      {/* Timestamp */}
      <span style={styles.logTime}>{log.time}</span>

      {/* Level Badge */}
      <span
        style={{
          ...styles.logLevel,
          background: cfg.labelBg,
          color: LEVEL_TEXT_COLOR[log.level],
        }}
      >
        {cfg.label}
      </span>

      {/* Message */}
      <span style={{ ...styles.logText, color: cfg.textColor }}>
        {log.text}
      </span>
    </div>
  );
};

/* ============================================================
   STYLES
   ============================================================ */
const styles: Record<string, React.CSSProperties> = {
  console: {
    background: '#050505',
    border: '1px solid #1e1e1e',
    borderRadius: '12px',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
    fontSize: '11px',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 12px',
    background: '#0a0a0a',
    borderBottom: '1px solid #1a1a1a',
    flexShrink: 0,
    gap: '8px',
  },
  dots: {
    display: 'flex',
    gap: '5px',
    flexShrink: 0,
  },
  dot: {
    display: 'inline-block',
    width: '8px',
    height: '8px',
    borderRadius: '50%',
  },
  title: {
    fontSize: '10px',
    color: '#505050',
    fontWeight: 500,
    letterSpacing: '0.05em',
    flex: 1,
    textAlign: 'center',
    fontFamily: "'Inter', sans-serif",
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    flexShrink: 0,
  },
  filterGroup: {
    display: 'flex',
    gap: '2px',
    background: '#111',
    borderRadius: '6px',
    padding: '2px',
    border: '1px solid #222',
  },
  filterBtn: {
    background: 'transparent',
    border: 'none',
    color: '#505050',
    fontSize: '9px',
    fontWeight: 600,
    padding: '2px 6px',
    borderRadius: '4px',
    cursor: 'pointer',
    fontFamily: "'JetBrains Mono', monospace",
    transition: 'all 0.12s ease',
    letterSpacing: '0.04em',
  },
  filterBtnActive: {
    background: '#222',
    color: '#d0d0d0',
  },
  scrollBtn: {
    background: 'rgba(245,158,11,0.1)',
    border: '1px solid rgba(245,158,11,0.3)',
    color: '#f59e0b',
    fontSize: '9px',
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: '4px',
    cursor: 'pointer',
    fontFamily: "'Inter', sans-serif",
    whiteSpace: 'nowrap',
  },
  clearBtn: {
    background: 'rgba(239,68,68,0.08)',
    border: '1px solid rgba(239,68,68,0.2)',
    color: '#ef4444',
    fontSize: '9px',
    fontWeight: 600,
    padding: '2px 7px',
    borderRadius: '4px',
    cursor: 'pointer',
    fontFamily: "'Inter', sans-serif",
  },
  body: {
    flex: 1,
    overflowY: 'auto',
    padding: '10px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '1px',
  },
  empty: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    minHeight: '80px',
    color: '#404040',
    fontSize: '11px',
    fontStyle: 'italic',
    gap: '6px',
    fontFamily: "'JetBrains Mono', monospace",
  },
  emptyCursor: {
    animation: 'pulse 1.2s ease infinite',
    color: '#505050',
  },
  logLine: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
    padding: '2px 6px 2px 8px',
    borderRadius: '4px',
    lineHeight: 1.7,
    borderLeft: '2px solid transparent',
    transition: 'background 0.1s ease',
  },
  logTime: {
    color: '#383838',
    flexShrink: 0,
    fontSize: '10px',
    marginTop: '2px',
    fontVariantNumeric: 'tabular-nums',
    minWidth: '68px',
  },
  logLevel: {
    flexShrink: 0,
    fontSize: '9px',
    fontWeight: 700,
    padding: '2px 5px',
    borderRadius: '3px',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    marginTop: '1px',
    fontFamily: "'JetBrains Mono', monospace",
  },
  logText: {
    flex: 1,
    wordBreak: 'break-word',
    fontSize: '11px',
    lineHeight: 1.7,
  },
  footer: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '5px 12px',
    borderTop: '1px solid #111',
    background: '#0a0a0a',
    flexShrink: 0,
  },
  footerText: {
    fontSize: '9px',
    color: '#383838',
    fontFamily: "'Inter', sans-serif",
  },
  footerDot: {
    width: '5px',
    height: '5px',
    borderRadius: '50%',
    flexShrink: 0,
  },
};

export default LogConsole;
