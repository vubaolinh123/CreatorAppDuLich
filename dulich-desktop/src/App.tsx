import { useState, useEffect } from "react";
import TitleBar from "./components/TitleBar";
import Sidebar from "./components/Sidebar";
import HomeScreen from "./screens/HomeScreen";
import StudioScreen from "./screens/StudioScreen";
import NewsChannelScreen from "./screens/NewsChannelScreen";
import CreatorProfileScreen from "./screens/CreatorProfileScreen";
import AlbumScreen from "./screens/AlbumScreen";
import SeedingManagerScreen from "./screens/SeedingManagerScreen";
import LibraryScreen from "./screens/LibraryScreen";
import SettingsScreen from "./screens/SettingsScreen";
import LogsScreen from "./screens/LogsScreen";
import { useAppStore, PageId } from "./stores/appStore";
import { invoke } from "@tauri-apps/api/core";

export default function App() {
  const [page, setPage] = useState<PageId>("home");
  const settings = useAppStore((s) => s.settings);

  useEffect(() => {
    const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;
    if (isTauri) {
      invoke("set_api_keys", {
        elevenlabsKey: settings.elevenLabsKey || "",
        vbeeKey: settings.vbeeKey || "",
        openaiKey: settings.openAiKey || "",
        anthropicKey: settings.anthropicKey || "",
      }).catch((err) => console.error("Failed to propagate API keys to Tauri backend:", err));
    }
  }, [settings.elevenLabsKey, settings.vbeeKey, settings.openAiKey, settings.anthropicKey]);


  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#0a0a0a",
        overflow: "hidden",
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      }}
    >
      {/* Custom Title Bar */}
      <TitleBar />

      {/* App Body */}
      <div style={{ display: "flex", flex: 1, minHeight: 0, overflow: "hidden" }}>
        {/* Sidebar Navigation */}
        <Sidebar activePage={page} onNavigate={setPage} />

        {/* Main Content */}
        <main
          style={{
            flex: 1,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {page === "home"    && <HomeScreen onNavigate={(s) => setPage(s as PageId)} />}
          {page === "studio"  && <StudioScreen />}
          {page === "news"    && <NewsChannelScreen />}
          {page === "creators" && <CreatorProfileScreen />}
          {page === "albums"   && <AlbumScreen />}
          {page === "seeding"  && <SeedingManagerScreen />}
          {page === "library" && <LibraryScreen onNavigate={(s) => setPage(s as PageId)} />}
          {page === "settings" && <SettingsScreen />}
          {page === "logs"    && <LogsScreen />}
        </main>
      </div>
    </div>
  );
}
