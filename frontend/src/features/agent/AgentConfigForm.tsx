import React, { useState } from 'react';
import { apiClient, ApiError } from '../../api/client';

interface AgentConfig {
  account_type: 'personal' | 'professional';
  sector: string;
  purpose: string;
  target_audience: string;
  style_guide: string;
}

interface AgentConfigFormProps {
  accountId: number;
  initialConfig?: Partial<AgentConfig>;
  onSave?: () => void;
}

export const AgentConfigForm: React.FC<AgentConfigFormProps> = ({
  accountId,
  initialConfig,
  onSave
}) => {
  const [accountType, setAccountType] = useState<'personal' | 'professional'>(
    (initialConfig?.account_type as 'personal' | 'professional') || 'personal'
  );
  const [sector, setSector] = useState(initialConfig?.sector || '');
  const [purpose, setPurpose] = useState(initialConfig?.purpose || '');
  const [targetAudience, setTargetAudience] = useState(initialConfig?.target_audience || '');
  const [styleGuide, setStyleGuide] = useState(initialConfig?.style_guide || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(false);

    const token = localStorage.getItem('authToken');
    if (!token) {
      setError('No autenticado');
      setSaving(false);
      return;
    }

    try {
      await apiClient.put(`/api/agent/config/${accountId}`, {
        account_type: accountType,
        sector,
        purpose,
        target_audience: targetAudience,
        style_guide: styleGuide
      });

      setSuccess(true);
      if (onSave) {
        onSave();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Error al actualizar configuración');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="mt-3" data-testid="agent-config-form">
      <h5 className="mb-3 fw-bold"><i className="bi bi-robot me-2"></i>Estrategia del Agente</h5>
      
      {error && <div className="alert alert-danger p-2 small">{error}</div>}
      {success && <div className="alert alert-success p-2 small">Estrategia guardada correctamente</div>}

      <div className="mb-3">
        <label className="form-label small fw-bold">Tipo de Cuenta</label>
        <div className="d-flex gap-3">
          <div className="form-check">
            <input
              type="radio"
              id={`personal-${accountId}`}
              name={`accountType-${accountId}`}
              className="form-check-input"
              value="personal"
              checked={accountType === 'personal'}
              onChange={() => setAccountType('personal')}
            />
            <label className="form-check-label small" htmlFor={`personal-${accountId}`}>Personal</label>
          </div>
          <div className="form-check">
            <input
              type="radio"
              id={`professional-${accountId}`}
              name={`accountType-${accountId}`}
              className="form-check-input"
              value="professional"
              checked={accountType === 'professional'}
              onChange={() => setAccountType('professional')}
            />
            <label className="form-check-label small" htmlFor={`professional-${accountId}`}>Profesional</label>
          </div>
        </div>
      </div>

      <div className="mb-3">
        <label htmlFor={`sector-${accountId}`} className="form-label small fw-bold">Sector / Nicho</label>
        <input
          type="text"
          id={`sector-${accountId}`}
          className="form-control form-control-sm bg-dark text-white border-secondary"
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          placeholder="Ej: Deporte, Fitness, Moda, Tecnología"
        />
      </div>

      <div className="mb-3">
        <label htmlFor={`purpose-${accountId}`} className="form-label small fw-bold">Objetivo Principal</label>
        <input
          type="text"
          id={`purpose-${accountId}`}
          className="form-control form-control-sm bg-dark text-white border-secondary"
          value={purpose}
          onChange={(e) => setPurpose(e.target.value)}
          placeholder="Ej: Captación de clientes, Branding, Ventas"
        />
      </div>

      <div className="mb-3">
        <label htmlFor={`target-${accountId}`} className="form-label small fw-bold">Audiencia Objetivo</label>
        <input
          type="text"
          id={`target-${accountId}`}
          className="form-control form-control-sm bg-dark text-white border-secondary"
          value={targetAudience}
          onChange={(e) => setTargetAudience(e.target.value)}
          placeholder="Ej: Jóvenes deportistas, Emprendedores"
        />
      </div>

      <div className="mb-3">
        <label htmlFor={`style-${accountId}`} className="form-label small fw-bold">Guía de Estilo</label>
        <textarea
          id={`style-${accountId}`}
          rows={3}
          className="form-control form-control-sm bg-dark text-white border-secondary"
          value={styleGuide}
          onChange={(e) => setStyleGuide(e.target.value)}
          placeholder="Ej: Tono técnico e inspirador, emojis con moderación..."
        />
      </div>

      <button type="submit" className="btn btn-sm btn-primary w-100" disabled={saving}>
        {saving ? <span className="spinner-border spinner-border-sm" role="status"></span> : 'Guardar Estrategia'}
      </button>
    </form>
  );
};

export default AgentConfigForm;
