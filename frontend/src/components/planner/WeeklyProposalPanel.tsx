import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';
import { apiClient, ApiError } from '../../api/client';
import type { ContentProposal, CalendarSlot, InstagramAccount } from '../../types';
import './WeeklyProposalPanel.css';

interface WeeklyProposalPanelProps {
  accountId: number | null;
  refreshSignal: number;
  onProposalAction: () => void;
  onProposalsFound?: () => void;
  focusPostId?: number | null;
  onFocusHandled?: () => void;
}

interface DriveImage {
  id: string;
  name: string;
}

type SlotActionKey = string;

const POST_TYPE_LABELS: Record<string, string> = {
  reel: 'Reel',
  carousel: 'Carousel',
  story: 'Story',
  post: 'Post',
};

const MATRIX_ROLE_LABELS: Record<string, string> = {
  proof: 'Proof',
  teach: 'Teach',
  opinion: 'Opinion',
  offer: 'Offer',
  // 'Story' a secas se confunde con el formato Story
  story: 'Storytelling',
  learning: 'Learning',
  reflection: 'Reflection',
};

// Foto adjuntada por Telegram (Storage) o imagen de Drive
function slotImageSrc(slot: CalendarSlot, token: string | null): string | null {
  if (slot.media_url) return slot.media_url;
  if (slot.image_id) return apiClient.getUrl(`/api/drive/files/${slot.image_id}/image?token=${token}`);
  return null;
}

function slotBadgeLabel(slot: CalendarSlot): string {
  const ptype = slot.post_type ?? 'post';
  const typeLabel = POST_TYPE_LABELS[ptype] ?? ptype;
  const role = slot.matrix_role;
  return role ? `${MATRIX_ROLE_LABELS[role] ?? role} · ${typeLabel}` : typeLabel;
}

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const WEEKDAY_LABELS: Record<string, string> = {
  Monday: 'Mon', Tuesday: 'Tue', Wednesday: 'Wed',
  Thursday: 'Thu', Friday: 'Fri', Saturday: 'Sat', Sunday: 'Sun',
};

function getDayNumber(weekStart: string, dayName: string): number {
  const base = new Date(weekStart + 'T12:00:00');
  base.setDate(base.getDate() + WEEKDAYS.indexOf(dayName));
  return base.getDate();
}

function getDefaultDatetime(weekStart: string, dayName: string): string {
  const base = new Date(weekStart + 'T09:00:00');
  base.setDate(base.getDate() + WEEKDAYS.indexOf(dayName));
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${base.getFullYear()}-${pad(base.getMonth() + 1)}-${pad(base.getDate())}T09:00`;
}

const WeeklyProposalPanel: React.FC<WeeklyProposalPanelProps> = ({
  accountId,
  refreshSignal,
  onProposalAction,
  onProposalsFound,
  focusPostId,
  onFocusHandled,
}) => {
  const { token } = useAuth();
  const [proposals, setProposals] = useState<ContentProposal[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<Record<SlotActionKey, boolean>>({});
  const [slotCaptions, setSlotCaptions] = useState<Record<SlotActionKey, string>>({});
  const [typeMenuOpen, setTypeMenuOpen] = useState<SlotActionKey | null>(null);
  const [activeSlot, setActiveSlot] = useState<string | null>(null);
  const [slotTimes, setSlotTimes] = useState<Record<SlotActionKey, string>>({});
  const [imagePicking, setImagePicking] = useState<string | null>(null);
  const [driveImages, setDriveImages] = useState<DriveImage[]>([]);
  const [imagePickLoading, setImagePickLoading] = useState(false);
  const [dragging, setDragging] = useState<{ proposalId: string; day: string } | null>(null);
  const [dragOverKey, setDragOverKey] = useState<string | null>(null);
  const prevCountRef = useRef<number>(0);
  const hasLoaded = useRef(false);
  const activeSlotRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!token || accountId === null) return;
    const fetchProposals = async () => {
      if (!hasLoaded.current) setLoading(true);
      setError(null);
      try {
        if (!accountId) {
          const accounts = await apiClient.get<InstagramAccount[]>('/instagram/accounts');
          const fetches = accounts.map((acc) =>
            apiClient.get<ContentProposal[]>(`/api/agent/proposals?account_id=${acc.id}`).catch(() => [])
          );
          const arrays = await Promise.all(fetches);
          setProposals(arrays.flat().filter(p => p.status === 'pending_approval'));
        } else {
          const data = await apiClient.get<ContentProposal[]>(`/api/agent/proposals?account_id=${accountId}`);
          setProposals(data.filter(p => p.status === 'pending_approval'));
        }
      } catch (err: unknown) {
        setError(err instanceof ApiError ? err.detail : 'Error desconocido');
      } finally {
        hasLoaded.current = true;
        setLoading(false);
      }
    };
    fetchProposals();
  }, [token, accountId, refreshSignal]);

  useEffect(() => {
    if (proposals.length > prevCountRef.current) onProposalsFound?.();
    prevCountRef.current = proposals.length;
  }, [proposals.length, onProposalsFound]);

  useEffect(() => {
    if (!focusPostId) return;
    for (const proposal of proposals) {
      const slotIndex = proposal.slots?.findIndex(s => s.post_id === focusPostId);
      if (slotIndex !== undefined && slotIndex >= 0) {
        setActiveSlot(`${proposal.id}-${slotIndex}`);
        onFocusHandled?.();
        setTimeout(() => activeSlotRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 150);
        return;
      }
    }
  }, [focusPostId, proposals]);

  const setSlotLoading = (key: SlotActionKey, val: boolean) =>
    setActionLoading(prev => ({ ...prev, [key]: val }));

  const handleProposalApprove = useCallback(async (proposalId: string) => {
    setSlotLoading(`${proposalId}-approve`, true);
    try {
      await apiClient.post(`/api/agent/proposals/${proposalId}/approve`);
      setProposals(prev => prev.filter(p => p.id !== proposalId));
      setActiveSlot(null);
      onProposalAction();
    } finally {
      setSlotLoading(`${proposalId}-approve`, false);
    }
  }, [onProposalAction]);

  const handleProposalReject = useCallback(async (proposalId: string) => {
    setSlotLoading(`${proposalId}-reject`, true);
    try {
      await apiClient.post(`/api/agent/proposals/${proposalId}/reject`);
      setProposals(prev => prev.filter(p => p.id !== proposalId));
      setActiveSlot(null);
      onProposalAction();
    } finally {
      setSlotLoading(`${proposalId}-reject`, false);
    }
  }, [onProposalAction]);

  const handleRegen = useCallback(async (proposalId: string, slotIndex: number) => {
    const key = `${proposalId}-${slotIndex}`;
    setSlotLoading(key + '-regen', true);
    try {
      const data = await apiClient.post<{ caption: string }>(
        `/api/agent/proposals/${proposalId}/slots/${slotIndex}/regenerate`
      );
      setSlotCaptions(prev => ({ ...prev, [key]: data.caption }));
      setProposals(prev => prev.map(p => {
        if (p.id !== proposalId) return p;
        return { ...p, slots: p.slots.map((s, i) => i === slotIndex ? { ...s, caption: data.caption } : s) };
      }));
    } catch {
      // Silent — user can retry Regenerate
    } finally {
      setSlotLoading(key + '-regen', false);
    }
  }, []);

  const handleSkip = useCallback(async (proposalId: string, slotIndex: number) => {
    const key = `${proposalId}-${slotIndex}-skip`;
    setSlotLoading(key, true);
    try {
      await apiClient.post(`/api/agent/proposals/${proposalId}/slots/${slotIndex}/skip`);
      setProposals(prev => prev.map(p => {
        if (p.id !== proposalId) return p;
        return { ...p, slots: p.slots.map((s, i) => i === slotIndex ? { ...s, post_id: undefined } : s) };
      }));
      setActiveSlot(null);
    } finally {
      setSlotLoading(key, false);
    }
  }, []);

  const handleTypeChange = useCallback(async (proposalId: string, slotIndex: number, post_type: string) => {
    const key = `${proposalId}-${slotIndex}-type`;
    setSlotLoading(key, true);
    setTypeMenuOpen(null);
    try {
      await apiClient.post(`/api/agent/proposals/${proposalId}/slots/${slotIndex}/type`, { post_type });
      setProposals(prev => prev.map(p => {
        if (p.id !== proposalId) return p;
        return { ...p, slots: p.slots.map((s, i) => i === slotIndex ? { ...s, post_type } : s) };
      }));
    } finally {
      setSlotLoading(key, false);
    }
  }, []);

  const handleHookSelect = useCallback(async (proposalId: string, slotIndex: number, hook: string) => {
    const key = `${proposalId}-${slotIndex}`;
    setSlotLoading(key + '-hook', true);
    try {
      const data = await apiClient.patch<{ caption: string }>(
        `/api/agent/proposals/${proposalId}/slots/${slotIndex}/hook`,
        { hook }
      );
      setSlotCaptions(prev => ({ ...prev, [key]: data.caption }));
      setProposals(prev => prev.map(p => {
        if (p.id !== proposalId) return p;
        return { ...p, slots: p.slots.map((s, i) => i === slotIndex ? { ...s, caption: data.caption } : s) };
      }));
    } catch {
      // Silent — the previous hook stays selected
    } finally {
      setSlotLoading(key + '-hook', false);
    }
  }, []);

  const handleSaveTime = useCallback(async (proposalId: string, slotIndex: number, slot: CalendarSlot, datetime: string) => {
    if (!slot.post_id || !datetime) return;
    const key = `${proposalId}-${slotIndex}-time`;
    setSlotLoading(key, true);
    try {
      const isoTime = new Date(datetime).toISOString();
      await apiClient.put(`/api/scheduler/reschedule/${slot.post_id}`, { new_scheduled_time: isoTime });
    } catch {
      // Silent — the visual update already reflects the input
    } finally {
      setSlotLoading(key, false);
    }
  }, []);

  const openImagePicker = useCallback(async (slotKey: string) => {
    if (!accountId) return;
    setImagePicking(slotKey);
    setImagePickLoading(true);
    try {
      const data = await apiClient.get<DriveImage[]>(`/api/drive/images?account_id=${accountId}`);
      setDriveImages(data);
    } catch {
      // Silent — picker shows the empty state
    } finally {
      setImagePickLoading(false);
    }
  }, [accountId]);

  const handleImageSelect = useCallback(async (proposalId: string, slotIndex: number, fileId: string) => {
    const key = `${proposalId}-${slotIndex}-img`;
    setSlotLoading(key, true);
    setImagePicking(null);
    try {
      await apiClient.patch(`/api/agent/proposals/${proposalId}/slots/${slotIndex}/image`, { drive_file_id: fileId });
      setProposals(prev => prev.map(p => {
        if (p.id !== proposalId) return p;
        return { ...p, slots: p.slots.map((s, i) => i === slotIndex ? { ...s, image_id: fileId, media_url: null } : s) };
      }));
    } finally {
      setSlotLoading(key, false);
    }
  }, []);

  const handleSlotReorder = useCallback(async (proposalId: string, fromDay: string, toDay: string) => {
    setProposals(prev => prev.map(p => {
      if (p.id !== proposalId) return p;
      const newSlots = p.slots.map(s => {
        if (s.day === fromDay) return { ...s, day: toDay };
        if (s.day === toDay) return { ...s, day: fromDay };
        return s;
      });
      return { ...p, slots: newSlots };
    }));
    try {
      await apiClient.patch(`/api/agent/proposals/${proposalId}/slots/reorder`, { from_day: fromDay, to_day: toDay });
      onProposalAction();
    } catch {
      // Silent — onProposalAction triggers a calendar re-fetch
    }
  }, [onProposalAction]);

  if (loading) {
    return (
      <div className="wpp-loading">
        <span className="wpp-spinner" />
        Loading proposals...
      </div>
    );
  }

  if (error) return <div className="wpp-container text-danger small">{error}</div>;
  if (proposals.length === 0) return null;

  return (
    <div className="wpp-container">
      <div className="wpp-section-label">
        <span className="wpp-pulse" />
        Pending AI Proposals
      </div>

      {proposals.map(proposal => (
        <div key={proposal.id} className="wpp-card">
          {/* Header */}
          <div className="wpp-header">
            <span className="wpp-week-label">Week of {proposal.week_start}</span>
            <div className="d-flex gap-2">
              <button
                onClick={() => handleProposalReject(proposal.id)}
                disabled={!!actionLoading[`${proposal.id}-reject`]}
                className="wpp-btn-reject"
              >
                Reject
              </button>
              <button
                onClick={() => handleProposalApprove(proposal.id)}
                disabled={!!actionLoading[`${proposal.id}-approve`]}
                className="wpp-btn-approve"
              >
                Approve all
              </button>
            </div>
          </div>

          {/* 7-day grid */}
          <div className="wpp-week-row">
            {WEEKDAYS.map(day => {
              const slotIndex = proposal.slots.findIndex((s: CalendarSlot) => s.day === day);
              const slot = slotIndex >= 0 ? proposal.slots[slotIndex] : undefined;
              const slotKey = `${proposal.id}-${slotIndex}`;
              const dayNum = getDayNumber(proposal.week_start, day);
              const isActive = activeSlot === slotKey && slot != null;
              const isSkipped = slot != null && slot.post_id == null;
              const ptype = slot?.post_type ?? 'post';

              let boxClass = 'wpp-day-box';
              if (slot && !isSkipped) boxClass += ' wpp-day-box--slot';
              if (isActive) boxClass += ' wpp-day-box--active';
              if (isSkipped) boxClass += ' wpp-day-box--skipped';
              if (
                dragOverKey === `${proposal.id}:${day}` &&
                dragging?.proposalId === proposal.id &&
                dragging.day !== day
              ) boxClass += ' wpp-day-box--drag-over';

              return (
                <div
                  key={day}
                  className={boxClass}
                  onClick={() => slot && !isSkipped && setActiveSlot(isActive ? null : slotKey)}
                  draggable={slot != null && !isSkipped}
                  onDragStart={(e) => {
                    if (!slot || isSkipped) return;
                    e.dataTransfer.effectAllowed = 'move';
                    setDragging({ proposalId: proposal.id, day });
                  }}
                  onDragEnd={() => { setDragging(null); setDragOverKey(null); }}
                  onDragOver={(e) => {
                    if (dragging && dragging.proposalId === proposal.id && dragging.day !== day) {
                      e.preventDefault();
                      setDragOverKey(`${proposal.id}:${day}`);
                    }
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    if (!dragging || dragging.proposalId !== proposal.id) return;
                    handleSlotReorder(proposal.id, dragging.day, day);
                    setDragging(null);
                    setDragOverKey(null);
                  }}
                >
                  <div className="wpp-day-header">
                    <span className="wpp-day-label">{WEEKDAY_LABELS[day]}</span>
                    <span className="wpp-day-number">{dayNum}</span>
                  </div>

                  {slot && !isSkipped ? (
                    <div className="wpp-day-content">
                      {slotImageSrc(slot, token) && (
                        <img
                          src={slotImageSrc(slot, token) ?? undefined}
                          alt={slot.theme ?? ''}
                          className="wpp-day-thumb"
                          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                        />
                      )}
                      <span className={`wpp-badge wpp-badge--${ptype}`}>
                        {slotBadgeLabel(slot)}
                      </span>
                    </div>
                  ) : (
                    <div className="wpp-day-empty">—</div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Expanded detail panel */}
          {activeSlot && activeSlot.startsWith(proposal.id) && (() => {
            const idx = parseInt(activeSlot.split('-').pop() ?? '-1', 10);
            if (idx < 0 || idx >= proposal.slots.length) return null;
            const slot = proposal.slots[idx];
            const caption = slotCaptions[activeSlot] ?? slot.caption;
            const ptype = slot.post_type ?? 'post';
            const slotTimeKey = `${proposal.id}-${idx}`;
            const defaultDt = getDefaultDatetime(proposal.week_start, slot.day);
            const currentDt = slotTimes[slotTimeKey] ?? defaultDt;

            return (
              <div className="wpp-detail-panel" ref={activeSlotRef}>
                {/* Image zone */}
                <div className="wpp-detail-img-wrap">
                  {slotImageSrc(slot, token) && (
                    <img
                      src={slotImageSrc(slot, token) ?? undefined}
                      alt={slot.theme ?? ''}
                      className="wpp-detail-thumb"
                      onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                    />
                  )}
                  <button
                    className="wpp-action-btn wpp-action-btn--img"
                    onClick={() => openImagePicker(activeSlot)}
                    disabled={!!actionLoading[slotTimeKey + '-img']}
                  >
                    Change image
                  </button>
                </div>

                {/* Image picker overlay */}
                {imagePicking === activeSlot && (
                  <div className="wpp-img-picker">
                    <div className="wpp-img-picker-header">
                      <span>Select an image</span>
                      <button className="wpp-img-picker-close" onClick={() => setImagePicking(null)}>✕</button>
                    </div>
                    {imagePickLoading ? (
                      <div className="wpp-img-picker-loading"><span className="wpp-spinner" /></div>
                    ) : driveImages.length === 0 ? (
                      <p className="wpp-img-picker-empty">No images found in Drive</p>
                    ) : (
                      <div className="wpp-img-picker-grid">
                        {driveImages.map(img => (
                          <button
                            key={img.id}
                            className="wpp-img-picker-item"
                            onClick={() => handleImageSelect(proposal.id, idx, img.id)}
                            title={img.name}
                          >
                            <img
                              src={apiClient.getUrl(`/api/drive/files/${img.id}/image?token=${token}`)}
                              alt={img.name}
                              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                            />
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div className="wpp-detail-body">
                  <div className="wpp-detail-meta">
                    <span className="wpp-detail-day">{slot.day}</span>
                    <span className={`wpp-badge wpp-badge--${ptype}`}>{slotBadgeLabel(slot)}</span>
                    {slot.theme && <span className="wpp-detail-theme">{slot.theme}</span>}
                  </div>
                  <p className="wpp-detail-caption">{caption}</p>

                  {ptype === 'reel' && (slot.hook_candidates?.length ?? 0) > 0 && (
                    <div className="wpp-hooks">
                      <span className="wpp-hooks-label">Hook candidates</span>
                      {slot.hook_candidates!.map(hook => {
                        const selected = caption.split('\n', 1)[0] === hook;
                        return (
                          <button
                            key={hook}
                            type="button"
                            className={`wpp-hook-option${selected ? ' wpp-hook-option--selected' : ''}`}
                            aria-pressed={selected}
                            onClick={() => !selected && handleHookSelect(proposal.id, idx, hook)}
                            disabled={!!actionLoading[activeSlot + '-hook']}
                          >
                            {hook}
                          </button>
                        );
                      })}
                    </div>
                  )}

                  {/* Date/time input */}
                  <div className="wpp-time-row">
                    <label className="wpp-time-label">Schedule for:</label>
                    <input
                      type="datetime-local"
                      className="wpp-time-input"
                      value={currentDt}
                      onChange={e => setSlotTimes(prev => ({ ...prev, [slotTimeKey]: e.target.value }))}
                    />
                    <button
                      className="wpp-action-btn"
                      onClick={() => handleSaveTime(proposal.id, idx, slot, currentDt)}
                      disabled={!!actionLoading[slotTimeKey + '-time']}
                    >
                      {actionLoading[slotTimeKey + '-time'] ? '...' : 'Save time'}
                    </button>
                  </div>

                  <div className="wpp-actions">
                    <button
                      onClick={() => handleRegen(proposal.id, idx)}
                      disabled={!!actionLoading[activeSlot + '-regen']}
                      className="wpp-action-btn"
                    >
                      {actionLoading[activeSlot + '-regen'] ? '...' : 'Regenerate'}
                    </button>

                    <div className="wpp-type-dropdown">
                      <button
                        onClick={() => setTypeMenuOpen(typeMenuOpen === activeSlot ? null : activeSlot)}
                        disabled={!!actionLoading[activeSlot + '-type']}
                        className="wpp-action-btn"
                      >
                        Type
                      </button>
                      {typeMenuOpen === activeSlot && (
                        <div className="wpp-type-menu">
                          {Object.entries(POST_TYPE_LABELS).map(([val, label]) => (
                            <button key={val} onClick={() => handleTypeChange(proposal.id, idx, val)}>
                              {label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => handleSkip(proposal.id, idx)}
                      disabled={!!actionLoading[activeSlot + '-skip']}
                      className="wpp-action-btn wpp-action-btn--danger"
                    >
                      Skip
                    </button>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      ))}
    </div>
  );
};

export default WeeklyProposalPanel;
