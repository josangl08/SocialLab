import React, { useState } from 'react';
import './TagInput.css';

interface TagInputProps {
  id: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  prefix?: string;
  max?: number;
  variant?: 'accent' | 'danger' | 'info';
  normalize?: (raw: string) => string;
  inputType?: 'text' | 'time';
}

/** Lista de etiquetas con campo para añadir (pilares, términos vetados, referentes, horarios). */
export const TagInput: React.FC<TagInputProps> = ({
  id, values, onChange, placeholder, prefix = '', max, variant = 'accent',
  normalize = raw => raw.trim(), inputType = 'text',
}) => {
  const [input, setInput] = useState('');
  const full = max !== undefined && values.length >= max;

  const add = () => {
    const value = normalize(input);
    if (value && !values.includes(value) && !full) onChange([...values, value]);
    setInput('');
  };

  return (
    <div className="sti">
      {values.length > 0 && (
        <div className="d-flex flex-wrap gap-2 mb-2">
          {values.map(v => (
            <span key={v} className={`sti-tag sti-tag--${variant}`}>
              {prefix}{v}
              <button type="button" className="sti-remove" aria-label={`Quitar ${v}`}
                onClick={() => onChange(values.filter(x => x !== v))}>×</button>
            </span>
          ))}
        </div>
      )}
      <div className="d-flex gap-2">
        <input
          id={id}
          type={inputType}
          className="form-control form-control-sm sti-input"
          value={input}
          disabled={full}
          placeholder={full ? `Máximo ${max}` : placeholder}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
        />
        <button type="button" className="btn btn-sm btn-outline-secondary flex-shrink-0" onClick={add}
          disabled={full} aria-label="Añadir">
          <i className="bi bi-plus" />
        </button>
      </div>
    </div>
  );
};
