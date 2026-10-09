import React, { useState, useEffect } from 'react';
import { apiClient, ApiError } from '../../api/client';
import './SportsExportSelector.css';

export interface Export {
  id: string;
  export_type: string;
  player?: {
    name: string;
    position?: string;
    team?: string;
  };
  match?: {
    home_team: any;
    away_team: any;
    score?: string;
    status?: string;
  };
  team?: {
    name: string;
  };
  stats: any;
  image_url?: string;
  date?: string;
}

export interface SportsExportResult {
  caption: string;
  mediaUrl: string | null;
  templateUsed?: string;
  metadata?: any;
}

interface SportsExportSelectorProps {
  accountId?: number | null;
  onPostGenerated: (result: SportsExportResult) => void;
  onCancel?: () => void;
}

export const getMockExports = (): Export[] => [
  {
    id: 'export_1',
    export_type: 'player',
    player: {
      name: 'Lionel Messi',
      position: 'Forward',
      team: 'Inter Miami',
    },
    stats: {
      goals: 12,
      assists: 9,
      shots: 54,
      pass_accuracy: '89%',
    },
    date: '2025-01-15',
  },
  {
    id: 'export_2',
    export_type: 'match',
    match: {
      home_team: { name: 'Barcelona' },
      away_team: { name: 'Real Madrid' },
      score: '3-1',
      status: 'finished',
    },
    stats: {
      possession: { home: 58, away: 42 },
      shots: { home: 15, away: 8 },
    },
    date: '2025-01-14',
  },
  {
    id: 'export_3',
    export_type: 'team',
    team: {
      name: 'Manchester City',
    },
    stats: {
      wins: 20,
      draws: 3,
      losses: 2,
      goals_scored: 65,
      goals_conceded: 18,
    },
    date: '2025-01-13',
  },
];

export const SportsExportSelector: React.FC<SportsExportSelectorProps> = ({
  accountId,
  onPostGenerated,
  onCancel,
}) => {
  const [step, setStep] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [exports, setExports] = useState<Export[]>([]);
  const [selectedExport, setSelectedExport] = useState<Export | null>(null);
  const [tone, setTone] = useState<string>('energetic');
  const [language, setLanguage] = useState<string>('es');

  useEffect(() => {
    fetchAvailableExports();
  }, []);

  const fetchAvailableExports = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<Export[]>('/api/drive/exports');
      if (!data || data.length === 0) {
        setExports(getMockExports());
      } else {
        setExports(data);
      }
    } catch {
      setExports(getMockExports());
    } finally {
      setLoading(false);
    }
  };

  const handleSelectExport = (exportData: Export) => {
    setSelectedExport(exportData);
    setStep(2);
  };

  const handleGeneratePost = async () => {
    if (!selectedExport) return;
    setLoading(true);

    try {
      const styleMap: Record<string, string> = {
        energetic: 'engaging',
        professional: 'informative',
        casual: 'informative',
        humorous: 'viral',
        inspirational: 'engaging',
      };

      const caption_style = styleMap[tone] || 'informative';

      const data = await apiClient.post<any>('/content/generate', {
        export_id: selectedExport.id,
        instagram_account_id: accountId || 1,
        format_type: 'square',
        caption_style: caption_style,
        language: language,
        auto_publish: false,
      });

      onPostGenerated({
        caption: data.caption || '',
        mediaUrl: data.preview_url || null,
        templateUsed: data.template_used?.name || 'Template Mock',
        metadata: data.metadata || {},
      });
    } catch (error) {
      if (error instanceof ApiError) {
        alert(`Error generando post: ${error.detail || 'Por favor intenta de nuevo.'}`);
      } else {
        alert('Error de conexión. Verifica que el backend esté corriendo.');
      }
    } finally {
      setLoading(false);
    }
  };

  const getExportTitle = (exp: Export) => {
    if (exp.export_type === 'player' && exp.player) {
      return `${exp.player.name} - ${exp.player.position || 'Player'}`;
    } else if (exp.export_type === 'match' && exp.match) {
      return `${exp.match.home_team.name} vs ${exp.match.away_team.name}`;
    } else if (exp.export_type === 'team' && exp.team) {
      return `${exp.team.name} - Team Stats`;
    }
    return 'Export Data';
  };

  return (
    <div className="sports-export-selector">
      {step === 1 && (
        <div className="sports-step">
          <div className="d-flex justify-content-between align-items-center mb-3">
            <div>
              <h4 className="m-0 text-light">
                <i className="bi bi-graph-up me-2 text-primary"></i>Selecciona datos de PROJECT 1
              </h4>
              <p className="text-secondary small m-0">
                Elige las estadísticas deportivas que quieres convertir en publicación
              </p>
            </div>
            {onCancel && (
              <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onCancel}>
                Cerrar
              </button>
            )}
          </div>

          {loading ? (
            <div className="text-center py-4">
              <div className="spinner-border text-primary" role="status"></div>
              <p className="text-secondary mt-2 small">Cargando datos disponibles...</p>
            </div>
          ) : exports.length === 0 ? (
            <div className="alert alert-secondary text-center">
              <i className="bi bi-inbox me-2"></i>No hay datos disponibles de PROJECT 1
            </div>
          ) : (
            <div className="sports-exports-grid">
              {exports.map((exp) => (
                <div
                  key={exp.id}
                  className="sports-export-card"
                  onClick={() => handleSelectExport(exp)}
                  role="button"
                  tabIndex={0}
                >
                  <div className="d-flex justify-content-between align-items-center mb-2">
                    <span className="badge bg-purple-subtle text-light border border-secondary">
                      {exp.export_type === 'player' && <><i className="bi bi-person me-1"></i>Jugador</>}
                      {exp.export_type === 'match' && <><i className="bi bi-trophy me-1"></i>Partido</>}
                      {exp.export_type === 'team' && <><i className="bi bi-shield-check me-1"></i>Equipo</>}
                    </span>
                    {exp.date && <span className="text-secondary small">{exp.date}</span>}
                  </div>
                  <h6 className="text-light mb-2">{getExportTitle(exp)}</h6>
                  <div className="sports-stats-preview">
                    {Object.entries(exp.stats || {}).slice(0, 3).map(([key, value]) => (
                      <div key={key} className="sports-stat-item">
                        <span className="text-secondary">{key.replace('_', ' ')}:</span>
                        <strong className="text-light ms-1">{String(value)}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {step === 2 && selectedExport && (
        <div className="sports-step">
          <h4 className="text-light mb-1">
            <i className="bi bi-gear me-2 text-primary"></i>Configurar estadísticas
          </h4>
          <p className="text-secondary small mb-3">
            Datos seleccionados: <strong className="text-light">{getExportTitle(selectedExport)}</strong>
          </p>

          <div className="row g-3 mb-3">
            <div className="col-md-6">
              <label className="form-label text-secondary small">Tono del Caption</label>
              <select
                className="form-select form-select-sm bg-dark text-light border-secondary"
                value={tone}
                onChange={(e) => setTone(e.target.value)}
              >
                <option value="energetic">Energético</option>
                <option value="professional">Profesional</option>
                <option value="casual">Casual</option>
                <option value="humorous">Divertido</option>
                <option value="inspirational">Inspiracional</option>
              </select>
            </div>
            <div className="col-md-6">
              <label className="form-label text-secondary small">Idioma</label>
              <select
                className="form-select form-select-sm bg-dark text-light border-secondary"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              >
                <option value="es">Español</option>
                <option value="en">Inglés</option>
              </select>
            </div>
          </div>

          <div className="d-flex justify-content-between">
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary"
              onClick={() => setStep(1)}
              disabled={loading}
            >
              <i className="bi bi-arrow-left me-1"></i>Cambiar datos
            </button>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={handleGeneratePost}
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="spinner-border spinner-border-sm me-1" role="status"></span>
                  Generando...
                </>
              ) : (
                <>
                  <i className="bi bi-stars me-1"></i>Generar publicación
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SportsExportSelector;
