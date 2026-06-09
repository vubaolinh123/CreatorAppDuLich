import { Key, Database, Link2, Mic } from "lucide-react";

const settingsSections = [
  { title: "Google API", icon: Link2, desc: "Drive & Sheets integration", status: "Chưa kết nối" },
  { title: "ElevenLabs", icon: Mic, desc: "Voice cloning API", status: "Chưa kết nối" },
  { title: "Ayrshare", icon: Key, desc: "Social media publishing", status: "Chưa kết nối" },
  { title: "Database", icon: Database, desc: "Local SQLite config", status: "OK" },
];

export default function SettingsPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-white mb-6">Cài đặt</h1>
      <div className="space-y-4">
        {settingsSections.map((section) => (
          <div key={section.title} className="bg-[#1a1a1a] rounded-xl border border-[#333] p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <section.icon size={20} className="text-gray-400" />
                <div>
                  <h3 className="text-white font-medium">{section.title}</h3>
                  <p className="text-xs text-gray-500">{section.desc}</p>
                </div>
              </div>
              <span className={`text-xs px-2 py-1 rounded-full ${
                section.status === "OK" ? "bg-green-500/10 text-green-400" : "bg-yellow-500/10 text-yellow-400"
              }`}>
                {section.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
