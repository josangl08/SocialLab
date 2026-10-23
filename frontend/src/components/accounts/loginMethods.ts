import type { LoginType } from '../../types';

export interface LoginFeature {
  label: string;
  available: boolean;
}

export interface LoginMethodInfo {
  type: LoginType;
  name: string;
  icon: string;
  tagline: string;
  features: LoginFeature[];
  requirements: string[];
  /** Resumen corto de lo que no incluye, para la tarjeta de la cuenta. */
  limitation: string;
}

// Única fuente de lo que aporta cada login: la usan el selector y las tarjetas de cuenta.
// Instagram no entrega por la API las Stories de mejores amigos, con ningún login
export const LOGIN_FOOTNOTE = 'Las Stories de mejores amigos no se importan con ninguna de las dos opciones.';

export const LOGIN_METHODS: Record<LoginType, LoginMethodInfo> = {
  instagram: {
    type: 'instagram',
    name: 'Instagram',
    icon: 'bi-instagram',
    tagline: 'Más simple',
    features: [
      { label: 'Publicar, métricas de posts y reels, comentarios', available: true },
      { label: 'Importar Stories y sus métricas', available: true },
      { label: 'Sin reconexiones: el acceso se renueva solo', available: true },
      { label: 'Importar colaboraciones', available: false },
    ],
    requirements: ['Cuenta profesional de Instagram (empresa o creador)'],
    limitation: 'No importa colaboraciones',
  },
  facebook: {
    type: 'facebook',
    name: 'Facebook',
    icon: 'bi-facebook',
    tagline: 'Más completo',
    features: [
      { label: 'Publicar, métricas de posts y reels, comentarios', available: true },
      { label: 'Importar Stories y sus métricas', available: true },
      { label: 'Importar colaboraciones', available: true },
      { label: 'Reconectar cada 90 días (te avisamos por Telegram)', available: false },
    ],
    requirements: [
      'Cuenta profesional de Instagram vinculada a una Página de Facebook',
      'Ser administrador de esa Página',
    ],
    limitation: 'Hay que reconectar cada 90 días',
  },
};
