import type { AgentConfigPatch, AgentStrategyConfig, AgentSuggestion, ContentTypeMix, StrategyTab } from '../../types';

export const STRATEGY_TABS: { key: StrategyTab; label: string; icon: string }[] = [
  { key: 'marca',       label: 'Marca',       icon: 'bi-tag' },
  { key: 'publicacion', label: 'Publicación', icon: 'bi-calendar-week' },
  { key: 'referentes',  label: 'Referentes',  icon: 'bi-search' },
  { key: 'diagnostico', label: 'Diagnóstico', icon: 'bi-clipboard2-pulse' },
];

export const isStrategyTab = (value: string | null): value is StrategyTab =>
  STRATEGY_TABS.some(t => t.key === value);

/** Campos que guarda cada pestaña (AD-7). */
export const TAB_FIELDS: Record<StrategyTab, (keyof AgentConfigPatch)[]> = {
  marca: [
    'account_type', 'sector', 'purpose', 'target_audience', 'style_guide', 'default_tone',
    'caption_voice', 'default_language', 'content_pillars', 'banned_phrases', 'humanizer_enabled',
  ],
  publicacion: ['content_type_mix', 'scheduling_mode', 'preferred_days', 'best_times', 'hashtag_strategy'],
  referentes: ['reference_accounts'],
  diagnostico: [],
};

export const MAX_REFERENCE_ACCOUNTS = 5;

export const FIELD_LABELS: Partial<Record<keyof AgentStrategyConfig, string>> = {
  account_type: 'Tipo de cuenta',
  sector: 'Sector',
  purpose: 'Objetivo',
  target_audience: 'Audiencia',
  style_guide: 'Guía de estilo',
  default_tone: 'Tono',
  default_language: 'Idioma',
  caption_voice: 'Estilo de caption',
  content_pillars: 'Pilares de contenido',
  banned_phrases: 'Términos vetados',
  humanizer_enabled: 'Filtro anti-slop',
  content_type_mix: 'Mix semanal',
  scheduling_mode: 'Distribución semanal',
  preferred_days: 'Días',
  best_times: 'Horarios',
  hashtag_strategy: 'Hashtags',
  reference_accounts: 'Referentes',
};

export const DEFAULT_CONFIG: AgentStrategyConfig = {
  account_type: 'personal', sector: '', purpose: '', target_audience: '',
  style_guide: '', default_tone: 'energetic', default_language: 'es',
  best_times: [], content_pillars: [], hashtag_strategy: 'moderate', caption_voice: null,
  reference_accounts: [], posts_per_week: 3, scheduling_mode: 'flexible', preferred_days: [],
  content_type_mix: { post: 2, reel: 1, carousel: 1, story: 0 },
  humanizer_enabled: true, banned_phrases: [],
};

// Valores recomendados por tipo de cuenta (Buffer/Sprout Social 2026 + NapoleonCat)
export const ACCOUNT_TYPE_PRESETS: Record<AgentStrategyConfig['account_type'], AgentConfigPatch> = {
  personal: {
    default_tone: 'energetic',
    best_times: ['09:00', '18:00', '21:00'],
    hashtag_strategy: 'minimal',
    content_type_mix: { post: 1, reel: 3, carousel: 2, story: 2 }, // reels: audio trending
    scheduling_mode: 'flexible',
  },
  professional: {
    default_tone: 'professional',
    best_times: ['13:00', '17:00'],
    hashtag_strategy: 'minimal',
    content_type_mix: { post: 2, reel: 1, carousel: 2, story: 1 }, // carruseles: compensa -12% de alcance en reels
    scheduling_mode: 'fixed',
  },
};

export const TONES: { value: AgentStrategyConfig['default_tone']; label: string; emoji: string }[] = [
  { value: 'energetic',     label: 'Energético',    emoji: '⚡' },
  { value: 'professional',  label: 'Profesional',   emoji: '💼' },
  { value: 'casual',        label: 'Casual',        emoji: '😊' },
  { value: 'inspirational', label: 'Inspiracional', emoji: '✨' },
];

export const CAPTION_VOICE_OPTS: { value: AgentStrategyConfig['caption_voice']; label: string; desc: string }[] = [
  { value: null,           label: 'Automático',  desc: 'hereda de la cuenta' },
  { value: 'personal',     label: 'Personal',    desc: 'corto, emojis' },
  { value: 'professional', label: 'Profesional', desc: 'semiformal' },
];

export const DAYS = [
  { key: 'Monday',    short: 'L', label: 'Lunes'     },
  { key: 'Tuesday',   short: 'M', label: 'Martes'    },
  { key: 'Wednesday', short: 'X', label: 'Miércoles' },
  { key: 'Thursday',  short: 'J', label: 'Jueves'    },
  { key: 'Friday',    short: 'V', label: 'Viernes'   },
  { key: 'Saturday',  short: 'S', label: 'Sábado'    },
  { key: 'Sunday',    short: 'D', label: 'Domingo'   },
];

export const CONTENT_TYPES: { key: keyof ContentTypeMix; label: string; icon: string; desc: string }[] = [
  { key: 'post',     label: 'Foto / Post', icon: '📸', desc: 'Publicación estática' },
  { key: 'reel',     label: 'Reel',        icon: '🎬', desc: 'Vídeo corto' },
  { key: 'carousel', label: 'Carrusel',    icon: '🎠', desc: 'Múltiples imágenes' },
  { key: 'story',    label: 'Story',       icon: '📖', desc: 'Efímero, 24h' },
];

export const WIZARD_OPTIONS = {
  dedica: [
    'Fitness y deporte', 'Deporte profesional', 'Fotografía', 'Videografía / Drone',
    'Gastronomía', 'Moda y estilo', 'Tecnología', 'Arte y creatividad',
    'Música', 'Viajes', 'Lifestyle / Marca personal', 'Negocio / Empresa',
    'Educación', 'Salud y bienestar', 'Videojuegos', 'Humor y entretenimiento',
  ],
  contenido: [
    'Fotografía artística', 'Vídeo con drone', 'Contenido de viajes', 'Día a día / Lifestyle',
    'Entrenamientos y partidos', 'Fotos de producto', 'Vídeos tutoriales',
    'Behind the scenes', 'Infografías', 'Reels / cortos', 'Stories',
    'Resultados y casos de éxito', 'Noticias y tendencias',
  ],
  objetivo: [
    'Inspirar a mi audiencia', 'Compartir mi pasión', 'Crecer como creador de contenido',
    'Vender mis productos/servicios', 'Ganar visibilidad', 'Construir una comunidad',
    'Posicionarme como experto', 'Atraer clientes potenciales', 'Entretener', 'Dar a conocer mi marca',
  ],
};

export const sameValue = (a: unknown, b: unknown): boolean => JSON.stringify(a) === JSON.stringify(b);

export const pickFields = (cfg: AgentStrategyConfig, fields: (keyof AgentConfigPatch)[]): AgentConfigPatch =>
  Object.fromEntries(fields.map(f => [f, cfg[f]])) as AgentConfigPatch;

export const isTabDirty = (tab: StrategyTab, draft: AgentStrategyConfig, saved: AgentStrategyConfig): boolean =>
  TAB_FIELDS[tab].some(f => !sameValue(draft[f], saved[f]));

export const tabOfField = (field: keyof AgentConfigPatch): StrategyTab | null =>
  (Object.keys(TAB_FIELDS) as StrategyTab[]).find(t => TAB_FIELDS[t].includes(field)) ?? null;

/** Representación legible de un valor de configuración (tabla del asistente, modal de presets). */
export const formatValue = (field: keyof AgentStrategyConfig, value: unknown): string => {
  if (value === null || value === undefined || value === '') return '—';
  if (field === 'content_type_mix' && typeof value === 'object') {
    return CONTENT_TYPES
      .map(ct => `${(value as ContentTypeMix)[ct.key] ?? 0} ${ct.label.toLowerCase()}`)
      .join(', ');
  }
  if (field === 'best_times' && Array.isArray(value) && value.length === 0) return 'Usar mis datos';
  if (field === 'preferred_days' && Array.isArray(value)) {
    return value.map(d => DAYS.find(x => x.key === d)?.label ?? d).join(', ') || '—';
  }
  if (Array.isArray(value)) return value.join(', ') || '—';
  if (typeof value === 'boolean') return value ? 'Activado' : 'Desactivado';
  return String(value);
};

/** Diff entre la configuración actual y el preset del nuevo tipo de cuenta (AD-7). */
export const presetChanges = (current: AgentStrategyConfig, newType: AgentStrategyConfig['account_type']) =>
  (Object.entries(ACCOUNT_TYPE_PRESETS[newType]) as [keyof AgentConfigPatch, unknown][])
    .filter(([field, value]) => !sameValue(current[field], value))
    .map(([field, value]) => ({ field, from: current[field], to: value }));

export const isFromReferences = (s: AgentSuggestion) => s.tool_args?.source === 'reference_accounts';
