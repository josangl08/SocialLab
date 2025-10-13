import React, { useState, useEffect } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './PostGenerator.css';

interface PostGeneratorProps {
  onPostGenerated: () => void;
}

interface Export {
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

interface GeneratedPost {
  post_id: string | null;  // Puede ser null si solo es preview
  template_used: string;
  caption: string;
  media_url: string;
  metadata: any;
}

const PostGenerator: React.FC<PostGeneratorProps> = ({ onPostGenerated }) => {
  const [step, setStep] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [exports, setExports] = useState<Export[]>([]);
  const [selectedExport, setSelectedExport] = useState<Export | null>(null);
  const [generatedPost, setGeneratedPost] = useState<GeneratedPost | null>(null);
  const [caption, setCaption] = useState<string>('');
  const [tone, setTone] = useState<string>('energetic');
  const [language, setLanguage] = useState<string>('es');
  const [showScheduleModal, setShowScheduleModal] = useState<boolean>(false);
  const [scheduledDateTime, setScheduledDateTime] = useState<Date | null>(null);
  const [showDraftModal, setShowDraftModal] = useState<boolean>(false);
  const [draftDateTime, setDraftDateTime] = useState<Date | null>(null);

  useEffect(() => {
    fetchAvailableExports();
  }, []);

  const fetchAvailableExports = async () => {
    setLoading(true);
    const token = localStorage.getItem('authToken');

    try {
      // Intentar obtener exports reales de Google Drive
      const response = await fetch('http://localhost:8000/api/drive/exports', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();

        // Si el backend devuelve array vacío o sin datos válidos, usar mock
        if (!data || data.length === 0) {
          console.warn('No se encontraron exports en Google Drive, usando datos mock');
          setExports(getMockExports());
        } else {
          setExports(data);
        }
        setLoading(false);
        return;
      }

      // Fallback: Si falla la petición, usar datos mock
      console.warn('Error en Google Drive API, usando datos mock');
      setExports(getMockExports());
      setLoading(false);
      return;

    } catch (error) {
      console.error('Error fetching exports:', error);
      setExports(getMockExports());
      setLoading(false);
    }
  };

  const getMockExports = (): Export[] => {
    return [
        {
          id: 'export_1',
          export_type: 'player',
          player: {
            name: 'Lionel Messi',
            position: 'Forward',
            team: 'Inter Miami'
          },
          stats: {
            goals: 12,
            assists: 9,
            shots: 54,
            pass_accuracy: '89%'
          },
          date: '2025-01-15'
        },
        {
          id: 'export_2',
          export_type: 'match',
          match: {
            home_team: { name: 'Barcelona' },
            away_team: { name: 'Real Madrid' },
            score: '3-1',
            status: 'finished'
          },
          stats: {
            possession: { home: 58, away: 42 },
            shots: { home: 15, away: 8 }
          },
          date: '2025-01-14'
        },
        {
          id: 'export_3',
          export_type: 'team',
          team: {
            name: 'Manchester City'
          },
          stats: {
            wins: 20,
            draws: 3,
            losses: 2,
            goals_scored: 65,
            goals_conceded: 18
          },
          date: '2025-01-13'
        }
      ];
  };

  const handleSelectExport = (exportData: Export) => {
    setSelectedExport(exportData);
    setStep(2);
  };

  const handleGeneratePost = async () => {
    if (!selectedExport) return;

    setLoading(true);
    const token = localStorage.getItem('authToken');

    try {
      // Mapear tono a caption_style correcto
      const styleMap: Record<string, string> = {
        'energetic': 'engaging',
        'professional': 'informative',
        'casual': 'informative',
        'humorous': 'viral',
        'inspirational': 'engaging'
      };

      const caption_style = styleMap[tone] || 'informative';

      const response = await fetch('http://localhost:8000/content/generate', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          export_id: selectedExport.id,
          instagram_account_id: 1, // TODO: Obtener del usuario
          format_type: 'square',
          caption_style: caption_style,
          language: language,  // Enviar el idioma seleccionado
          auto_publish: false
        })
      });

      if (response.ok) {
        const data = await response.json();

        // Adaptar respuesta del backend al formato esperado
        const adaptedData = {
          post_id: data.post_id,
          template_used: data.template_used?.name || 'Template Mock',
          caption: data.caption || '',
          media_url: data.preview_url || null,  // Puede ser null para datos mock
          metadata: data.metadata || {}
        };

        setGeneratedPost(adaptedData);
        setCaption(data.caption || '');
        setStep(3);
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Error desconocido' }));
        alert(`Error generando post: ${errorData.detail || 'Por favor intenta de nuevo.'}`);
      }
    } catch (error) {
      console.error('Error generating post:', error);
      alert('Error de conexión. Verifica que el backend esté corriendo.');
    } finally {
      setLoading(false);
    }
  };

  const handleSavePost = async (status: 'draft' | 'scheduled', scheduledAt?: string) => {
    if (!generatedPost) return;

    // Si es programado pero no hay fecha, mostrar error
    if (status === 'scheduled' && !scheduledAt) {
      alert('Por favor selecciona una fecha y hora para programar el post');
      return;
    }

    setLoading(true);
    const token = localStorage.getItem('authToken');

    try {
      // Si no hay post_id, crear nuevo post (el backend solo generó preview)
      if (!generatedPost.post_id) {
        // Subir la imagen primero (convertir base64 a blob)
        const base64Data = generatedPost.media_url?.split(',')[1];
        if (!base64Data) {
          alert('Error: No hay imagen para guardar');
          setLoading(false);
          return;
        }

        const byteCharacters = atob(base64Data);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'image/png' });

        // Crear FormData para el post
        const formData = new FormData();
        formData.append('content', caption);
        formData.append('post_type', 'post');
        formData.append('status', status);

        // Si hay fecha programada, agregarla
        if (scheduledAt) {
          formData.append('scheduled_at', scheduledAt);
        }

        formData.append('media_file', blob, `${generatedPost.metadata.export_id}.png`);

        const response = await fetch('http://localhost:8000/posts', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
          body: formData
        });

        if (response.ok) {
          alert(`Post guardado como ${status === 'draft' ? 'borrador' : 'programado'}!`);
          setShowScheduleModal(false); // Cerrar modal de programación
          setShowDraftModal(false); // Cerrar modal de borrador
          onPostGenerated();
          resetGenerator();
        } else {
          const errorData = await response.json().catch(() => ({ detail: 'Error desconocido' }));
          alert(`Error guardando post: ${errorData.detail}`);
        }
      } else {
        // Si ya tiene post_id, actualizar (flujo antiguo, no debería pasar)
        const response = await fetch(`http://localhost:8000/api/posts/${generatedPost.post_id}`, {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            content: caption,
            status: status
          })
        });

        if (response.ok) {
          alert(`Post guardado como ${status === 'draft' ? 'borrador' : 'programado'}!`);
          onPostGenerated();
          resetGenerator();
        } else {
          alert('Error guardando post.');
        }
      }
    } catch (error) {
      console.error('Error saving post:', error);
      alert('Error guardando post.');
    } finally {
      setLoading(false);
    }
  };

  const resetGenerator = () => {
    setStep(1);
    setSelectedExport(null);
    setGeneratedPost(null);
    setCaption('');
    setShowScheduleModal(false);
    setScheduledDateTime(null);
    setShowDraftModal(false);
    setDraftDateTime(null);
  };

  const handleScheduleClick = () => {
    // Obtener fecha/hora mínima (ahora + 5 minutos)
    const now = new Date();
    now.setMinutes(now.getMinutes() + 5);
    setScheduledDateTime(now);
    setShowScheduleModal(true);
  };

  const handleConfirmSchedule = () => {
    if (!scheduledDateTime) {
      alert('Por favor selecciona una fecha y hora');
      return;
    }

    const now = new Date();

    // Verificar que la fecha sea futura
    if (scheduledDateTime <= now) {
      alert('La fecha programada debe ser en el futuro');
      return;
    }

    // Convertir a formato ISO para el backend
    const isoDateTime = scheduledDateTime.toISOString();
    handleSavePost('scheduled', isoDateTime);
  };

  const handleDraftClick = () => {
    // Obtener fecha/hora actual como referencia
    const now = new Date();
    setDraftDateTime(now);
    setShowDraftModal(true);
  };

  const handleConfirmDraft = () => {
    if (!draftDateTime) {
      alert('Por favor selecciona una fecha y hora');
      return;
    }

    // Convertir a formato ISO para el backend
    const isoDateTime = draftDateTime.toISOString();
    handleSavePost('draft', isoDateTime);
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
    <div className="post-generator">
      {/* Progress Indicator */}
      <div className="progress-indicator">
        <div className={`progress-step ${step >= 1 ? 'active' : ''}`}>
          <div className="step-number">1</div>
          <div className="step-label">Seleccionar Datos</div>
        </div>
        <div className={`progress-line ${step >= 2 ? 'active' : ''}`}></div>
        <div className={`progress-step ${step >= 2 ? 'active' : ''}`}>
          <div className="step-number">2</div>
          <div className="step-label">Configurar</div>
        </div>
        <div className={`progress-line ${step >= 3 ? 'active' : ''}`}></div>
        <div className={`progress-step ${step >= 3 ? 'active' : ''}`}>
          <div className="step-number">3</div>
          <div className="step-label">Revisar y Guardar</div>
        </div>
      </div>

      {/* Step 1: Select Export */}
      {step === 1 && (
        <div className="step-content">
          <h2><i className="bi bi-graph-up me-2"></i>Selecciona Datos de PROJECT 1</h2>
          <p className="step-description">
            Elige las estadísticas que quieres convertir en un post de Instagram
          </p>

          {loading ? (
            <div className="loading-state">
              <div className="spinner"></div>
              <p>Cargando datos disponibles...</p>
            </div>
          ) : exports.length === 0 ? (
            <div className="empty-state">
              <p><i className="bi bi-inbox me-2"></i>No hay datos disponibles de PROJECT 1</p>
              <p className="text-muted">Exporta estadísticas desde PROJECT 1 primero</p>
            </div>
          ) : (
            <div className="exports-grid">
              {exports.map((exp) => (
                <div
                  key={exp.id}
                  className="export-card"
                  onClick={() => handleSelectExport(exp)}
                >
                  <div className="export-header">
                    <span className="export-type-badge">
                      {exp.export_type === 'player' && <><i className="bi bi-person me-1"></i>Player</>}
                      {exp.export_type === 'match' && <><i className="bi bi-trophy me-1"></i>Match</>}
                      {exp.export_type === 'team' && <><i className="bi bi-shield-check me-1"></i>Team</>}
                    </span>
                    {exp.date && (
                      <span className="export-date">{new Date(exp.date).toLocaleDateString()}</span>
                    )}
                  </div>
                  <h3 className="export-title">{getExportTitle(exp)}</h3>
                  <div className="export-preview">
                    {Object.entries(exp.stats).slice(0, 3).map(([key, value]) => (
                      <div key={key} className="stat-item">
                        <span className="stat-label">{key.replace('_', ' ')}</span>
                        <span className="stat-value">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Step 2: Configure */}
      {step === 2 && selectedExport && (
        <div className="step-content">
          <h2><i className="bi bi-gear me-2"></i>Configurar Post</h2>
          <p className="step-description">
            Personaliza el tono y el idioma para el caption generado por IA
          </p>

          <div className="config-section">
            <div className="selected-export-preview">
              <h3><i className="bi bi-graph-up me-2"></i>Datos seleccionados:</h3>
              <p><strong>{getExportTitle(selectedExport)}</strong></p>
            </div>

            <div className="form-group">
              <label><i className="bi bi-palette me-2"></i>Tono del Caption:</label>
              <select value={tone} onChange={(e) => setTone(e.target.value)}>
                <option value="energetic">Energético</option>
                <option value="professional">Profesional</option>
                <option value="casual">Casual</option>
                <option value="humorous">Divertido</option>
                <option value="inspirational">Inspiracional</option>
              </select>
            </div>

            <div className="form-group">
              <label><i className="bi bi-globe me-2"></i>Idioma:</label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="es">Español</option>
                <option value="en">Inglés</option>
              </select>
            </div>

            <div className="action-buttons">
              <button className="btn-secondary" onClick={() => setStep(1)}>
                <i className="bi bi-arrow-left me-2"></i>Atrás
              </button>
              <button
                className="btn-primary"
                onClick={handleGeneratePost}
                disabled={loading}
              >
                {loading ? <><i className="bi bi-arrow-repeat me-2"></i>Generando...</> : <><i className="bi bi-stars me-2"></i>Generar Post</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Review and Save */}
      {step === 3 && generatedPost && (
        <div className="step-content">
          <h2><i className="bi bi-eye me-2"></i>Revisar Post Generado</h2>
          <p className="step-description">
            Edita el caption si es necesario y guarda tu post
          </p>

          <div className="post-preview">
            <div className="preview-image-section">
              <h3><i className="bi bi-image me-2"></i>Imagen:</h3>
              {generatedPost.media_url ? (
                <img
                  src={generatedPost.media_url}
                  alt="Post preview"
                  className="preview-image"
                />
              ) : (
                <div className="image-placeholder">
                  <p><i className="bi bi-card-image me-2"></i>Modo de Prueba</p>
                  <p className="text-muted">
                    Usando datos de ejemplo. La imagen se generará cuando uses datos reales de Google Drive.
                  </p>
                  <p className="text-muted">Template: {generatedPost.template_used}</p>
                </div>
              )}
            </div>

            <div className="preview-caption-section">
              <h3><i className="bi bi-pencil-square me-2"></i>Caption:</h3>
              <textarea
                className="caption-editor"
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                rows={8}
                placeholder="Escribe tu caption aquí..."
              />
              <p className="caption-length">{caption.length} caracteres</p>
            </div>
          </div>

          <div className="action-buttons">
            <button className="btn-secondary" onClick={resetGenerator}>
              <i className="bi bi-arrow-repeat me-2"></i>Generar Otro
            </button>
            <button
              className="btn-outline"
              onClick={handleDraftClick}
              disabled={loading}
            >
              <i className="bi bi-save me-2"></i>Guardar Borrador
            </button>
            <button
              className="btn-primary"
              onClick={handleScheduleClick}
              disabled={loading}
            >
              <i className="bi bi-calendar-check me-2"></i>Programar
            </button>
          </div>
        </div>
      )}

      {/* Schedule Modal */}
      {showScheduleModal && (
        <div className="schedule-modal-overlay" onClick={() => setShowScheduleModal(false)}>
          <div className="schedule-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="schedule-modal-header">
              <h3><i className="bi bi-calendar-check me-2"></i>Programar Publicación</h3>
              <button
                className="modal-close"
                onClick={() => setShowScheduleModal(false)}
                aria-label="Cerrar"
              >
                <i className="bi bi-x-lg"></i>
              </button>
            </div>

            <div className="schedule-modal-body">
              <p className="modal-description">
                Selecciona la fecha y hora en que deseas publicar este post en Instagram
              </p>

              <div className="form-group">
                <label>
                  <i className="bi bi-calendar me-2"></i>Fecha y Hora:
                </label>
                <DatePicker
                  selected={scheduledDateTime}
                  onChange={(date: Date | null) => setScheduledDateTime(date)}
                  showTimeSelect
                  timeFormat="HH:mm"
                  timeIntervals={15}
                  dateFormat="dd/MM/yyyy HH:mm"
                  minDate={new Date()}
                  className="datetime-picker-input"
                  calendarClassName="datetime-picker-calendar"
                  placeholderText="Selecciona fecha y hora"
                  showMonthDropdown
                  showYearDropdown
                  dropdownMode="select"
                  popperPlacement="top"
                />
                <small className="text-muted">
                  La fecha debe ser al menos 5 minutos en el futuro
                </small>
              </div>
            </div>

            <div className="schedule-modal-footer">
              <button
                className="btn-secondary"
                onClick={() => setShowScheduleModal(false)}
                disabled={loading}
              >
                Cancelar
              </button>
              <button
                className="btn-primary"
                onClick={handleConfirmSchedule}
                disabled={loading || !scheduledDateTime}
              >
                {loading ? (
                  <><i className="bi bi-arrow-repeat me-2"></i>Guardando...</>
                ) : (
                  <><i className="bi bi-calendar-check me-2"></i>Confirmar Programación</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Draft Modal */}
      {showDraftModal && (
        <div className="schedule-modal-overlay" onClick={() => setShowDraftModal(false)}>
          <div className="schedule-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="schedule-modal-header">
              <h3><i className="bi bi-save me-2"></i>Guardar Borrador</h3>
              <button
                className="modal-close"
                onClick={() => setShowDraftModal(false)}
                aria-label="Cerrar"
              >
                <i className="bi bi-x-lg"></i>
              </button>
            </div>

            <div className="schedule-modal-body">
              <p className="modal-description">
                Selecciona la fecha y hora en que deseas trabajar en este borrador
              </p>

              <div className="form-group">
                <label>
                  <i className="bi bi-calendar me-2"></i>Fecha y Hora:
                </label>
                <DatePicker
                  selected={draftDateTime}
                  onChange={(date: Date | null) => setDraftDateTime(date)}
                  showTimeSelect
                  timeFormat="HH:mm"
                  timeIntervals={15}
                  dateFormat="dd/MM/yyyy HH:mm"
                  className="datetime-picker-input"
                  calendarClassName="datetime-picker-calendar"
                  placeholderText="Selecciona fecha y hora"
                  showMonthDropdown
                  showYearDropdown
                  dropdownMode="select"
                  popperPlacement="top"
                />
                <small className="text-muted">
                  Esta fecha te ayudará a organizar cuándo trabajar en el borrador
                </small>
              </div>
            </div>

            <div className="schedule-modal-footer">
              <button
                className="btn-secondary"
                onClick={() => setShowDraftModal(false)}
                disabled={loading}
              >
                Cancelar
              </button>
              <button
                className="btn-primary"
                onClick={handleConfirmDraft}
                disabled={loading || !draftDateTime}
              >
                {loading ? (
                  <><i className="bi bi-arrow-repeat me-2"></i>Guardando...</>
                ) : (
                  <><i className="bi bi-save me-2"></i>Guardar Borrador</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PostGenerator;
