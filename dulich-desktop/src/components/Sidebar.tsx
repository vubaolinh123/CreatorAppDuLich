/**
 * Sidebar.tsx — Icon Sidebar Navigation (64px wide)
 * DuLichApp Desktop v0.1.0
 */

import React, { useState } from 'react';
import type { PageId } from '../stores/appStore';

/* ============================================================
   NAV ITEM DEFINITION
   ============================================================ */
interface NavItemDef {
  id: PageId;
  icon: string;
  label: string;
}

const NAV_ITEMS: NavItemDef[] = [
  { id: 'home',     icon: '🏠', label: 'Tổng quan' },
  { id: 'studio',   icon: '✨', label: 'Tạo bài' },
  { id: 'news',     icon: '📺', label: 'Kênh Tin Tức' },
  { id: 'creators', icon: '👤', label: 'Người tạo' },
  { id: 'albums',   icon: '🖼️', label: 'Albums Seeding' },
  { id: 'seeding',  icon: '📍', label: 'Địa điểm Seeding' },
  { id: 'library',  icon: '📋', label: 'Thư viện' },
  { id: 'settings', icon: '⚙️', label: 'Cài đặt' },
  { id: 'logs',     icon: '📊', label: 'Nhật ký' },
];

/* ============================================================
   SIDEBAR PROPS
   ============================================================ */
interface SidebarProps {
  activePage: PageId;
  onNavigate: (page: PageId) => void;
}

/* ============================================================
   COMPONENT
   ============================================================ */
const Sidebar: React.FC<SidebarProps> = ({ activePage, onNavigate }) => {
  return (
    <aside style={styles.sidebar}>
      {/* Logo Icon */}
      <div style={styles.logoWrapper} title="DuLichApp">
        <span style={styles.logoEmoji}>🌴</span>
      </div>

      {/* Separator */}
      <div style={styles.separator} />

      {/* Navigation Items */}
      <nav style={styles.nav}>
        {NAV_ITEMS.map((item) => (
          <NavItem
            key={item.id}
            item={item}
            isActive={activePage === item.id}
            onClick={() => onNavigate(item.id)}
          />
        ))}
      </nav>

      {/* Bottom Section */}
      <div style={styles.bottom}>
        <div style={styles.separator} />
        <span style={styles.versionText}>0.1</span>
      </div>
    </aside>
  );
};

/* ============================================================
   NAV ITEM COMPONENT
   ============================================================ */
interface NavItemProps {
  item: NavItemDef;
  isActive: boolean;
  onClick: () => void;
}

const NavItem: React.FC<NavItemProps> = ({ item, isActive, onClick }) => {
  const [isHovered, setIsHovered] = useState(false);

  const buttonStyle: React.CSSProperties = {
    ...styles.navItem,
    ...(isActive ? styles.navItemActive : {}),
    ...(isHovered && !isActive ? styles.navItemHovered : {}),
  };

  return (
    <div style={styles.navItemWrapper}>
      {/* Active indicator bar */}
      {isActive && <div style={styles.activeBar} />}

      <button
        style={buttonStyle}
        onClick={onClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        tabIndex={0}
        aria-label={item.label}
        aria-current={isActive ? 'page' : undefined}
      >
        <span style={styles.navIcon}>{item.icon}</span>
      </button>

      {/* Tooltip */}
      <div
        style={{
          ...styles.tooltip,
          opacity: isHovered ? 1 : 0,
          transform: isHovered
            ? 'translateY(-50%) translateX(0)'
            : 'translateY(-50%) translateX(-4px)',
        }}
        aria-hidden
      >
        {item.label}
        <div style={styles.tooltipArrow} />
      </div>
    </div>
  );
};

/* ============================================================
   STYLES
   ============================================================ */
const styles: Record<string, React.CSSProperties> = {
  sidebar: {
    width: '64px',
    height: '100%',
    background: '#111111',
    borderRight: '1px solid #1e1e1e',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '10px 0 12px',
    flexShrink: 0,
    position: 'relative',
    zIndex: 10,
    overflowX: 'visible',
  },
  logoWrapper: {
    width: '42px',
    height: '42px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '12px',
    background: 'linear-gradient(135deg, rgba(124,58,237,0.15) 0%, rgba(37,99,235,0.12) 100%)',
    border: '1px solid rgba(124,58,237,0.2)',
    cursor: 'default',
    marginBottom: '4px',
    userSelect: 'none',
  },
  logoEmoji: {
    fontSize: '20px',
    lineHeight: 1,
  },
  separator: {
    width: '32px',
    height: '1px',
    background: '#1e1e1e',
    margin: '8px 0',
    flexShrink: 0,
  },
  nav: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '4px',
    flex: 1,
    width: '100%',
    padding: '0 8px',
    overflowX: 'visible',
  },
  navItemWrapper: {
    position: 'relative',
    width: '48px',
    display: 'flex',
    alignItems: 'center',
    overflow: 'visible',
  },
  activeBar: {
    position: 'absolute',
    left: '-8px',
    top: '50%',
    transform: 'translateY(-50%)',
    width: '3px',
    height: '24px',
    background: 'linear-gradient(180deg, #7c3aed 0%, #2563eb 100%)',
    borderRadius: '0 4px 4px 0',
    zIndex: 1,
  },
  navItem: {
    width: '48px',
    height: '48px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '12px',
    cursor: 'pointer',
    border: '1px solid transparent',
    background: 'transparent',
    transition: 'all 0.18s ease',
    position: 'relative',
    userSelect: 'none',
  } as React.CSSProperties,
  navItemHovered: {
    background: '#1a1a1a',
    borderColor: '#2a2a2a',
  },
  navItemActive: {
    background: 'linear-gradient(135deg, rgba(124,58,237,0.18) 0%, rgba(37,99,235,0.16) 100%)',
    borderColor: 'rgba(124,58,237,0.35)',
    boxShadow: '0 2px 12px rgba(124, 58, 237, 0.15)',
  },
  navIcon: {
    fontSize: '19px',
    lineHeight: 1,
    userSelect: 'none',
    transition: 'transform 0.18s ease',
  },
  tooltip: {
    position: 'absolute',
    left: 'calc(100% + 14px)',
    top: '50%',
    transform: 'translateY(-50%)',
    background: '#222222',
    color: '#f0f0f0',
    fontSize: '11px',
    fontWeight: 500,
    fontFamily: "'Inter', sans-serif",
    padding: '5px 10px',
    borderRadius: '7px',
    border: '1px solid #333333',
    whiteSpace: 'nowrap',
    pointerEvents: 'none',
    transition: 'opacity 0.15s ease, transform 0.15s ease',
    boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
    zIndex: 1000,
  },
  tooltipArrow: {
    position: 'absolute',
    right: '100%',
    top: '50%',
    transform: 'translateY(-50%)',
    width: 0,
    height: 0,
    borderTop: '5px solid transparent',
    borderBottom: '5px solid transparent',
    borderRight: '5px solid #333333',
  },
  bottom: {
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '4px',
  },
  versionText: {
    fontSize: '9px',
    color: '#404040',
    fontWeight: 600,
    letterSpacing: '0.06em',
    userSelect: 'none',
  },
};

export default Sidebar;
