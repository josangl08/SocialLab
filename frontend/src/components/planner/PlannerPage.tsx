import React, { useState, useEffect, useCallback } from 'react';
import CalendarView from '../calendar/CalendarView';
import PostList from '../posts/PostList';
import CreatePost from '../posts/CreatePost';
import EditPostForm from '../posts/EditPostForm';
import './PlannerPage.css';

interface EditablePost {
  id: number;
  user_id: string;
  content: string;
  media_url: string | null;
  post_type: string;
  status: string;
  scheduled_at: string | null;
  created_at: string;
  publication_date?: string | null;
}

const PlannerPage: React.FC = () => {
  const [view, setView]               = useState<'calendar' | 'list'>('calendar');
  const [showDrawer, setShowDrawer]   = useState(false);
  const [drawerDate, setDrawerDate]   = useState('');
  const [editingPost, setEditingPost] = useState<EditablePost | null>(null);
  const [calendarSignal, setCalendarSignal] = useState(0);

  const openDrawer = useCallback((date?: string) => {
    setEditingPost(null);
    setDrawerDate(date ?? '');
    setShowDrawer(true);
  }, []);

  const openEditDrawer = useCallback((post: EditablePost) => {
    setEditingPost(post);
    setShowDrawer(true);
  }, []);

  const closeDrawer = useCallback(() => {
    setShowDrawer(false);
    setEditingPost(null);
  }, []);

  useEffect(() => {
    if (!showDrawer) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeDrawer(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [showDrawer, closeDrawer]);

  useEffect(() => {
    document.body.style.overflow = showDrawer ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [showDrawer]);

  return (
    <div className="planner-page">
      {/* ── Tab bar ─────────────────────────── */}
      <div className="planner-header">
        <div className="planner-tabs">
          <button
            className={`planner-tab${view === 'calendar' ? ' active' : ''}`}
            onClick={() => setView('calendar')}
          >
            <i className="bi bi-calendar-event"></i>
            Calendario
          </button>
          <button
            className={`planner-tab${view === 'list' ? ' active' : ''}`}
            onClick={() => setView('list')}
          >
            <i className="bi bi-grid-3x3"></i>
            Publicaciones
          </button>
        </div>
        <button className="planner-new-btn" onClick={() => openDrawer()}>
          <i className="bi bi-plus-lg"></i>
          Nueva Publicación
        </button>
      </div>

      {/* ── Content ─────────────────────────── */}
      <div className="planner-content">
        {view === 'calendar'
          ? <CalendarView
              onNewPost={openDrawer}
              onEdit={openEditDrawer}
              refreshSignal={calendarSignal}
            />
          : <PostList />
        }
      </div>

      {/* ── Create / Edit drawer ─────────────── */}
      {showDrawer && (
        <div className="planner-drawer-backdrop" onClick={closeDrawer}>
          <div className="planner-drawer" onClick={e => e.stopPropagation()}>
            <div className="planner-drawer-header">
              <span className="planner-drawer-title">
                <i className={`bi ${editingPost ? 'bi-pencil-square' : 'bi-plus-circle'}`}></i>
                {editingPost ? 'Editar publicación' : 'Nueva Publicación'}
              </span>
              <button className="planner-drawer-close" onClick={closeDrawer} aria-label="Cerrar">
                <i className="bi bi-x-lg"></i>
              </button>
            </div>
            <div className="planner-drawer-body">
              {editingPost ? (
                <EditPostForm
                  post={editingPost as any}
                  onSave={() => { closeDrawer(); setCalendarSignal(k => k + 1); }}
                  onCancel={closeDrawer}
                />
              ) : (
                <CreatePost
                  key={drawerDate}
                  initialDate={drawerDate || undefined}
                  onPostCreated={closeDrawer}
                  onCancel={closeDrawer}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlannerPage;
