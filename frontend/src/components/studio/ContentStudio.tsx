import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { apiClient, ApiError } from '../../api/client';
import type { InstagramAccount, ContentFormat, StrategyMode, ReelOut, CarouselSlide, ContentStructure } from '../../types';
import { getFirstOfDayOfMonth } from '../../utils/campaign';
import type { MonthlyCampaign } from '../../types';
import SourceSelector, { type ContentSource } from './SourceSelector';
import SportsExportSelector, { type SportsExportResult } from './SportsExportSelector';
import FormatEditor, { type SavePostPayload } from './FormatEditor';
import QualityInspector from './QualityInspector';
import RepurposePanel, { type RepurposePiece } from './RepurposePanel';
import CarouselEditor from './CarouselEditor';
import IdeaGenerator from './IdeaGenerator';
import ProspectComments from './ProspectComments';
import { accountZones, browserTimezone, toDatetimeLocalValue } from '../../utils/timezone';
import './ContentStudio.css';

export interface ContentStudioProps {
  onPostGenerated?: () => void;
}

export const ContentStudio: React.FC<ContentStudioProps> = ({ onPostGenerated }) => {
  const { token } = useAuth();
  const [searchParams] = useSearchParams();

  // Origen y formato
  const [source, setSource] = useState<ContentSource>('idea');
  const [format, setFormat] = useState<Exclude<ContentFormat, 'story'>>('post');
  const [strategyMode, setStrategyMode] = useState<StrategyMode>('personal_storyline');

  // Cuentas de Instagram
  const [accounts, setAccounts] = useState<InstagramAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');

  // Draft state
  const [caption, setCaption] = useState<string>('');
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [mediaUrl, setMediaUrl] = useState<string | null>(null);
  // Estructura de la pieza generada abierta en el editor
  const [reel, setReel] = useState<ReelOut | null>(null);
  const [slides, setSlides] = useState<CarouselSlide[] | null>(null);

  // Fecha precargada de query ?date=
  const [scheduledAt, setScheduledAt] = useState<string>(() => {
    const rawDate = searchParams.get('date');
    if (!rawDate) return '';
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(rawDate)) {
      return rawDate;
    }
    const parsed = new Date(rawDate);
    if (isNaN(parsed.getTime())) return '';
    return toDatetimeLocalValue(parsed, browserTimezone());
  });

  const [loading, setLoading] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Cargar cuentas
  useEffect(() => {
    if (!token) return;
    apiClient
      .get<InstagramAccount[]>('/instagram/accounts')
      .then((data) => {
        setAccounts(data || []);
        if (data && data.length > 0) {
          setSelectedAccountId((curr) => curr || String(data[0].id));
          // El instante de ?date= se muestra en la zona de la cuenta (AD-9)
          const rawDate = searchParams.get('date');
          const parsed = rawDate ? new Date(rawDate) : null;
          if (rawDate && parsed && !isNaN(parsed.getTime()) && !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(rawDate)) {
            setScheduledAt(toDatetimeLocalValue(parsed, accountZones(data, data[0].id).primary));
          }
        }
      })
      .catch(() => {});
  }, [token]);

  const selectedAccount = accounts.find((acc) => String(acc.id) === selectedAccountId);
  const selectedZones = accountZones(accounts, selectedAccount?.id);
  // `sector` es texto libre ("Contenido Visual Deportivo y Viajes"): se compara sin acentos por raíz
  const normalizedSector = (selectedAccount?.sector ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
  const isSportsSector = normalizedSector.includes('deport') || normalizedSector.includes('sport');
  const hasTelegram = Boolean(selectedAccount?.telegram_chat_id);

  // Estrategia por defecto = la de la campaña del mes; sin campaña → personal (AD-2)
  useEffect(() => {
    if (!selectedAccountId) {
      setStrategyMode('personal_storyline');
      return;
    }
    const monthDate = getFirstOfDayOfMonth(new Date());
    apiClient
      .get<MonthlyCampaign | null>(`/api/agent/campaign?account_id=${selectedAccountId}&month_date=${monthDate}`)
      .then((campaign) => setStrategyMode(campaign?.strategy_mode ?? 'personal_storyline'))
      .catch(() => setStrategyMode('personal_storyline'));
  }, [selectedAccountId]);

  // Si cambia de cuenta y no es deportes, resetea origen deportivo
  useEffect(() => {
    if (!isSportsSector && source === 'sports') {
      setSource('idea');
    }
  }, [isSportsSector, source]);

  const handleSportsGenerated = (result: SportsExportResult) => {
    setCaption(result.caption);
    setMediaUrl(result.mediaUrl);
    setMediaFile(null);
    setFeedback({
      message: 'Estadísticas deportivas convertidas en publicación.',
      type: 'success',
    });
  };

  const handleOpenPiece = (piece: RepurposePiece) => {
    if (piece.kind === 'reel') {
      setFormat('reel');
      setCaption(piece.reel.caption);
      setReel(piece.reel);
      setSlides(null);
    } else {
      setFormat('carousel');
      setCaption(piece.carousel.caption);
      setSlides(piece.carousel.slides);
      setReel(null);
    }
  };

  // Elegir otro gancho sustituye la primera línea del caption
  const handleChooseHook = (hookText: string) => {
    const lines = caption.split('\n');
    lines[0] = hookText;
    setCaption(lines.join('\n'));
  };

  const handleSavePost = async (payload: SavePostPayload) => {
    setLoading(true);
    setFeedback(null);

    try {
      const formData = new FormData();
      formData.append('content', caption);
      formData.append('post_type', format);
      formData.append('status', payload.status);
      formData.append('notify_telegram', String(payload.notifyTelegram));
      formData.append('content_format', format);
      if (format === 'reel' && payload.trialGraduation) {
        formData.append('trial_graduation', payload.trialGraduation);
      }
      const structure: ContentStructure | null =
        format === 'carousel' && slides
          ? { slides }
          : format === 'reel' && reel
          ? { hooks: reel.hooks, beats: reel.beats, on_screen_text: reel.on_screen_text }
          : null;
      if (structure) {
        formData.append('content_structure', JSON.stringify(structure));
      }

      if (payload.scheduledAt) {
        formData.append('scheduled_at', payload.scheduledAt);
      }
      if (selectedAccountId) {
        formData.append('instagram_account_id', selectedAccountId);
      }

      // Archivo del usuario o imagen de P1 (data URL o URL pública de Storage)
      if (mediaFile) {
        formData.append('media_file', mediaFile, mediaFile.name);
      } else if (mediaUrl) {
        const blob = await (await fetch(mediaUrl)).blob();
        formData.append('media_file', blob, 'media.png');
      }

      await apiClient.postForm('/api/posts', formData);

      const msg =
        payload.status === 'scheduled'
          ? 'Publicación programada exitosamente.'
          : payload.notifyTelegram
          ? 'Borrador enviado a revisión en Telegram.'
          : 'Borrador guardado correctamente.';

      setFeedback({ message: msg, type: 'success' });
      onPostGenerated?.();
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Error al guardar la publicación.';
      setFeedback({ message: detail, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="content-studio container-fluid py-4 px-lg-5">
      {/* Header con título y toggle de estrategia */}
      <div className="d-flex flex-wrap justify-content-between align-items-center mb-4 gap-3">
        <div>
          <h2 className="m-0 text-light fw-bold">
            <i className="bi bi-palette2 me-2 text-primary"></i>Content Studio
          </h2>
          <p className="text-secondary small m-0">
            Creación, edición y control determinista de calidad de publicaciones
          </p>
        </div>

        <div className="d-flex align-items-center gap-3">
          {/* Selector de cuenta */}
          {accounts.length > 0 && (
            <div className="account-picker d-flex align-items-center gap-2">
              <label htmlFor="instagram-account-select" className="text-secondary small m-0 text-nowrap">
                Cuenta de Instagram:
              </label>
              <select
                id="instagram-account-select"
                className="form-select form-select-sm bg-dark text-light border-secondary"
                value={selectedAccountId}
                onChange={(e) => setSelectedAccountId(e.target.value)}
              >
                <option value="">Sin cuenta específica</option>
                {accounts.map((acc) => (
                  <option key={acc.id} value={String(acc.id)}>
                    @{acc.username ?? acc.account_name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Toggle de Estrategia */}
          <div className="strategy-toggle-wrap d-flex align-items-center gap-2">
            <span className="text-secondary small">Estrategia:</span>
            <button
              type="button"
              className={`btn btn-sm ${
                strategyMode === 'commercial_campaign'
                  ? 'btn-outline-primary'
                  : 'btn-outline-secondary'
              }`}
              onClick={() =>
                setStrategyMode((curr) =>
                  curr === 'commercial_campaign' ? 'personal_storyline' : 'commercial_campaign'
                )
              }
              title="Cambiar estrategia para esta sesión"
            >
              <i
                className={`bi me-1 ${
                  strategyMode === 'commercial_campaign' ? 'bi-briefcase' : 'bi-person-heart'
                }`}
              ></i>
              {strategyMode === 'commercial_campaign' ? 'Campaña comercial' : 'Historia personal'}
            </button>
          </div>
        </div>
      </div>

      {/* Banner de feedback */}
      {feedback && (
        <div
          className={`alert ${
            feedback.type === 'success' ? 'alert-success' : 'alert-danger'
          } alert-dismissible fade show mb-4`}
          role="alert"
        >
          <i
            className={`bi ${
              feedback.type === 'success' ? 'bi-check-circle' : 'bi-exclamation-triangle'
            } me-2`}
          ></i>
          {feedback.message}
          <button
            type="button"
            className="btn-close"
            onClick={() => setFeedback(null)}
            aria-label="Cerrar"
          ></button>
        </div>
      )}

      {/* Grid de 2 columnas */}
      <div className="row g-4">
        {/* Columna Izquierda: Origen + Editor */}
        <div className="col-lg-7">
          <SourceSelector
            source={source}
            onSelectSource={setSource}
            isSportsSector={isSportsSector}
          />

          {source === 'sports' && isSportsSector && (
            <SportsExportSelector
              accountId={selectedAccountId ? Number(selectedAccountId) : null}
              onPostGenerated={handleSportsGenerated}
              onCancel={() => setSource('idea')}
            />
          )}

          {source === 'repurpose' && (
            <RepurposePanel
              accountId={selectedAccountId ? Number(selectedAccountId) : null}
              strategyMode={strategyMode}
              onOpenPiece={handleOpenPiece}
            />
          )}

          {source === 'idea' && format !== 'post' && (
            <IdeaGenerator
              accountId={selectedAccountId ? Number(selectedAccountId) : null}
              format={format}
              strategyMode={strategyMode}
              onGenerated={handleOpenPiece}
            />
          )}

          {format === 'reel' && reel && reel.hooks.length > 0 && (
            <div className="studio-hook-candidates mb-3" role="group" aria-label="Ganchos candidatos">
              <label className="form-label text-secondary small d-block">
                <i className="bi bi-lightning-charge me-1 text-warning"></i>Ganchos candidatos
              </label>
              {reel.hooks.map((hook, idx) => (
                <button
                  key={idx}
                  type="button"
                  className={`studio-hook-btn ${caption.split('\n')[0] === hook.text ? 'active' : ''}`}
                  onClick={() => handleChooseHook(hook.text)}
                >
                  <span className="badge bg-secondary me-2">{hook.score}</span>
                  {hook.text}
                </button>
              ))}
            </div>
          )}

          {format === 'carousel' && slides && (
            <div className="mb-3">
              <CarouselEditor slides={slides} onSlidesChange={setSlides} />
            </div>
          )}

          <FormatEditor
            format={format}
            onFormatChange={setFormat}
            caption={caption}
            onCaptionChange={setCaption}
            mediaFile={mediaFile}
            onMediaFileChange={setMediaFile}
            mediaUrl={mediaUrl}
            scheduledAt={scheduledAt}
            onScheduledAtChange={setScheduledAt}
            timezone={selectedZones.primary}
            secondaryTimezone={selectedZones.secondary}
            strategyMode={strategyMode}
            hasTelegram={hasTelegram}
            onSave={handleSavePost}
            loading={loading}
          />
        </div>

        {/* Columna Derecha: Inspector de Calidad */}
        <div className="col-lg-5">
          <QualityInspector
            caption={caption}
            format={format}
            beats={reel?.beats.beats}
            beatsTotalSeconds={reel?.beats.total_s}
            beatsLoopsToHook={reel?.beats.loops_to_hook}
          />
          <ProspectComments
            accountId={selectedAccountId ? Number(selectedAccountId) : null}
            strategyMode={strategyMode}
          />
        </div>
      </div>
    </div>
  );
};

export default ContentStudio;
