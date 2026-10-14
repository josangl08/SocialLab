import React from 'react';
import { formatInZones, fromDatetimeLocalValue, zoneLabel } from '../../utils/timezone';
import './ScheduleZoneHint.css';

interface ScheduleZoneHintProps {
  /** Valor del input datetime-local, en hora de pared de `timezone` */
  value: string;
  timezone: string;
  secondaryTimezone?: string | null;
}

/** Indica en qué zona se lee un campo de fecha/hora y su equivalencia en la secundaria (AD-9). */
const ScheduleZoneHint: React.FC<ScheduleZoneHintProps> = ({ value, timezone, secondaryTimezone }) => {
  const showSecondary = Boolean(value && secondaryTimezone && secondaryTimezone !== timezone);
  return (
    <small className="szh-hint" data-testid="schedule-zone-hint">
      <i className="bi bi-globe2"></i> Hora de {zoneLabel(timezone)}
      {showSecondary && secondaryTimezone && (
        <span className="szh-secondary">
          {' '}= {formatInZones(fromDatetimeLocalValue(value, timezone), { primary: secondaryTimezone })}
        </span>
      )}
    </small>
  );
};

export default ScheduleZoneHint;
