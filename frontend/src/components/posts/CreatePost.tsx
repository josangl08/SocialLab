import React, { useState, FormEvent } from 'react';
import { useAuth } from '../../context/AuthContext';
import './CreatePost.css';

interface CreatePostProps {
  onPostCreated: () => void;
}

const CreatePost: React.FC<CreatePostProps> = ({ onPostCreated }) => {
  const { token } = useAuth();
  const [content, setContent] = useState<string>('');
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [mediaPreview, setMediaPreview] = useState<string | null>(null);
  const [postType, setPostType] = useState<string>('post');
  const [status, setStatus] = useState<string>('draft');
  const [scheduledAt, setScheduledAt] = useState<string>('');
  const [message, setMessage] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  // --- Nuevos estados para la funcionalidad de IA ---
  const [aiTopic, setAiTopic] = useState<string>('');
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [aiMessage, setAiMessage] = useState<string>('');


  const formatErrorMessage = (errorData: any) => {
    if (errorData && Array.isArray(errorData.detail)) {
      return errorData.detail.map((err: any) => err.msg || err.message || JSON.stringify(err)).join('; ');
    } else if (errorData && errorData.detail) {
      return errorData.detail;
    } else if (errorData && errorData.message) {
      return errorData.message;
    }
    return 'Error desconocido';
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files ? e.target.files[0] : null;
    setMediaFile(file);
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setMediaPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    } else {
      setMediaPreview(null);
    }
  };

  // --- Nueva función para generar contenido con IA ---
  const handleGenerateAIContent = async () => {
    if (!aiTopic) {
      setAiMessage('Por favor, introduce un tema para la IA.');
      return;
    }
    setAiLoading(true);
    setAiMessage('');
    setMessage('');

    try {
      const response = await fetch('http://localhost:8000/ai/generate-post-content', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ topic: aiTopic }),
      });

      if (response.ok) {
        const data = await response.json();
        setContent(data.generated_text); // Actualizar el contenido principal
        setAiMessage('Contenido generado exitosamente.');
      } else {
        const errorData = await response.json();
        setAiMessage('Error al generar contenido: ' + formatErrorMessage(errorData));
      }
    } catch (error: any) {
      setAiMessage('Error de red o servidor: ' + error.message);
    } finally {
      setAiLoading(false);
    }
  };


  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage('');
    setLoading(true);

    if (!token) {
      setMessage('Error: No hay token de autenticación.');
      setLoading(false);
      return;
    }

    if (!mediaFile) {
      setMessage('Error: Un archivo multimedia es obligatorio para publicaciones de Instagram.');
      setLoading(false);
      return;
    }

    const formData = new FormData();
    formData.append('content', content);
    formData.append('post_type', postType);
    formData.append('status', status);
    if (scheduledAt) {
      formData.append('scheduled_at', new Date(scheduledAt).toISOString());
    }
    formData.append('media_file', mediaFile);

    try {
      const response = await fetch('http://localhost:8000/posts', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (response.ok) {
        setMessage('Publicación creada exitosamente!');
        setContent('');
        setAiTopic('');
        setMediaFile(null);
        setMediaPreview(null);
        (event.target as HTMLFormElement).reset();
        setPostType('post');
        setStatus('draft');
        setScheduledAt('');
        onPostCreated();
      } else {
        const errorData = await response.json();
        setMessage('Error al crear publicación: ' + formatErrorMessage(errorData));
      }
    } catch (error: any) {
      setMessage('Error de red o servidor: ' + error.message);
      console.error('Error de red o servidor:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-4 p-4 bg-light rounded shadow-sm create-post-card">
      <h3 className="mb-4 text-primary">Crear Nueva Publicación</h3>
      
      {/* --- Sección de IA --- */}
      <div className="p-3 mb-4 bg-white rounded border">
        <h5 className="text-secondary">Asistente de Contenido IA</h5>
        <div className="mb-2">
          <textarea
            className="form-control"
            placeholder="Escribe un tema o idea para tu publicación (ej: 'lanzamiento de nuevas zapatillas ecológicas')..."
            value={aiTopic}
            onChange={(e) => setAiTopic(e.target.value)}
            rows={2}
            disabled={aiLoading || loading}
          />
        </div>
        <button 
          type="button" 
          className="btn btn-outline-primary w-100" 
          onClick={handleGenerateAIContent} 
          disabled={aiLoading || loading}
        >
          {aiLoading ? (
            <><span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generando...</>
          ) : (
            '✨ Generar texto con IA'
          )}
        </button>
        {aiMessage && (
          <p className={`mt-2 text-center small ${aiMessage.startsWith('Error') ? 'text-danger' : 'text-success'}`}>
            {aiMessage}
          </p>
        )}
      </div>
      {/* --- Fin Sección de IA --- */}

      <form onSubmit={handleSubmit}>
        <div className="mb-3">
          <label htmlFor="content" className="form-label">Contenido de la Publicación</label>
          <textarea
            id="content"
            className="form-control"
            placeholder="El texto generado por la IA aparecerá aquí..."
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={5}
            required
            disabled={loading}
          />
        </div>
        <div className="mb-3">
          <label htmlFor="mediaFile" className="form-label">Subir Imagen/Video <span className="text-danger">*</span></label>
          <input
            type="file"
            className="form-control"
            id="mediaFile"
            onChange={handleFileChange}
            required
            disabled={loading}
            accept="image/*,video/*"
          />
          {mediaPreview && (
            <div className="mt-2 text-center">
              {mediaPreview.startsWith('data:image') ? (
                <img src={mediaPreview} alt="Previsualización" className="img-fluid rounded" style={{ maxHeight: '200px' }} />
              ) : (
                <video src={mediaPreview} controls className="img-fluid rounded" style={{ maxHeight: '200px' }} />
              )}
            </div>
          )}
        </div>
        <div className="row">
          <div className="col-md-6 mb-3">
            <label htmlFor="postType" className="form-label">Tipo de Publicación</label>
            <select
              className="form-select"
              id="postType"
              value={postType}
              onChange={(e) => setPostType(e.target.value)}
              disabled={loading}
            >
              <option value="post">Post</option>
              <option value="reel">Reel</option>
              <option value="story">Story</option>
            </select>
          </div>
          <div className="col-md-6 mb-3">
            <label htmlFor="status" className="form-label">Estado</label>
            <select
              className="form-select"
              id="status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              disabled={loading}
            >
              <option value="draft">Borrador</option>
              <option value="scheduled">Programado</option>
              <option value="published">Publicado</option>
            </select>
          </div>
        </div>
        <div className="mb-3">
          <label htmlFor="scheduledAt" className="form-label">Programar para (opcional)</label>
          <input
            type="datetime-local"
            className="form-control"
            id="scheduledAt"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            disabled={loading}
          />
        </div>
        <button type="submit" className="btn btn-primary w-100" disabled={loading}>
            {loading ? (
              <><span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Creando...</>
            ) : (
              'Crear Publicación'
            )}
        </button>
      </form>
      {message && (
        <p className={`mt-3 text-center ${message.startsWith('Error') ? 'text-danger' : 'text-success'}`}>
          {message}
        </p>
      )}
    </div>
  );
};

export default CreatePost;

