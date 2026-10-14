import React, { useEffect, useState } from 'react';
import type { InstagramAccount } from '../../types';
import { browserTimezone } from '../../utils/timezone';
import { apiClient, ApiError } from '../../api/client';
import './AccountTimezoneSettings.css';

export interface AccountTimezoneSettingsProps {
  account: InstagramAccount;
  onUpdate?: (updated: Partial<InstagramAccount>) => void;
}

export const AccountTimezoneSettings: React.FC<AccountTimezoneSettingsProps> = ({
  account,
  onUpdate,
}) => {
  const browserTz = browserTimezone();
  const [primary, setPrimary] = useState<string>(account.primary_timezone || '');
  const [secondary, setSecondary] = useState<string>(account.secondary_timezone || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Zonas IANA soportadas por el entorno
  const supportedZones: string[] = typeof Intl !== 'undefined' && typeof Intl.supportedValuesOf === 'function'
    ? Intl.supportedValuesOf('timeZone')
    : [];

  // Mantiene los inputs al día si la cuenta cambia desde fuera (p. ej. recarga de la lista)
  useEffect(() => {
    setPrimary(account.primary_timezone || '');
    setSecondary(account.secondary_timezone || '');
  }, [account.primary_timezone, account.secondary_timezone]);

  const saveZones = async (primaryTz: string | null, secondaryTz: string | null) => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const payload = { primary_timezone: primaryTz, secondary_timezone: secondaryTz };
      await apiClient.put(`/instagram/accounts/${account.id}/config`, payload);
      setPrimary(primaryTz ?? '');
      setSecondary(secondaryTz ?? '');
      setSuccess(true);
      onUpdate?.(payload);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Error al guardar la zona horaria');
    } finally {
      setSaving(false);
    }
  };

  const handleSave = () => saveZones(primary.trim() || null, secondary.trim() || null);
  const handleReset = () => saveZones(null, null);

  const datalistId = `tz-datalist-${account.id}`;

  return (
    <div className="account-tz-settings" data-testid="account-tz-settings">
      <div className="account-tz-settings__title">
        <i className="bi bi-clock"></i> Zona horaria
      </div>

      <datalist id={datalistId}>
        {supportedZones.map(tz => (
          <option key={tz} value={tz} />
        ))}
      </datalist>

      <div className="account-tz-settings__grid">
        <div className="account-tz-settings__field">
          <label htmlFor={`tz-primary-${account.id}`} className="account-tz-settings__label">
            Zona principal
          </label>
          <input
            id={`tz-primary-${account.id}`}
            type="text"
            list={datalistId}
            className="account-tz-settings__input"
            value={primary}
            onChange={e => setPrimary(e.target.value)}
            placeholder={`Navegador (${browserTz})`}
            data-testid="input-primary-tz"
          />
          <span className="account-tz-settings__hint">
            Por defecto: Navegador ({browserTz})
          </span>
        </div>

        <div className="account-tz-settings__field">
          <label htmlFor={`tz-secondary-${account.id}`} className="account-tz-settings__label">
            Zona secundaria (opcional)
          </label>
          <input
            id={`tz-secondary-${account.id}`}
            type="text"
            list={datalistId}
            className="account-tz-settings__input"
            value={secondary}
            onChange={e => setSecondary(e.target.value)}
            placeholder="Ninguna"
            data-testid="input-secondary-tz"
          />
          <span className="account-tz-settings__hint">
            Informativa, solo lectura
          </span>
        </div>
      </div>

      {error && (
        <div className="account-tz-settings__error" role="alert" data-testid="tz-error-msg">
          <i className="bi bi-exclamation-triangle"></i> {error}
        </div>
      )}

      {success && (
        <div className="account-tz-settings__success" role="status" data-testid="tz-success-msg">
          <i className="bi bi-check-circle"></i> Configuración guardada
        </div>
      )}

      <div className="account-tz-settings__actions">
        <button
          type="button"
          className="account-tz-settings__btn account-tz-settings__btn-reset"
          onClick={handleReset}
          disabled={saving}
          data-testid="btn-reset-tz"
        >
          Restablecer
        </button>
        <button
          type="button"
          className="account-tz-settings__btn account-tz-settings__btn-save"
          onClick={handleSave}
          disabled={saving}
          data-testid="btn-save-tz"
        >
          {saving ? 'Guardando...' : 'Guardar zona'}
        </button>
      </div>
    </div>
  );
};
