/**
 * appStore.ts — Zustand Global State Management
 * DuLichApp Desktop v0.1.0
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

/* ============================================================
   TYPE DEFINITIONS
   ============================================================ */

export type PageId = 'home' | 'studio' | 'news' | 'creators' | 'albums' | 'seeding' | 'library' | 'settings' | 'logs';

export interface Creator {
  id: number;
  name: string;
  voiceId: string;
  avatar: string;
  platform?: string;
}

export interface ResourceSettings {
  maxWorkers: number;   // 1–8
  ramGb: number;        // e.g. 2.0, 4.0, 8.0
  cpuCores: number;     // e.g. 2, 4
  voiceProvider: 'vbee' | 'elevenlabs' | 'mock';
  mongoUri: string;     // e.g. mongodb://localhost:27017
}

export interface Settings {
  dashboardUrl: string;
  anthropicKey: string;
  elevenLabsKey: string;
  vbeeKey: string;
  outputFolder: string;
  creators: Creator[];
  defaultCreatorId: number;
  autoSync: boolean;
  theme: 'dark';
  resources: ResourceSettings;
}

export interface LogLine {
  id: string;
  time: string;
  level: 'info' | 'success' | 'warning' | 'error';
  text: string;
  jobId?: string;
}

export interface PipelineResult {
  script: {
    hook: string;
    body: string;
    cta: string;
  };
  captions: {
    hooks: string[];
    caption_short: string;
    caption_long: string;
    hashtags: string[];
  };
  images: {
    description: string;
    prompts: string[];
  };
  videoPath: string;
  audioPath: string;
  syncedAt?: string;
  thumbnailUrl?: string;
}

export interface Job {
  id: string;
  topic: string;
  creatorId: number;
  templateId: string;
  seeds: string[];
  channel: 'personal' | 'news';
  status: 'idle' | 'running' | 'done' | 'error';
  logs: LogLine[];
  result?: PipelineResult;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
  progress?: number; // 0–100
}

// News batch job (groups multiple clips)
export interface NewsJob {
  id: string;
  briefId: string;
  topics: string[];
  totalClips: number;
  doneClips: number;
  workers: number;
  status: 'pending' | 'running' | 'done' | 'partial' | 'error';
  results: Array<{
    topic: string;
    status: 'done' | 'error';
    videoPath?: string;
    scriptHook?: string;
  }>;
  createdAt: string;
  completedAt?: string;
}

export type LibraryStatus = 'local' | 'synced' | 'published';

export interface LibraryItem {
  id: string;
  topic: string;
  creator: string;
  status: LibraryStatus;
  createdAt: string;
  result: PipelineResult;
  views?: number;
  likes?: number;
  platform?: string;
}

/* ============================================================
   DEFAULT / MOCK DATA
   ============================================================ */

const DEFAULT_CREATORS: Creator[] = [
  {
    id: 1,
    name: 'Nguyễn Thành Nam',
    voiceId: 'EXAVITQu4vr4xnSDxMaL',
    avatar: '👨‍💼',
    platform: 'TikTok @namtravel',
  },
  {
    id: 2,
    name: 'Trần Minh Châu',
    voiceId: 'ErXwobaYiN019PkySvjV',
    avatar: '👩‍💻',
    platform: 'TikTok @chau_dulich',
  },
  {
    id: 3,
    name: 'Lê Hoàng Phúc',
    voiceId: 'VR6AewLTigWG4xSOukaG',
    avatar: '🧑‍🎤',
    platform: 'YouTube @phuctravel',
  },
];

const DEFAULT_RESOURCE_SETTINGS: ResourceSettings = {
  maxWorkers: 2,
  ramGb: 4.0,
  cpuCores: 2,
  voiceProvider: 'vbee',
  mongoUri: 'mongodb://localhost:27017',
};

const DEFAULT_SETTINGS: Settings = {
  dashboardUrl: 'http://localhost:8080',
  anthropicKey: '',
  elevenLabsKey: '',
  vbeeKey: '',
  outputFolder: '',
  creators: DEFAULT_CREATORS,
  defaultCreatorId: 1,
  autoSync: false,
  theme: 'dark',
  resources: DEFAULT_RESOURCE_SETTINGS,
};

const MOCK_LIBRARY: LibraryItem[] = [
  {
    id: 'lib-001',
    topic: 'Top 5 quán cà phê view đẹp ở Đà Lạt không phải ai cũng biết',
    creator: 'Nguyễn Thành Nam',
    status: 'published',
    createdAt: '2026-06-08T09:15:00Z',
    views: 128400,
    likes: 9200,
    platform: 'TikTok',
    result: {
      script: {
        hook: 'Bạn đã biết 5 quán cà phê siêu đẹp ở Đà Lạt này chưa?',
        body: 'Đà Lạt không chỉ nổi tiếng với hoa và sương mù. Còn có những quán cà phê view triệu đô đang chờ bạn khám phá...',
        cta: 'Follow để không bỏ lỡ những địa điểm đẹp nhất Việt Nam nhé!',
      },
      captions: {
        hooks: ['5 quán cafe đẹp nhất Đà Lạt 2026 🌸', 'View đỉnh, đồ uống ngon, giá hợp lý'],
        caption_short: 'Top 5 quán cafe Đà Lạt cực đẹp không phải ai cũng biết ☕🌿',
        caption_long: 'Nếu bạn đang lên kế hoạch đến Đà Lạt, đừng bỏ qua 5 quán cà phê view đẹp này nhé! Từ những ban công nhìn ra thung lũng cho đến những không gian xanh mát giữa rừng thông...',
        hashtags: ['#dalatcafe', '#dulichtrongnuoc', '#vietnam', '#cafedepdalat', '#dulich2026'],
      },
      images: {
        description: 'Quán cà phê view rừng thông Đà Lạt, ánh sáng buổi sáng vàng ấm',
        prompts: [
          'A cozy mountain cafe in Dalat Vietnam surrounded by pine trees, morning golden light, fog, cinematic',
          'Vietnamese coffee shop interior with large windows overlooking valley, minimalist wooden decor',
        ],
      },
      videoPath: 'D:/Output/Videos/dalat_cafe_001.mp4',
      audioPath: 'D:/Output/Audio/dalat_cafe_001.mp3',
      syncedAt: '2026-06-08T12:00:00Z',
    },
  },
  {
    id: 'lib-002',
    topic: 'Hành trình Hội An 3 ngày 2 đêm với budget 2 triệu đồng',
    creator: 'Trần Minh Châu',
    status: 'synced',
    createdAt: '2026-06-07T14:30:00Z',
    views: 54200,
    likes: 3800,
    platform: 'TikTok',
    result: {
      script: {
        hook: '3 ngày ở Hội An chỉ với 2 triệu — bạn có tin không?',
        body: 'Hội An luôn được xếp hạng là một trong những điểm du lịch đẹp nhất thế giới. Nhưng không phải ai cũng biết cách du lịch ở đây với chi phí thấp...',
        cta: 'Save bài này lại để dùng khi đi Hội An nhé! Và nhớ follow mình để cập nhật thêm tips du lịch.',
      },
      captions: {
        hooks: ['Hội An 2 triệu đồng — đủ không?', 'Budget trip Hội An 2026 chi tiết nhất'],
        caption_short: 'Budget trip Hội An 3N2Đ chỉ 2 triệu đồng 🏮✨ Chi tiết trong video!',
        caption_long: 'Mình vừa hoàn thành chuyến đi Hội An 3 ngày 2 đêm với tổng chi phí chỉ hơn 2 triệu đồng. Bao gồm ăn uống, phương tiện, và các hoạt động tham quan...',
        hashtags: ['#hoian', '#budgettravel', '#dulichtietkiem', '#vietnam', '#traveltips'],
      },
      images: {
        description: 'Phố cổ Hội An về đêm với đèn lồng đỏ rực, ánh nước lung linh',
        prompts: [
          'Hoi An ancient town at night, red lanterns glowing, reflection in water, cinematic photography',
          'Traditional Vietnamese lantern street in Hoi An, warm evening light, tourists walking',
        ],
      },
      videoPath: 'D:/Output/Videos/hoian_budget_002.mp4',
      audioPath: 'D:/Output/Audio/hoian_budget_002.mp3',
      syncedAt: '2026-06-07T18:00:00Z',
    },
  },
  {
    id: 'lib-003',
    topic: 'Kinh nghiệm leo núi Fansipan lần đầu — Những điều PHẢI biết',
    creator: 'Lê Hoàng Phúc',
    status: 'local',
    createdAt: '2026-06-09T08:00:00Z',
    result: {
      script: {
        hook: 'Lần đầu leo Fansipan — Mình suýt bỏ cuộc ở độ cao 2800m',
        body: 'Fansipan — Nóc nhà Đông Dương. Nghe có vẻ hùng vĩ nhưng để chinh phục được nó thì bạn cần chuẩn bị kỹ lưỡng hơn bạn nghĩ...',
        cta: 'Nếu bài này có ích, đừng quên để lại một like và share cho bạn bè cùng biết nhé!',
      },
      captions: {
        hooks: ['Leo Fansipan lần đầu — Tất cả những gì bạn cần biết 🏔️', 'Sai lầm của mình khi leo Fansipan'],
        caption_short: 'Kinh nghiệm leo Fansipan từ A–Z cho người mới 🏔️❄️',
        caption_long: 'Sau chuyến chinh phục Fansipan đầu tiên, mình muốn chia sẻ tất cả những gì mình học được...',
        hashtags: ['#fansipan', '#trekking', '#vietnam', '#adventure', '#hiking'],
      },
      images: {
        description: 'Đỉnh Fansipan trong mây, tuyết trắng, cảnh quan hùng vĩ',
        prompts: [
          'Summit of Fansipan mountain Vietnam covered in clouds and snow, epic landscape, golden hour',
          'Trekker at Fansipan peak in Vietnam, misty mountains, dramatic lighting',
        ],
      },
      videoPath: '',
      audioPath: '',
    },
  },
  {
    id: 'lib-004',
    topic: 'Review nhà nghỉ 200k/đêm ở Nha Trang — Liệu có đáng tiền?',
    creator: 'Nguyễn Thành Nam',
    status: 'local',
    createdAt: '2026-06-06T11:20:00Z',
    result: {
      script: {
        hook: 'Mình đã thử ngủ ở nhà nghỉ 200k tại Nha Trang — Đây là kết quả',
        body: 'Nha Trang nổi tiếng với resort sang trọng, nhưng nếu đi budget thì sao? Mình đã test 5 nhà nghỉ giá rẻ nhất khu vực trung tâm...',
        cta: 'Comment địa điểm bạn muốn mình review tiếp theo nhé!',
      },
      captions: {
        hooks: ['Nhà nghỉ 200k Nha Trang có đáng không?', 'Budget accommodation Nha Trang review 2026'],
        caption_short: 'Review nhà nghỉ 200k/đêm ở Nha Trang — Trung thực 100% 🏖️',
        caption_long: 'Mình đã dành 5 ngày để test các nhà nghỉ giá rẻ ở Nha Trang và đây là đánh giá thật sự nhất...',
        hashtags: ['#nhatrang', '#budgethotel', '#travelreview', '#vietnam', '#dulich'],
      },
      images: {
        description: 'Bãi biển Nha Trang buổi sáng sớm, nước xanh trong, bầu trời hồng',
        prompts: [
          'Nha Trang beach Vietnam at sunrise, crystal blue water, golden sand, peaceful atmosphere',
          'Budget guesthouse room in Vietnam with sea view, clean and simple decor',
        ],
      },
      videoPath: 'D:/Output/Videos/nhatrang_review_004.mp4',
      audioPath: 'D:/Output/Audio/nhatrang_review_004.mp3',
    },
  },
];

/* ============================================================
   STORE INTERFACE
   ============================================================ */

interface AppStore {
  // Navigation
  page: PageId;
  setPage: (page: PageId) => void;

  // Settings
  settings: Settings;
  updateSettings: (patch: Partial<Settings>) => void;
  updateResourceSettings: (patch: Partial<ResourceSettings>) => void;
  addCreator: (creator: Omit<Creator, 'id'>) => void;
  removeCreator: (id: number) => void;

  // Active Job
  currentJob: Job | null;
  createJob: (params: Pick<Job, 'topic' | 'creatorId' | 'templateId' | 'seeds' | 'channel'>) => string;
  updateJob: (id: string, patch: Partial<Job>) => void;
  clearJob: () => void;

  // News Batch Jobs
  newsJobs: NewsJob[];
  addNewsJob: (job: Omit<NewsJob, 'id' | 'createdAt'>) => string;
  updateNewsJob: (id: string, patch: Partial<NewsJob>) => void;
  clearNewsJobs: () => void;

  // Global Logs
  globalLogs: LogLine[];
  addLog: (log: Omit<LogLine, 'id' | 'time'>) => void;
  clearLogs: () => void;

  // Library
  library: LibraryItem[];
  loadLibrary: () => void;
  addToLibrary: (item: LibraryItem) => void;
  syncItem: (id: string) => Promise<void>;
  removeFromLibrary: (id: string) => void;

  // UI State
  isLoading: boolean;
  setLoading: (v: boolean) => void;
}

/* ============================================================
   HELPERS
   ============================================================ */

function genId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function nowIso(): string {
  return new Date().toISOString();
}

function nowTime(): string {
  return new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/* ============================================================
   ZUSTAND STORE
   ============================================================ */

export const useAppStore = create<AppStore>()(
  persist(
    (set, get) => ({
      /* ---- Navigation ---- */
      page: 'home',
      setPage: (page) => set({ page }),

      /* ---- Settings ---- */
      settings: DEFAULT_SETTINGS,

      updateSettings: (patch) =>
        set((state) => ({
          settings: { ...state.settings, ...patch },
        })),

      updateResourceSettings: (patch) =>
        set((state) => ({
          settings: {
            ...state.settings,
            resources: { ...state.settings.resources, ...patch },
          },
        })),

      addCreator: (creator) =>
        set((state) => {
          const maxId = Math.max(0, ...state.settings.creators.map((c) => c.id));
          const newCreator: Creator = { ...creator, id: maxId + 1 };
          return {
            settings: {
              ...state.settings,
              creators: [...state.settings.creators, newCreator],
            },
          };
        }),

      removeCreator: (id) =>
        set((state) => ({
          settings: {
            ...state.settings,
            creators: state.settings.creators.filter((c) => c.id !== id),
          },
        })),

      /* ---- Current Job ---- */
      currentJob: null,

      createJob: (params) => {
        const id = genId();
        const newJob: Job = {
          id,
          ...params,
          channel: params.channel || 'personal',
          status: 'idle',
          logs: [],
          createdAt: nowIso(),
          progress: 0,
        };
        set({ currentJob: newJob });
        return id;
      },

      updateJob: (id, patch) =>
        set((state) => {
          if (!state.currentJob || state.currentJob.id !== id) return {};
          return { currentJob: { ...state.currentJob, ...patch } };
        }),

      clearJob: () => set({ currentJob: null }),

      /* ---- News Batch Jobs ---- */
      newsJobs: [],

      addNewsJob: (job) => {
        const id = genId();
        const newJob: NewsJob = { id, createdAt: nowIso(), ...job };
        set((state) => ({ newsJobs: [newJob, ...state.newsJobs] }));
        return id;
      },

      updateNewsJob: (id, patch) =>
        set((state) => ({
          newsJobs: state.newsJobs.map((j) => (j.id === id ? { ...j, ...patch } : j)),
        })),

      clearNewsJobs: () => set({ newsJobs: [] }),

      globalLogs: [],

      addLog: (log) => {
        const newLog: LogLine = {
          id: genId(),
          time: nowTime(),
          ...log,
        };
        set((state) => ({
          globalLogs: [...state.globalLogs.slice(-499), newLog],
          // Also append to currentJob logs if jobId matches
          currentJob:
            state.currentJob && (!log.jobId || log.jobId === state.currentJob.id)
              ? {
                  ...state.currentJob,
                  logs: [...state.currentJob.logs.slice(-199), newLog],
                }
              : state.currentJob,
        }));
      },

      clearLogs: () => set({ globalLogs: [] }),

      /* ---- Library ---- */
      library: MOCK_LIBRARY,

      loadLibrary: () => {
        // In production: read from filesystem or backend
        // For now, no-op (mock data already loaded)
        const existing = get().library;
        if (existing.length === 0) {
          set({ library: MOCK_LIBRARY });
        }
      },

      addToLibrary: (item) =>
        set((state) => ({
          library: [item, ...state.library],
        })),

      syncItem: async (id) => {
        const { addLog } = get();
        addLog({ level: 'info', text: `Đang đồng bộ item ${id}...` });

        // Simulate sync delay
        await new Promise((r) => setTimeout(r, 1500));

        set((state) => ({
          library: state.library.map((item) =>
            item.id === id
              ? { ...item, status: 'synced', result: { ...item.result, syncedAt: nowIso() } }
              : item
          ),
        }));

        addLog({ level: 'success', text: `Đã đồng bộ thành công item ${id} ✓` });
      },

      removeFromLibrary: (id) =>
        set((state) => ({
          library: state.library.filter((item) => item.id !== id),
        })),

      /* ---- UI ---- */
      isLoading: false,
      setLoading: (v) => set({ isLoading: v }),
    }),
    {
      name: 'dulichapp-store',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        settings: state.settings,
        library: state.library,
        newsJobs: state.newsJobs,
        page: state.page,
      }),
    }
  )
);

/* ============================================================
   SELECTOR HOOKS (convenience)
   ============================================================ */

export const useSettings       = () => useAppStore((s) => s.settings);
export const useResourceSettings = () => useAppStore((s) => s.settings?.resources ?? DEFAULT_RESOURCE_SETTINGS);
export const usePage           = () => useAppStore((s) => s.page);
export const useSetPage        = () => useAppStore((s) => s.setPage);
export const useCurrentJob     = () => useAppStore((s) => s.currentJob);
export const useNewsJobs       = () => useAppStore((s) => s.newsJobs);
export const useLibrary        = () => useAppStore((s) => s.library);
export const useGlobalLogs     = () => useAppStore((s) => s.globalLogs);
export const useAddLog         = () => useAppStore((s) => s.addLog);
export const useActiveCreator  = () => {
  const settings = useSettings();
  return settings.creators.find((c) => c.id === settings.defaultCreatorId) ?? settings.creators[0] ?? null;
};
