import React from 'react';
import KPICard from './KPICard';

interface KPIStripProps {
  cards: Array<React.ComponentProps<typeof KPICard>>;
}

export const KPIStrip: React.FC<KPIStripProps> = ({ cards }) => {
  return (
    <div className="an-kpi-strip">
      {cards.map((cardProps, index) => (
        <KPICard key={index} {...cardProps} />
      ))}
    </div>
  );
};

export default KPIStrip;
