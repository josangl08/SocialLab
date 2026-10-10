import React from 'react';
import type { BeatItemOutput } from '../../types';
import './BeatSheet.css';

export interface BeatSheetProps {
  beats: BeatItemOutput[];
  totalSeconds?: number;
  loopsToHook?: boolean;
}

export const BeatSheet: React.FC<BeatSheetProps> = ({
  beats,
  totalSeconds,
  loopsToHook,
}) => {
  if (!beats || beats.length === 0) {
    return null;
  }

  return (
    <div className="beat-sheet mt-3 p-3 rounded border border-secondary bg-dark bg-opacity-50">
      <div className="d-flex justify-content-between align-items-center mb-2">
        <h6 className="m-0 text-light small fw-bold">
          <i className="bi bi-stopwatch me-1 text-primary"></i>Beat Sheet (Guion de Reel)
        </h6>
        <div className="d-flex align-items-center gap-2">
          {totalSeconds !== undefined && (
            <span className="badge bg-secondary">
              Total: {totalSeconds.toFixed(1)}s
            </span>
          )}
          {loopsToHook && (
            <span className="badge bg-success-subtle text-success border border-success">
              <i className="bi bi-arrow-repeat me-1"></i>Loop perfecto
            </span>
          )}
        </div>
      </div>

      <div className="table-responsive">
        <table className="table table-sm table-dark table-borderless m-0 small align-middle">
          <thead>
            <tr className="text-secondary border-bottom border-secondary">
              <th>Tiempo</th>
              <th>Duración</th>
              <th>Beat</th>
              <th>Texto</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {beats.map((beat, idx) => {
              const isOver4 = beat.alert === 'OVER_4S' || beat.duration_s > 4;
              return (
                <tr key={idx} className="border-bottom border-dark">
                  <td className="beat-sheet-time text-secondary font-monospace">
                    {beat.start_s.toFixed(1)}s - {beat.end_s.toFixed(1)}s
                  </td>
                  <td className="beat-sheet-time font-monospace">
                    {beat.duration_s.toFixed(1)}s
                  </td>
                  <td>
                    <span className="badge bg-secondary-subtle text-light">
                      {beat.label}
                    </span>
                  </td>
                  <td className="text-light">{beat.text || '—'}</td>
                  <td className="text-end">
                    {isOver4 && (
                      <span className="badge bg-danger text-white">
                        OVER_4S
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default BeatSheet;
