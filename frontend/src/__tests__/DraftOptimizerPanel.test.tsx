import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import DraftOptimizerPanel from '../components/analytics/panels/DraftOptimizerPanel';

describe('DraftOptimizerPanel Component', () => {
  const mockBestPostingTimesRaw = [
    { hour: '15:00', day_of_week: 1, score: 80, online_followers: 200, avg_engagement: 35.5, posts_count: 5 },
    { hour: '19:00', day_of_week: 2, score: 95, online_followers: 350, avg_engagement: 48.2, posts_count: 8 }
  ];

  const mockByContentType = {
    'IMAGE': { count: 3, total_likes: 30, total_comments: 6, total_engagement: 36, avg_engagement: 12.0, type_name: 'Imágenes' },
    'REELS': { count: 12, total_likes: 240, total_comments: 60, total_engagement: 300, avg_engagement: 25.0, type_name: 'Reels' }
  };

  test('renders with calculated slot and format', () => {
    render(
      <DraftOptimizerPanel 
        bestPostingTimesRaw={mockBestPostingTimesRaw} 
        byContentType={mockByContentType} 
      />
    );

    // Should display the optimal day (day_of_week: 2 is Miércoles)
    expect(screen.getByText('Miércoles a las 19:00')).toBeInTheDocument();
    
    // Should display the most common format (Reels has count 12 vs Image count 3)
    expect(screen.getByText('Reels')).toBeInTheDocument();

    // Should display estimated engagement delta
    expect(screen.getByText('+48% de incremento')).toBeInTheDocument();
  });

  test('collapses and expands on click', () => {
    render(
      <DraftOptimizerPanel 
        bestPostingTimesRaw={mockBestPostingTimesRaw} 
        byContentType={mockByContentType} 
      />
    );

    // Initial state: expanded
    expect(screen.getByText('Horario Recomendado')).toBeInTheDocument();

    // Click header to collapse
    const header = screen.getByRole('button');
    fireEvent.click(header);

    // Body details should no longer be visible
    expect(screen.queryByText('Horario Recomendado')).not.toBeInTheDocument();

    // Click again to expand
    fireEvent.click(header);
    expect(screen.getByText('Horario Recomendado')).toBeInTheDocument();
  });
});
