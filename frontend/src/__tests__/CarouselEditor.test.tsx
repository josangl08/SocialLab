import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CarouselEditor, { countWords, getSlideWarning } from '../components/studio/CarouselEditor';
import type { CarouselSlide } from '../types';

describe('CarouselEditor Component', () => {
  const sampleSlides: CarouselSlide[] = [
    {
      index: 1,
      role: 'cover',
      text: '5 errores al programar posts',
      word_count: 5,
    },
    {
      index: 2,
      role: 'stake',
      text: 'Publicar sin estrategia te hace perder alcance y tiempo valioso cada semana.',
      word_count: 12,
    },
    {
      index: 3,
      role: 'idea',
      text: 'El primer error es no definir un gancho claro en los primeros segundos de tu contenido.',
      word_count: 16,
    },
    {
      index: 4,
      role: 'recap',
      text: 'Recuerda: planifica con antelación, revisa tus métricas y mantén consistencia.',
      word_count: 10,
    },
    {
      index: 5,
      role: 'cta',
      text: 'Guarda este carrusel para tu próxima sesión de contenido.',
      word_count: 9,
    },
  ];

  it('renders empty message when no slides are provided', () => {
    render(<CarouselEditor slides={[]} />);
    expect(screen.getByText(/no hay diapositivas para mostrar/i)).toBeInTheDocument();
  });

  it('renders first slide correctly with role and word count', () => {
    render(<CarouselEditor slides={sampleSlides} />);
    expect(screen.getByText(/editor de carrusel \(5 diapositivas\)/i)).toBeInTheDocument();
    expect(screen.getByText(/diapositiva 1 de 5/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue('5 errores al programar posts')).toBeInTheDocument();
    expect(screen.getByTestId('slide-word-count')).toHaveTextContent('5 palabras');
  });

  it('navigates through slides with Anterior / Siguiente buttons', () => {
    render(<CarouselEditor slides={sampleSlides} />);

    const prevBtn = screen.getByRole('button', { name: /slide anterior/i });
    const nextBtn = screen.getByRole('button', { name: /siguiente slide/i });

    expect(prevBtn).toBeDisabled();
    expect(nextBtn).not.toBeDisabled();

    // Click next -> Slide 2 (stake)
    fireEvent.click(nextBtn);
    expect(screen.getByText(/diapositiva 2 de 5/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue(sampleSlides[1].text)).toBeInTheDocument();
    expect(prevBtn).not.toBeDisabled();

    // Click next again -> Slide 3 (idea)
    fireEvent.click(nextBtn);
    expect(screen.getByText(/diapositiva 3 de 5/i)).toBeInTheDocument();

    // Click previous -> back to Slide 2
    fireEvent.click(prevBtn);
    expect(screen.getByText(/diapositiva 2 de 5/i)).toBeInTheDocument();
  });

  it('navigates directly by clicking slide chip', () => {
    render(<CarouselEditor slides={sampleSlides} />);

    const chip4 = screen.getByRole('tab', { name: /diapositiva 4/i });
    fireEvent.click(chip4);

    expect(screen.getByText(/diapositiva 4 de 5/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue(sampleSlides[3].text)).toBeInTheDocument();
  });

  it('shows warning when cover slide exceeds 6 words', () => {
    const slidesWithLongCover: CarouselSlide[] = [
      {
        index: 1,
        role: 'cover',
        text: 'Este es un título de portada demasiado largo para Instagram', // 10 words
        word_count: 10,
      },
    ];

    render(<CarouselEditor slides={slidesWithLongCover} />);
    const warning = screen.getByTestId('slide-warning');
    expect(warning).toHaveTextContent(/la portada no debería superar 6 palabras/i);
    expect(warning).toHaveTextContent(/actual: 10/i);
  });

  it('does not show warning when cover slide has 6 or fewer words', () => {
    render(<CarouselEditor slides={sampleSlides} />);
    expect(screen.queryByTestId('slide-warning')).not.toBeInTheDocument();
  });

  it('shows warning when idea slide exceeds 25 words', () => {
    const longIdeaText =
      'Esta es una idea extremadamente larga que contiene muchas explicaciones innecesarias y que termina superando con creces el límite máximo sugerido de veinticinco palabras para mantener alta retención en lectores.';
    const slidesWithLongIdea: CarouselSlide[] = [
      {
        index: 1,
        role: 'idea',
        text: longIdeaText, // 28 words
        word_count: 28,
      },
    ];

    render(<CarouselEditor slides={slidesWithLongIdea} />);
    const warning = screen.getByTestId('slide-warning');
    expect(warning).toHaveTextContent(/la idea principal no debería superar 25 palabras/i);
  });

  it('calls onSlidesChange when editing slide text', () => {
    const onSlidesChange = vi.fn();
    render(<CarouselEditor slides={sampleSlides} onSlidesChange={onSlidesChange} />);

    const textarea = screen.getByDisplayValue('5 errores al programar posts');
    fireEvent.change(textarea, { target: { value: 'Nuevo título portada' } });

    expect(onSlidesChange).toHaveBeenCalledTimes(1);
    const updatedSlides = onSlidesChange.mock.calls[0][0];
    expect(updatedSlides[0].text).toBe('Nuevo título portada');
    expect(updatedSlides[0].word_count).toBe(3);
  });

  it('renders and updates accompanying caption', () => {
    const onCaptionChange = vi.fn();
    render(
      <CarouselEditor
        slides={sampleSlides}
        caption="Caption inicial del carrusel"
        onCaptionChange={onCaptionChange}
      />
    );

    const captionArea = screen.getByDisplayValue('Caption inicial del carrusel');
    expect(captionArea).toBeInTheDocument();

    fireEvent.change(captionArea, { target: { value: 'Caption actualizado' } });
    expect(onCaptionChange).toHaveBeenCalledWith('Caption actualizado');
  });

  describe('helper functions', () => {
    it('countWords counts accurately with whitespace', () => {
      expect(countWords('')).toBe(0);
      expect(countWords('   ')).toBe(0);
      expect(countWords('palabra')).toBe(1);
      expect(countWords('  dos   palabras  ')).toBe(2);
    });

    it('getSlideWarning identifies violations', () => {
      expect(getSlideWarning({ index: 1, role: 'cover', text: 'uno dos tres cuatro cinco seis', word_count: 6 })).toBeNull();
      expect(getSlideWarning({ index: 1, role: 'cover', text: 'uno dos tres cuatro cinco seis siete', word_count: 7 })).not.toBeNull();
      expect(getSlideWarning({ index: 2, role: 'stake', text: 'uno dos tres cuatro cinco seis siete', word_count: 7 })).toBeNull();
    });
  });
});
