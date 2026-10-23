import React, { useEffect } from 'react';
import type { LoginType } from '../../types';
import { LOGIN_FOOTNOTE, LOGIN_METHODS } from './loginMethods';
import './LoginMethodModal.css';

interface LoginMethodModalProps {
  /** Login actual de la cuenta al cambiarlo; undefined al conectar una cuenta nueva. */
  current?: LoginType;
  onChoose: (method: LoginType) => void;
  onClose: () => void;
}

export const LoginMethodModal: React.FC<LoginMethodModalProps> = ({ current, onChoose, onClose }) => {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <>
      <div className="lm-backdrop" onClick={onClose} />
      <div className="lm-dialog" role="dialog" aria-modal="true" aria-labelledby="lm-title">
        <div className="lm-header">
          <h4 id="lm-title" className="lm-title">
            {current ? 'Cambiar el tipo de conexión' : '¿Cómo quieres conectar la cuenta?'}
          </h4>
          <button className="lm-close" onClick={onClose} aria-label="Cerrar">×</button>
        </div>

        <div className="lm-options">
          {Object.values(LOGIN_METHODS).map(method => (
            <section key={method.type} className={`lm-option lm-option-${method.type}`} aria-label={method.name}>
              <div className="lm-option-head">
                <i className={`bi ${method.icon} lm-option-icon`}></i>
                <span className="lm-option-name">{method.name}</span>
                {method.type === current
                  ? <span className="lm-tag lm-tag-current">Actual</span>
                  : <span className="lm-tag">{method.tagline}</span>}
              </div>

              <ul className="lm-features">
                {method.features.map(feature => (
                  <li key={feature.label} className={feature.available ? 'lm-yes' : 'lm-no'}>
                    <i className={`bi ${feature.available ? 'bi-check-lg' : 'bi-x-lg'}`} aria-hidden="true"></i>
                    <span>{feature.label}</span>
                  </li>
                ))}
              </ul>

              <div className="lm-requirements">
                <span className="lm-requirements-title">Necesitas</span>
                <ul>
                  {method.requirements.map(req => <li key={req}>{req}</li>)}
                </ul>
              </div>

              <button
                className="st-btn st-btn-primary st-btn-sm lm-connect"
                onClick={() => onChoose(method.type)}
              >
                <i className={`bi ${method.icon}`}></i>Conectar con {method.name}
              </button>
            </section>
          ))}
        </div>

        <p className="lm-footnote">
          {LOGIN_FOOTNOTE}
          {current && ' Cambiar de conexión conserva tus posts, métricas y configuración.'}
        </p>
      </div>
    </>
  );
};
