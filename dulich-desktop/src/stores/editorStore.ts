import { create } from "zustand";

export interface Clip {
  id: string;
  name: string;
  type: "video" | "image" | "audio" | "text";
  start: number;
  duration: number;
  src?: string;
  text?: string;
  track: string;
}

export interface Project {
  id: string;
  name: string;
  creator: string;
  templateId: string;
  clips: Clip[];
  createdAt: string;
  updatedAt: string;
}

export interface SeedingItem {
  id: string;
  name: string;
  type: "restaurant" | "hotel";
  category: string;
  location: string;
  notes: string;
}

export interface Creator {
  id: string;
  name: string;
  email: string;
  voiceId: string;
  templateId: string;
  driveFolder: string;
}

export interface AppState {
  project: Project | null;
  setProject: (project: Project) => void;
  addClip: (clip: Clip) => void;
  removeClip: (id: string) => void;
  updateClip: (id: string, updates: Partial<Clip>) => void;
  seeding: SeedingItem[];
  setSeeding: (seeding: SeedingItem[]) => void;
  addSeeding: (item: SeedingItem) => void;
  removeSeeding: (id: string) => void;
  creators: Creator[];
  setCreators: (creators: Creator[]) => void;
  currentCreator: Creator | null;
  setCurrentCreator: (creator: Creator | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  project: null,
  setProject: (project) => set({ project }),
  addClip: (clip) =>
    set((state) => ({
      project: state.project
        ? { ...state.project, clips: [...state.project.clips, clip] }
        : null,
    })),
  removeClip: (id) =>
    set((state) => ({
      project: state.project
        ? { ...state.project, clips: state.project.clips.filter((c) => c.id !== id) }
        : null,
    })),
  updateClip: (id, updates) =>
    set((state) => ({
      project: state.project
        ? {
            ...state.project,
            clips: state.project.clips.map((c) =>
              c.id === id ? { ...c, ...updates } : c
            ),
          }
        : null,
    })),
  seeding: [],
  setSeeding: (seeding) => set({ seeding }),
  addSeeding: (item) =>
    set((state) => ({ seeding: [...state.seeding, item] })),
  removeSeeding: (id) =>
    set((state) => ({
      seeding: state.seeding.filter((s) => s.id !== id),
    })),
  creators: [],
  setCreators: (creators) => set({ creators }),
  currentCreator: null,
  setCurrentCreator: (creator) => set({ currentCreator: creator }),
}));
