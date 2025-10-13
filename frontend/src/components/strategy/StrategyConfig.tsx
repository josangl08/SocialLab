import React, { useState, useEffect } from 'react';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './StrategyConfig.css';

interface StrategySettings {
  default_tone: string;
  default_language: string;
  posting_frequency: string;
  best_times: string[];
  content_pillars: string[];
  hashtag_strategy: string;
  caption_length: string;
}

const StrategyConfig: React.FC = () => {
  const [settings, setSettings] = useState<StrategySettings>({
    default_tone: 'energetic',
    default_language: 'es',
    posting_frequency: 'daily',
    best_times: ['09:00', '18:00'],
    content_pillars: ['Match Highlights', 'Player Stats', 'Team News'],
    hashtag_strategy: 'moderate',
    caption_length: 'medium'
  });

  const [loading, setLoading] = useState<boolean>(false);
  const [saved, setSaved] = useState<boolean>(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    const token = localStorage.getItem('authToken');
    if (!token) return;

    try {
      // Por ahora usamos configuración por defecto
      // En producción: GET /api/strategy/settings
    } catch (error) {
      console.error('Error loading settings:', error);
    }
  };

  const handleSave = async () => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      alert('Debes iniciar sesión');
      return;
    }

    setLoading(true);
    setSaved(false);

    try {
      // En producción: POST /api/strategy/settings
      await new Promise(resolve => setTimeout(resolve, 1000));

      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (error) {
      console.error('Error saving settings:', error);
      alert('Error guardando configuración');
    } finally {
      setLoading(false);
    }
  };

  const handleAddPillar = () => {
    const newPillar = prompt('Nuevo pilar de contenido:');
    if (newPillar && newPillar.trim()) {
      setSettings({
        ...settings,
        content_pillars: [...settings.content_pillars, newPillar.trim()]
      });
    }
  };

  const handleRemovePillar = (index: number) => {
    setSettings({
      ...settings,
      content_pillars: settings.content_pillars.filter((_, i) => i !== index)
    });
  };

  const handleAddTime = () => {
    const newTime = prompt('Horario óptimo (formato HH:MM):');
    if (newTime && /^\d{2}:\d{2}$/.test(newTime)) {
      setSettings({
        ...settings,
        best_times: [...settings.best_times, newTime]
      });
    } else if (newTime) {
      alert('Formato inválido. Usa HH:MM (ej: 09:00)');
    }
  };

  const handleRemoveTime = (index: number) => {
    setSettings({
      ...settings,
      best_times: settings.best_times.filter((_, i) => i !== index)
    });
  };

  return (
    <div className="strategy-config">
      <div className="strategy-header">
        <h2><i className="bi bi-bullseye me-2"></i>Estrategia de Community Manager</h2>
        <p className="strategy-description">
          Configura las preferencias predeterminadas para la generación de contenido con IA
        </p>
      </div>

      {saved && (
        <div className="alert alert-success">
          <i className="bi bi-check-circle me-2"></i>Configuración guardada exitosamente
        </div>
      )}

      <div className="strategy-sections">
        {/* Tone and Language */}
        <div className="strategy-section">
          <h3><i className="bi bi-pencil-square me-2"></i>Estilo de Contenido</h3>

          <div className="form-group">
            <label>Tono por defecto:</label>
            <select
              value={settings.default_tone}
              onChange={(e) => setSettings({ ...settings, default_tone: e.target.value })}
            >
              <option value="energetic">Energético</option>
              <option value="professional">Profesional</option>
              <option value="casual">Casual</option>
              <option value="humorous">Divertido</option>
              <option value="inspirational">Inspiracional</option>
            </select>
          </div>

          <div className="form-group">
            <label>Idioma por defecto:</label>
            <select
              value={settings.default_language}
              onChange={(e) => setSettings({ ...settings, default_language: e.target.value })}
            >
              <option value="es">Español</option>
              <option value="en">Inglés</option>
            </select>
          </div>

          <div className="form-group">
            <label>Longitud de captions:</label>
            <select
              value={settings.caption_length}
              onChange={(e) => setSettings({ ...settings, caption_length: e.target.value })}
            >
              <option value="short">Corto (50-100 caracteres)</option>
              <option value="medium">Medio (100-200 caracteres)</option>
              <option value="long">Largo (200-500 caracteres)</option>
            </select>
          </div>
        </div>

        {/* Posting Schedule */}
        <div className="strategy-section">
          <h3><i className="bi bi-calendar-event me-2"></i>Calendario de Publicación</h3>

          <div className="form-group">
            <label>Frecuencia de publicación:</label>
            <select
              value={settings.posting_frequency}
              onChange={(e) => setSettings({ ...settings, posting_frequency: e.target.value })}
            >
              <option value="multiple_daily">Varias veces al día</option>
              <option value="daily">Una vez al día</option>
              <option value="few_times_week">Varias veces a la semana</option>
              <option value="weekly">Una vez a la semana</option>
            </select>
          </div>

          <div className="form-group">
            <label>Horarios óptimos de publicación:</label>
            <div className="tags-container">
              {settings.best_times.map((time, index) => (
                <div key={index} className="tag">
                  <i className="bi bi-clock me-1"></i>{time}
                  <button
                    className="tag-remove"
                    onClick={() => handleRemoveTime(index)}
                  >
                    ×
                  </button>
                </div>
              ))}
              <button className="btn-add-tag" onClick={handleAddTime}>
                + Agregar horario
              </button>
            </div>
            <p className="field-hint">
              Horarios en los que tu audiencia está más activa
            </p>
          </div>
        </div>

        {/* Content Strategy */}
        <div className="strategy-section">
          <h3><i className="bi bi-palette me-2"></i>Pilares de Contenido</h3>

          <div className="form-group">
            <label>Temas principales:</label>
            <div className="tags-container">
              {settings.content_pillars.map((pillar, index) => (
                <div key={index} className="tag tag-pillar">
                  {pillar}
                  <button
                    className="tag-remove"
                    onClick={() => handleRemovePillar(index)}
                  >
                    ×
                  </button>
                </div>
              ))}
              <button className="btn-add-tag" onClick={handleAddPillar}>
                + Agregar pilar
              </button>
            </div>
            <p className="field-hint">
              Categorías de contenido que quieres cubrir regularmente
            </p>
          </div>
        </div>

        {/* Hashtag Strategy */}
        <div className="strategy-section">
          <h3><i className="bi bi-hash me-2"></i>Estrategia de Hashtags</h3>

          <div className="form-group">
            <label>Cantidad de hashtags:</label>
            <select
              value={settings.hashtag_strategy}
              onChange={(e) => setSettings({ ...settings, hashtag_strategy: e.target.value })}
            >
              <option value="minimal">Mínimos (3-5 hashtags)</option>
              <option value="moderate">Moderados (6-10 hashtags)</option>
              <option value="maximum">Máximos (11-15 hashtags)</option>
            </select>
          </div>

          <div className="info-box">
            <p>
              <i className="bi bi-lightbulb me-2"></i><strong>Tip:</strong> Los hashtags se generarán automáticamente según el
              contenido de cada post y esta configuración.
            </p>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="strategy-actions">
        <button
          className="btn-primary"
          onClick={handleSave}
          disabled={loading}
        >
          {loading ? <><i className="bi bi-arrow-repeat me-2"></i>Guardando...</> : <><i className="bi bi-save me-2"></i>Guardar Configuración</>}
        </button>
      </div>

      {/* Info Section */}
      <div className="strategy-info">
        <h4><i className="bi bi-info-circle me-2"></i>Acerca de esta configuración</h4>
        <p>
          Estas preferencias se aplicarán por defecto cuando generes nuevo contenido.
          Siempre podrás ajustar los parámetros individualmente para cada post.
        </p>
        <p>
          <strong>Próximamente:</strong> Análisis de engagement para optimizar automáticamente
          estos valores según el rendimiento de tus publicaciones.
        </p>
      </div>
    </div>
  );
};

export default StrategyConfig;
