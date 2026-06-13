import React, { useState } from 'react';

interface HybridSelectProps {
  options: string[];
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  accentColor?: string;
  accentBg?: string;
}

export const HybridSelect: React.FC<HybridSelectProps> = ({
  options,
  value,
  onChange,
  placeholder = 'Añadir opción...',
  accentColor = '#818cf8',
  accentBg = 'rgba(99,102,241,0.14)',
}) => {
  const [input, setInput] = useState('');

  const toggle = (opt: string) => {
    onChange(value.includes(opt) ? value.filter(v => v !== opt) : [...value, opt]);
  };

  const addCustom = () => {
    const t = input.trim();
    if (t && !value.includes(t)) { onChange([...value, t]); }
    setInput('');
  };

  const isSelected = (opt: string) => value.includes(opt);
  const isCustom = (opt: string) => !options.includes(opt) && value.includes(opt);

  return (
    <div>
      <div className="d-flex flex-wrap gap-2 mb-2">
        {options.map(opt => (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            style={{
              border: isSelected(opt) ? `1.5px solid ${accentColor}` : '1px solid rgba(255,255,255,0.1)',
              borderRadius: 20,
              padding: '4px 12px',
              fontSize: '0.78rem',
              fontWeight: isSelected(opt) ? 600 : 400,
              backgroundColor: isSelected(opt) ? accentBg : 'rgba(255,255,255,0.03)',
              color: isSelected(opt) ? accentColor : 'rgba(255,255,255,0.55)',
              cursor: 'pointer',
              transition: 'all 0.13s',
            }}
          >
            {isSelected(opt) && <i className="bi bi-check2 me-1" style={{ fontSize: '0.72rem' }} />}
            {opt}
          </button>
        ))}

        {value.filter(isCustom).map(opt => (
          <span
            key={opt}
            style={{
              border: `1.5px solid ${accentColor}`,
              borderRadius: 20,
              padding: '4px 10px',
              fontSize: '0.78rem',
              fontWeight: 600,
              backgroundColor: accentBg,
              color: accentColor,
              display: 'flex', alignItems: 'center', gap: 5,
            }}
          >
            <i className="bi bi-check2" style={{ fontSize: '0.72rem' }} />
            {opt}
            <button
              type="button"
              onClick={() => toggle(opt)}
              style={{ background: 'none', border: 'none', color: accentColor, padding: 0, cursor: 'pointer', lineHeight: 1, fontSize: '1rem', opacity: 0.6 }}
            >×</button>
          </span>
        ))}
      </div>

      <div className="d-flex gap-2 mt-1">
        <input
          className="form-control form-control-sm"
          style={{ backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', borderRadius: 8, fontSize: '0.8rem' }}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addCustom())}
          placeholder={placeholder}
        />
        <button
          type="button"
          className="btn btn-sm btn-outline-secondary"
          onClick={addCustom}
          style={{ flexShrink: 0 }}
        >
          <i className="bi bi-plus" />
        </button>
      </div>
    </div>
  );
};

export default HybridSelect;
