import React, { useState, useEffect } from 'react';
import { HybridSelect } from './HybridSelect';

export interface ContentTypeMix {
  post: number;
  reel: number;
  carousel: number;
  story: number;
}

export interface AgentStrategyConfig {
  account_type: 'personal' | 'professional';
  sector: string;
  purpose: string;
  target_audience: string;
  style_guide: string;
  default_tone: 'energetic' | 'professional' | 'casual' | 'inspirational';
  default_language: 'es' | 'en';
  posting_frequency: string;
  best_times: string[];
  content_pillars: string[];
  hashtag_strategy: 'minimal' | 'moderate' | 'maximum';
  reference_accounts: string[];
  posts_per_week: number;
  scheduling_mode: 'fixed' | 'flexible';
  preferred_days: string[];
  content_type_mix: ContentTypeMix;
}

const DEFAULT: AgentStrategyConfig = {
  account_type: 'personal', sector: '', purpose: '', target_audience: '',
  style_guide: '', default_tone: 'energetic', default_language: 'es',
  posting_frequency: 'few_times_week', best_times: ['09:00', '18:00'],
  content_pillars: [], hashtag_strategy: 'moderate', reference_accounts: [],
  posts_per_week: 3, scheduling_mode: 'flexible', preferred_days: [],
  content_type_mix: { post: 2, reel: 1, carousel: 1, story: 0 },
};

interface Props {
  accountId: number;
  accountUsername?: string;
  show: boolean;
  onHide: () => void;
  onSave: () => void;
}

// Research-backed defaults (Buffer/Sprout Social 2026 + NapoleonCat algorithm data)
const PERSONAL_STRATEGY_DEFAULTS = {
  default_tone: 'energetic' as const,
  best_times: ['09:00', '18:00', '21:00'],  // Thu 9am + eves (Buffer 9.6M posts)
  hashtag_strategy: 'minimal' as const,      // 3-5 cap enforced Dec 2025
  content_type_mix: { post: 1, reel: 3, carousel: 2, story: 2 }, // reel-heavy: trending audio access
  posts_per_week: 5,
  scheduling_mode: 'flexible' as const,
};

const PROFESSIONAL_STRATEGY_DEFAULTS = {
  default_tone: 'professional' as const,
  best_times: ['13:00', '17:00'],            // Tue 13-19h, decision-maker window
  hashtag_strategy: 'minimal' as const,      // 3-5 cap, industry+branded
  content_type_mix: { post: 2, reel: 1, carousel: 2, story: 1 }, // carousel-heavy: compensates -12% reel reach
  posts_per_week: 5,
  scheduling_mode: 'fixed' as const,
};

const TONES = [
  { value: 'energetic'     as const, label: 'Energético',    emoji: '⚡', color: '#f59e0b', bg: 'rgba(245,158,11,0.12)'  },
  { value: 'professional'  as const, label: 'Profesional',   emoji: '💼', color: '#3b82f6', bg: 'rgba(59,130,246,0.12)'  },
  { value: 'casual'        as const, label: 'Casual',        emoji: '😊', color: '#22c55e', bg: 'rgba(34,197,94,0.12)'   },
  { value: 'inspirational' as const, label: 'Inspiracional', emoji: '✨', color: '#a855f7', bg: 'rgba(168,85,247,0.12)'  },
];

const HASHTAG_OPTS = [
  { value: 'minimal'  as const, label: 'Mínimos',   desc: '3–5'   },
  { value: 'moderate' as const, label: 'Moderados', desc: '6–10'  },
  { value: 'maximum'  as const, label: 'Máximos',   desc: '11–15' },
];

const DAYS = [
  { key: 'Monday',    short: 'L', label: 'Lunes'     },
  { key: 'Tuesday',   short: 'M', label: 'Martes'    },
  { key: 'Wednesday', short: 'X', label: 'Miércoles' },
  { key: 'Thursday',  short: 'J', label: 'Jueves'    },
  { key: 'Friday',    short: 'V', label: 'Viernes'   },
  { key: 'Saturday',  short: 'S', label: 'Sábado'    },
  { key: 'Sunday',    short: 'D', label: 'Domingo'   },
];

const CONTENT_TYPES = [
  { key: 'post'     as const, label: 'Foto / Post', icon: '📸', desc: 'Publicación estática'    },
  { key: 'reel'     as const, label: 'Reel',        icon: '🎬', desc: 'Vídeo corto'             },
  { key: 'carousel' as const, label: 'Carrusel',    icon: '🎠', desc: 'Múltiples imágenes'      },
  { key: 'story'    as const, label: 'Story',       icon: '📖', desc: 'Efímero, 24h'            },
];

const WIZARD_OPTIONS = {
  dedica: [
    'Fitness y deporte','Deporte profesional','Fotografía','Videografía / Drone',
    'Gastronomía','Moda y estilo','Tecnología','Arte y creatividad',
    'Música','Viajes','Lifestyle / Marca personal','Negocio / Empresa',
    'Educación','Salud y bienestar','Videojuegos','Humor y entretenimiento',
  ],
  contenido: [
    'Fotografía artística','Vídeo con drone','Contenido de viajes','Día a día / Lifestyle',
    'Entrenamientos y partidos','Fotos de producto','Vídeos tutoriales',
    'Behind the scenes','Infografías','Reels / cortos','Stories',
    'Resultados y casos de éxito','Noticias y tendencias',
  ],
  objetivo: [
    'Inspirar a mi audiencia','Compartir mi pasión','Crecer como creador de contenido',
    'Vender mis productos/servicios','Ganar visibilidad','Construir una comunidad',
    'Posicionarme como experto','Atraer clientes potenciales','Entretener','Dar a conocer mi marca',
  ],
};

interface WizardState { dedica: string[]; contenido: string[]; objetivo: string[]; referentes: string[]; }

const inp: React.CSSProperties = {
  backgroundColor: 'rgba(255,255,255,0.05)',
  border: '1px solid rgba(255,255,255,0.12)',
  color: '#fff', borderRadius: 8,
};

const SL = ({ icon, label }: { icon: string; label: string }) => (
  <div className="d-flex align-items-center gap-2 mb-3" style={{ marginTop: 4 }}>
    <i className={`bi ${icon}`} style={{ color: '#818cf8', fontSize: '0.85rem' }} />
    <span style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.4)' }}>{label}</span>
  </div>
);

const FL = ({ icon, label }: { icon: string; label: string }) => (
  <label className="form-label small d-flex align-items-center gap-2 mb-1" style={{ color: 'rgba(255,255,255,0.65)', fontWeight: 500 }}>
    <i className={`bi ${icon}`} style={{ color: 'rgba(255,255,255,0.28)', fontSize: '0.8rem' }} />
    {label}
  </label>
);

const Sep = () => <hr style={{ borderColor: 'rgba(255,255,255,0.07)', margin: '20px 0 16px' }} />;

const WQ = ({ num, label, children }: { num: number; label: string; children: React.ReactNode }) => (
  <div className="mb-4">
    <div className="d-flex align-items-center gap-2 mb-2">
      <span style={{ width: 22, height: 22, borderRadius: '50%', backgroundColor: 'rgba(99,102,241,0.25)', border: '1px solid rgba(129,140,248,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', fontWeight: 700, color: '#a5b4fc', flexShrink: 0 }}>{num}</span>
      <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'rgba(255,255,255,0.9)' }}>{label}</span>
    </div>
    {children}
  </div>
);

function Counter({ value, onChange, min = 0, max = 7 }: { value: number; onChange: (v: number) => void; min?: number; max?: number }) {
  return (
    <div className="d-flex align-items-center gap-1">
      <button type="button" onClick={() => onChange(Math.max(min, value - 1))}
        style={{ width: 26, height: 26, borderRadius: '50%', border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)', cursor: 'pointer', fontSize: '1rem', lineHeight: 1, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        −
      </button>
      <span style={{ width: 22, textAlign: 'center', fontWeight: 700, fontSize: '0.95rem', color: value > 0 ? '#fff' : 'rgba(255,255,255,0.25)' }}>{value}</span>
      <button type="button" onClick={() => onChange(Math.min(max, value + 1))}
        style={{ width: 26, height: 26, borderRadius: '50%', border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)', cursor: 'pointer', fontSize: '1rem', lineHeight: 1, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        +
      </button>
    </div>
  );
}

export const AgentStrategyDrawer: React.FC<Props> = ({
  accountId, accountUsername, show, onHide, onSave,
}) => {
  const [cfg, setCfg] = useState<AgentStrategyConfig>(DEFAULT);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newPillar, setNewPillar] = useState('');
  const [newTime, setNewTime] = useState('');
  const [newRef, setNewRef] = useState('');
  const [visible, setVisible] = useState(false);
  const [animate, setAnimate] = useState(false);
  const [wizardMode, setWizardMode] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [typeAdjusted, setTypeAdjusted] = useState<'personal' | 'professional' | null>(null);
  const [generatedBanner, setGeneratedBanner] = useState(false);
  const [suggestingTimes, setSuggestingTimes] = useState(false);
  const [wizard, setWizard] = useState<WizardState>({ dedica: [], contenido: [], objetivo: [], referentes: [] });

  // ── Load strategy directly from API every time the drawer opens ──
  useEffect(() => {
    if (!show || !accountId) return;
    const token = localStorage.getItem('authToken');
    if (!token) return;
    setLoading(true);
    setWizardMode(false);
    setSaved(false);
    setError(null);
    fetch(`http://localhost:8000/api/agent/config/${accountId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => setCfg({ ...DEFAULT, ...data }))
      .catch(() => setCfg(DEFAULT))
      .finally(() => setLoading(false));
  }, [show, accountId]);

  useEffect(() => {
    if (show) {
      setVisible(true);
      requestAnimationFrame(() => requestAnimationFrame(() => setAnimate(true)));
    } else {
      setAnimate(false);
      const t = setTimeout(() => setVisible(false), 300);
      return () => clearTimeout(t);
    }
  }, [show]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && show) onHide(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [show, onHide]);

  const set = <K extends keyof AgentStrategyConfig>(k: K, v: AgentStrategyConfig[K]) =>
    setCfg(p => ({ ...p, [k]: v }));

  const setMix = (type: keyof ContentTypeMix, value: number) =>
    setCfg(p => {
      const mix = { ...p.content_type_mix, [type]: value };
      const total = Object.values(mix).reduce((s, n) => s + n, 0);
      return { ...p, content_type_mix: mix, posts_per_week: total };
    });

  const totalPosts = Object.values(cfg.content_type_mix).reduce((s, n) => s + n, 0);

  const toggleDay = (day: string) => {
    const days = cfg.preferred_days;
    set('preferred_days', days.includes(day) ? days.filter(d => d !== day) : [...days, day]);
  };

  const addPillar = () => {
    const t = newPillar.trim();
    if (t && !cfg.content_pillars.includes(t)) { set('content_pillars', [...cfg.content_pillars, t]); setNewPillar(''); }
  };
  const addTime = () => {
    if (newTime && /^\d{2}:\d{2}$/.test(newTime) && !cfg.best_times.includes(newTime)) {
      set('best_times', [...cfg.best_times, newTime].sort()); setNewTime('');
    }
  };
  const addRef = () => {
    const t = newRef.trim().replace(/^@/, '');
    if (t && !cfg.reference_accounts.includes(t)) { set('reference_accounts', [...cfg.reference_accounts, t]); setNewRef(''); }
  };

  const handleSuggestTimes = async () => {
    const token = localStorage.getItem('authToken');
    if (!token) return;
    setSuggestingTimes(true);
    try {
      const res = await fetch('http://localhost:8000/api/agent/suggest-times', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ sector: cfg.sector, target_audience: cfg.target_audience, default_tone: cfg.default_tone, account_type: cfg.account_type }),
      });
      if (res.ok) { const d = await res.json(); if (d.best_times) set('best_times', d.best_times); }
    } catch { /* silent */ }
    finally { setSuggestingTimes(false); }
  };

  const handleAccountTypeChange = (newType: 'personal' | 'professional') => {
    const defaults = newType === 'professional' ? PROFESSIONAL_STRATEGY_DEFAULTS : PERSONAL_STRATEGY_DEFAULTS;
    setCfg(prev => ({ ...prev, account_type: newType, ...defaults }));
    setTypeAdjusted(newType);
    setTimeout(() => setTypeAdjusted(null), 3500);
  };

  const handleGenerate = async () => {
    const token = localStorage.getItem('authToken');
    if (!token) return;
    if (!wizard.dedica.length && !wizard.contenido.length && !wizard.objetivo.length) {
      setError('Responde al menos una pregunta.'); return;
    }
    setGenerating(true); setError(null);
    try {
      const res = await fetch('http://localhost:8000/api/agent/generate-strategy', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(wizard),
      });
      if (!res.ok) throw new Error('Error al generar');
      const generated = await res.json();
      setCfg(prev => ({
        ...prev, ...generated,
        reference_accounts: wizard.referentes.length ? wizard.referentes : prev.reference_accounts,
        // Let AI-generated content_type_mix apply (no override)
      }));
      setWizardMode(false);
      setGeneratedBanner(true);
      setTimeout(() => setGeneratedBanner(false), 5000);
    } catch (e: any) { setError(e.message); }
    finally { setGenerating(false); }
  };

  const handleSave = async () => {
    const token = localStorage.getItem('authToken');
    if (!token) return;
    setSaving(true); setError(null);
    try {
      const payload = { ...cfg, posts_per_week: totalPosts };
      const res = await fetch(`http://localhost:8000/api/agent/config/${accountId}`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Error al guardar');
      setSaved(true);
      setTimeout(() => setSaved(false), 4000);
      onSave();
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  };

  if (!visible) return null;

  return (
    <>
      <div className={`offcanvas-backdrop fade ${animate ? 'show' : ''}`} onClick={onHide} style={{ zIndex: 1044 }} />
      <div className={`offcanvas offcanvas-end ${animate ? 'show' : ''}`}
        style={{ width: 460, zIndex: 1045, backgroundColor: '#111419', borderLeft: '1px solid rgba(255,255,255,0.07)', display: 'flex', flexDirection: 'column' }} tabIndex={-1}>

        {/* Header */}
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid rgba(255,255,255,0.07)', flexShrink: 0 }}>
          <div className="d-flex justify-content-between align-items-start">
            <div>
              <div className="d-flex align-items-center gap-2 mb-1">
                {wizardMode
                  ? <button type="button" onClick={() => setWizardMode(false)} style={{ background: 'none', border: 'none', color: '#818cf8', padding: 0, cursor: 'pointer', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <i className="bi bi-arrow-left" /> Volver
                    </button>
                  : <><span style={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: '#22c55e', display: 'inline-block', boxShadow: '0 0 5px #22c55e' }} />
                    <span style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.35)' }}>Estrategia del Agente</span></>
                }
              </div>
              <h5 className="mb-0 fw-bold text-white">{wizardMode ? '✨ Asistente IA' : `@${accountUsername || `cuenta_${accountId}`}`}</h5>
            </div>
            <button type="button" className="btn-close btn-close-white mt-1" onClick={onHide} style={{ opacity: 0.4 }} />
          </div>
        </div>

        {/* Body */}
        <div className="offcanvas-body" style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.08) transparent' }}>

          {loading ? (
            <div className="d-flex justify-content-center align-items-center" style={{ height: 200 }}>
              <div className="spinner-border text-primary" style={{ width: 28, height: 28, borderWidth: 2 }} role="status" />
            </div>

          ) : wizardMode ? (
            <>
              <p style={{ fontSize: '0.83rem', color: 'rgba(255,255,255,0.5)', marginBottom: 24, lineHeight: 1.6 }}>
                Selecciona o escribe tus opciones. Cuantas más respondas, más precisa será la estrategia.
              </p>
              <WQ num={1} label="¿A qué se dedica tu cuenta?">
                <HybridSelect options={WIZARD_OPTIONS.dedica} value={wizard.dedica} onChange={v => setWizard(p => ({ ...p, dedica: v }))} placeholder="Añadir otro..." accentColor="#818cf8" accentBg="rgba(99,102,241,0.14)" />
              </WQ>
              <WQ num={2} label="¿Qué tipo de contenido vas a publicar?">
                <HybridSelect options={WIZARD_OPTIONS.contenido} value={wizard.contenido} onChange={v => setWizard(p => ({ ...p, contenido: v }))} placeholder="Añadir otro tipo..." accentColor="#34d399" accentBg="rgba(52,211,153,0.12)" />
              </WQ>
              <WQ num={3} label="¿Qué quieres conseguir con Instagram?">
                <HybridSelect options={WIZARD_OPTIONS.objetivo} value={wizard.objetivo} onChange={v => setWizard(p => ({ ...p, objetivo: v }))} placeholder="Añadir otro objetivo..." accentColor="#f59e0b" accentBg="rgba(245,158,11,0.12)" />
              </WQ>
              <WQ num={4} label="¿Tienes cuentas referentes? (opcional)">
                <div className="d-flex flex-wrap gap-2 mb-2">
                  {wizard.referentes.map((r, i) => (
                    <span key={i} style={{ backgroundColor: 'rgba(59,130,246,0.12)', color: '#93c5fd', border: '1px solid rgba(59,130,246,0.25)', borderRadius: 20, padding: '4px 10px', fontSize: '0.76rem', display: 'flex', alignItems: 'center', gap: 5 }}>
                      @{r}<button type="button" onClick={() => setWizard(p => ({ ...p, referentes: p.referentes.filter((_, j) => j !== i) }))} style={{ background: 'none', border: 'none', color: '#93c5fd', padding: 0, cursor: 'pointer', lineHeight: 1, fontSize: '1rem', opacity: 0.55 }}>×</button>
                    </span>
                  ))}
                </div>
                <div className="d-flex gap-2">
                  <div className="input-group input-group-sm">
                    <span className="input-group-text" style={{ backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.4)', borderRight: 'none' }}>@</span>
                    <input className="form-control" style={{ ...inp, borderLeft: 'none' }} placeholder="cuenta_referente"
                      onKeyDown={e => { if (e.key === 'Enter') { const t = (e.target as HTMLInputElement).value.trim().replace(/^@/, ''); if (t && !wizard.referentes.includes(t)) { setWizard(p => ({ ...p, referentes: [...p.referentes, t] })); (e.target as HTMLInputElement).value = ''; } } }} />
                  </div>
                  <button type="button" className="btn btn-sm btn-outline-secondary" style={{ flexShrink: 0 }}
                    onClick={e => { const i = (e.currentTarget.previousElementSibling?.querySelector('input') as HTMLInputElement); if (i) { const t = i.value.trim().replace(/^@/, ''); if (t && !wizard.referentes.includes(t)) { setWizard(p => ({ ...p, referentes: [...p.referentes, t] })); i.value = ''; } } }}>
                    <i className="bi bi-plus" />
                  </button>
                </div>
              </WQ>
              {error && <div className="alert alert-danger py-2 px-3 small" style={{ borderRadius: 8 }}><i className="bi bi-exclamation-circle me-2" />{error}</div>}
            </>

          ) : (
            <>
              {generatedBanner && (
                <div className="alert py-2 px-3 mb-3 small d-flex align-items-center gap-2" style={{ backgroundColor: 'rgba(99,102,241,0.15)', border: '1px solid rgba(129,140,248,0.4)', color: '#a5b4fc', borderRadius: 10 }}>
                  <i className="bi bi-stars" /> Estrategia generada — revisa y guarda.
                </div>
              )}
              {saved && (
                <div className="alert py-2 px-3 mb-3 small d-flex align-items-center gap-2" style={{ backgroundColor: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.3)', color: '#86efac', borderRadius: 10 }}>
                  <i className="bi bi-check2-circle" /> Estrategia guardada correctamente.
                </div>
              )}
              {typeAdjusted && (
                <div className="alert py-2 px-3 mb-3 small d-flex align-items-center gap-2" style={{ backgroundColor: 'rgba(168,85,247,0.12)', border: '1px solid rgba(168,85,247,0.35)', color: '#d8b4fe', borderRadius: 10 }}>
                  <i className="bi bi-sliders" /> Ajustado para cuenta {typeAdjusted === 'professional' ? 'profesional' : 'personal'} — mix de contenido y horarios actualizados.
                </div>
              )}

              <button type="button" className="btn w-100 mb-4" onClick={() => { setWizardMode(true); setError(null); }}
                style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(168,85,247,0.2))', border: '1px solid rgba(129,140,248,0.35)', color: '#c4b5fd', borderRadius: 10, padding: '10px', fontWeight: 600, fontSize: '0.85rem' }}>
                <i className="bi bi-stars me-2" />✨ Generar estrategia con IA
                <span style={{ display: 'block', fontSize: '0.72rem', fontWeight: 400, opacity: 0.7, marginTop: 2 }}>Responde 3–4 preguntas y la IA rellena el formulario</span>
              </button>

              {/* Tipo de cuenta */}
              <SL icon="bi-grid-1x2" label="Tipo de Cuenta" />
              <div className="d-flex gap-3 mb-4">
                {([
                  { value: 'personal' as const, icon: 'bi-person', label: 'Personal', desc: 'Creador, 1ª persona, audio trending' },
                  { value: 'professional' as const, icon: 'bi-briefcase', label: 'Profesional', desc: 'Marca, funnel conversión, cadencia fija' },
                ]).map(opt => (
                  <div key={opt.value} className="flex-grow-1" onClick={() => handleAccountTypeChange(opt.value)}
                    style={{ border: cfg.account_type === opt.value ? '1.5px solid #818cf8' : '1px solid rgba(255,255,255,0.09)', borderRadius: 12, padding: '14px 12px', cursor: 'pointer', backgroundColor: cfg.account_type === opt.value ? 'rgba(99,102,241,0.1)' : 'rgba(255,255,255,0.02)', transition: 'all 0.15s' }}>
                    <i className={`bi ${opt.icon} d-block mb-1`} style={{ fontSize: '1.25rem', color: cfg.account_type === opt.value ? '#a5b4fc' : 'rgba(255,255,255,0.3)' }} />
                    <div style={{ fontWeight: 600, fontSize: '0.83rem', color: cfg.account_type === opt.value ? '#fff' : 'rgba(255,255,255,0.6)' }}>{opt.label}</div>
                    <div style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.3)', marginTop: 2 }}>{opt.desc}</div>
                  </div>
                ))}
              </div>

              {/* Identidad */}
              <SL icon="bi-tag" label="Identidad" />
              <div className="mb-3">
                <FL icon="bi-building" label="Sector / Nicho" />
                <input className="form-control form-control-sm" style={inp} value={cfg.sector} onChange={e => set('sector', e.target.value)} placeholder="Ej: Deporte profesional, Fotografía, Fitness" />
              </div>
              <div className="mb-3">
                <FL icon="bi-bullseye" label="Objetivo Principal" />
                <input className="form-control form-control-sm" style={inp} value={cfg.purpose} onChange={e => set('purpose', e.target.value)} placeholder="Ej: Inspirar y compartir mi pasión" />
              </div>
              <div className="mb-4">
                <FL icon="bi-people" label="Audiencia Objetivo" />
                <textarea className="form-control form-control-sm" style={{ ...inp, resize: 'none' }} rows={2} value={cfg.target_audience} onChange={e => set('target_audience', e.target.value)} placeholder="Ej: Jóvenes aficionados al fútbol y la fotografía, 18-30 años" />
              </div>

              <Sep />

              {/* Voz */}
              <SL icon="bi-mic" label="Voz del Agente" />
              <div className="mb-3">
                <FL icon="bi-sliders" label="Tono" />
                <div className="d-flex flex-wrap gap-2">
                  {TONES.map(t => (
                    <button key={t.value} type="button" onClick={() => set('default_tone', t.value)}
                      style={{ border: cfg.default_tone === t.value ? `1.5px solid ${t.color}` : '1px solid rgba(255,255,255,0.1)', borderRadius: 20, padding: '5px 13px', fontSize: '0.8rem', fontWeight: cfg.default_tone === t.value ? 600 : 400, backgroundColor: cfg.default_tone === t.value ? t.bg : 'transparent', color: cfg.default_tone === t.value ? t.color : 'rgba(255,255,255,0.5)', cursor: 'pointer', transition: 'all 0.15s' }}>
                      {t.emoji} {t.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="mb-3">
                <FL icon="bi-translate" label="Idioma" />
                <div className="d-flex gap-2">
                  {(['es', 'en'] as const).map(lang => (
                    <button key={lang} type="button" className={`btn btn-sm ${cfg.default_language === lang ? 'btn-primary' : 'btn-outline-secondary'}`}
                      style={{ minWidth: 60, fontWeight: cfg.default_language === lang ? 600 : 400 }} onClick={() => set('default_language', lang)}>
                      {lang === 'es' ? '🇪🇸 ES' : '🇬🇧 EN'}
                    </button>
                  ))}
                </div>
              </div>
              <div className="mb-4">
                <FL icon="bi-pencil" label="Guía de Estilo" />
                <textarea className="form-control form-control-sm" style={{ ...inp, resize: 'none' }} rows={3} value={cfg.style_guide} onChange={e => set('style_guide', e.target.value)} placeholder="Ej: Tono cercano e inspirador, combinar fútbol con fotografía y viajes" />
              </div>

              <Sep />

              {/* Contenido */}
              <SL icon="bi-palette" label="Contenido" />
              <div className="mb-3">
                <FL icon="bi-collection" label="Pilares de Contenido" />
                <div className="d-flex flex-wrap gap-2 mb-2">
                  {cfg.content_pillars.map((p, i) => (
                    <span key={i} style={{ backgroundColor: 'rgba(99,102,241,0.14)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.28)', borderRadius: 20, padding: '4px 10px', fontSize: '0.76rem', display: 'flex', alignItems: 'center', gap: 5 }}>
                      {p}<button type="button" onClick={() => set('content_pillars', cfg.content_pillars.filter((_, j) => j !== i))} style={{ background: 'none', border: 'none', color: '#a5b4fc', padding: 0, cursor: 'pointer', lineHeight: 1, fontSize: '1rem', opacity: 0.55 }}>×</button>
                    </span>
                  ))}
                </div>
                <div className="d-flex gap-2">
                  <input className="form-control form-control-sm" style={inp} value={newPillar} onChange={e => setNewPillar(e.target.value)} onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addPillar())} placeholder="Ej: Fotografía de viajes, Día de partido" />
                  <button type="button" className="btn btn-sm btn-outline-secondary" onClick={addPillar} style={{ flexShrink: 0 }}><i className="bi bi-plus" /></button>
                </div>
              </div>
              <div className="mb-4">
                <FL icon="bi-hash" label="Hashtags por Post" />
                <div className="d-flex gap-2">
                  {HASHTAG_OPTS.map(o => (
                    <button key={o.value} type="button" onClick={() => set('hashtag_strategy', o.value)} className={`btn btn-sm flex-grow-1 ${cfg.hashtag_strategy === o.value ? 'btn-primary' : 'btn-outline-secondary'}`}>
                      {o.label}<div style={{ fontSize: '0.62rem', opacity: 0.65, fontWeight: 400 }}>{o.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              <Sep />

              {/* Publicación */}
              <SL icon="bi-calendar-week" label="Publicación" />

              {/* Content type mix */}
              <div className="mb-4">
                <div className="d-flex align-items-center justify-content-between mb-2">
                  <FL icon="bi-layout-three-columns" label="Piezas por tipo y semana" />
                  <span style={{ fontSize: '0.72rem', color: totalPosts > 0 ? '#a5b4fc' : 'rgba(255,255,255,0.3)', fontWeight: 600 }}>
                    {totalPosts} total/semana
                  </span>
                </div>
                <div style={{ backgroundColor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 12, overflow: 'hidden' }}>
                  {CONTENT_TYPES.map((ct, i) => (
                    <div key={ct.key} className="d-flex align-items-center justify-content-between px-3 py-2"
                      style={{ borderBottom: i < CONTENT_TYPES.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none' }}>
                      <div className="d-flex align-items-center gap-2">
                        <span style={{ fontSize: '1.1rem' }}>{ct.icon}</span>
                        <div>
                          <div style={{ fontSize: '0.82rem', fontWeight: 600, color: cfg.content_type_mix[ct.key] > 0 ? '#fff' : 'rgba(255,255,255,0.4)' }}>{ct.label}</div>
                          <div style={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.28)' }}>{ct.desc}</div>
                        </div>
                      </div>
                      <Counter value={cfg.content_type_mix[ct.key]} onChange={v => setMix(ct.key, v)} />
                    </div>
                  ))}
                </div>
              </div>

              {/* Scheduling mode + days */}
              <div className="mb-3">
                <FL icon="bi-shuffle" label="Distribución semanal" />
                <div className="d-flex gap-2 mb-3">
                  {([
                    { value: 'flexible' as const, icon: 'bi-shuffle',   label: 'Flexible',        desc: 'Agente distribuye libremente' },
                    { value: 'fixed'    as const, icon: 'bi-calendar3', label: 'Días específicos', desc: 'Tú eliges los días' },
                  ]).map(m => (
                    <div key={m.value} className="flex-grow-1" onClick={() => set('scheduling_mode', m.value)}
                      style={{ border: cfg.scheduling_mode === m.value ? '1.5px solid #3b82f6' : '1px solid rgba(255,255,255,0.09)', borderRadius: 10, padding: '10px 12px', cursor: 'pointer', textAlign: 'center', backgroundColor: cfg.scheduling_mode === m.value ? 'rgba(59,130,246,0.1)' : 'rgba(255,255,255,0.02)', transition: 'all 0.15s' }}>
                      <i className={`bi ${m.icon} d-block mb-1`} style={{ fontSize: '1.1rem', color: cfg.scheduling_mode === m.value ? '#60a5fa' : 'rgba(255,255,255,0.28)' }} />
                      <div style={{ fontWeight: 600, fontSize: '0.78rem', color: cfg.scheduling_mode === m.value ? '#fff' : 'rgba(255,255,255,0.55)' }}>{m.label}</div>
                      <div style={{ fontSize: '0.65rem', color: cfg.scheduling_mode === m.value ? 'rgba(96,165,250,0.75)' : 'rgba(255,255,255,0.25)', marginTop: 1 }}>{m.desc}</div>
                    </div>
                  ))}
                </div>
                {cfg.scheduling_mode === 'fixed' && (
                  <>
                    <FL icon="bi-calendar-day" label="Días preferidos" />
                    <div className="d-flex gap-2">
                      {DAYS.map(d => {
                        const on = cfg.preferred_days.includes(d.key);
                        return (
                          <button key={d.key} type="button" onClick={() => toggleDay(d.key)} title={d.label}
                            style={{ width: 36, height: 36, borderRadius: '50%', border: on ? '1.5px solid #3b82f6' : '1px solid rgba(255,255,255,0.12)', backgroundColor: on ? 'rgba(59,130,246,0.15)' : 'transparent', color: on ? '#60a5fa' : 'rgba(255,255,255,0.4)', fontWeight: on ? 700 : 400, fontSize: '0.75rem', cursor: 'pointer', transition: 'all 0.15s', padding: 0 }}>
                            {d.short}
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>

              {/* Best times */}
              <div className="mb-4">
                <div className="d-flex align-items-center justify-content-between mb-1">
                  <FL icon="bi-clock" label="Horarios Óptimos" />
                  <button type="button" onClick={handleSuggestTimes} disabled={suggestingTimes}
                    style={{ background: 'none', border: 'none', color: '#818cf8', fontSize: '0.73rem', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', gap: 4 }}>
                    {suggestingTimes ? <span className="spinner-border spinner-border-sm" style={{ width: 10, height: 10, borderWidth: 1 }} /> : <i className="bi bi-stars" />}
                    Sugerir con IA
                  </button>
                </div>
                <div className="d-flex flex-wrap gap-2 mb-2">
                  {cfg.best_times.map((t, i) => (
                    <span key={i} style={{ backgroundColor: 'rgba(59,130,246,0.12)', color: '#93c5fd', border: '1px solid rgba(59,130,246,0.25)', borderRadius: 20, padding: '4px 10px', fontSize: '0.76rem', display: 'flex', alignItems: 'center', gap: 5 }}>
                      <i className="bi bi-clock" style={{ fontSize: '0.68rem' }} /> {t}
                      <button type="button" onClick={() => set('best_times', cfg.best_times.filter((_, j) => j !== i))} style={{ background: 'none', border: 'none', color: '#93c5fd', padding: 0, cursor: 'pointer', lineHeight: 1, fontSize: '1rem', opacity: 0.55 }}>×</button>
                    </span>
                  ))}
                </div>
                <div className="d-flex gap-2">
                  <input type="time" className="form-control form-control-sm" style={{ ...inp, colorScheme: 'dark', maxWidth: 120 }} value={newTime} onChange={e => setNewTime(e.target.value)} onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addTime())} />
                  <button type="button" className="btn btn-sm btn-outline-secondary" onClick={addTime}><i className="bi bi-plus" /> Añadir</button>
                </div>
              </div>

              <Sep />

              {/* Cuentas Referentes */}
              <SL icon="bi-search" label="Cuentas Referentes" />
              <FL icon="bi-at" label="Cuentas de referencia (opcional)" />
              <div className="d-flex flex-wrap gap-2 mb-2">
                {cfg.reference_accounts.map((r, i) => (
                  <span key={i} style={{ backgroundColor: 'rgba(59,130,246,0.12)', color: '#93c5fd', border: '1px solid rgba(59,130,246,0.25)', borderRadius: 20, padding: '4px 10px', fontSize: '0.76rem', display: 'flex', alignItems: 'center', gap: 5 }}>
                    @{r}<button type="button" onClick={() => set('reference_accounts', cfg.reference_accounts.filter((_, j) => j !== i))} style={{ background: 'none', border: 'none', color: '#93c5fd', padding: 0, cursor: 'pointer', lineHeight: 1, fontSize: '1rem', opacity: 0.55 }}>×</button>
                  </span>
                ))}
              </div>
              <div className="d-flex gap-2">
                <div className="input-group input-group-sm">
                  <span className="input-group-text" style={{ backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.4)', borderRight: 'none' }}>@</span>
                  <input className="form-control form-control-sm" style={{ ...inp, borderLeft: 'none' }} value={newRef} onChange={e => setNewRef(e.target.value)} onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addRef())} placeholder="cuenta_referente" />
                </div>
                <button type="button" className="btn btn-sm btn-outline-secondary" onClick={addRef} style={{ flexShrink: 0 }}><i className="bi bi-plus" /></button>
              </div>

              {error && <div className="alert alert-danger py-2 px-3 mt-3 small" style={{ borderRadius: 8 }}><i className="bi bi-exclamation-circle me-2" />{error}</div>}
            </>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '14px 24px', borderTop: '1px solid rgba(255,255,255,0.07)', backgroundColor: '#0d1015', flexShrink: 0 }}>
          {wizardMode ? (
            <button type="button" className="btn w-100"
              style={{ background: 'linear-gradient(135deg, #6366f1, #a855f7)', border: 'none', color: '#fff', fontWeight: 600, padding: '10px', borderRadius: 10 }}
              onClick={handleGenerate} disabled={generating}>
              {generating ? <><span className="spinner-border spinner-border-sm me-2" />Generando...</> : <><i className="bi bi-stars me-2" />Generar Estrategia</>}
            </button>
          ) : (
            <button type="button" className="btn btn-primary w-100" style={{ fontWeight: 600, padding: '10px', borderRadius: 10 }} onClick={handleSave} disabled={saving || loading}>
              {saving ? <><span className="spinner-border spinner-border-sm me-2" />Guardando...</> : <><i className="bi bi-robot me-2" />Guardar Estrategia</>}
            </button>
          )}
        </div>
      </div>
    </>
  );
};

export default AgentStrategyDrawer;
