export interface Post {
  id: number;
  user_id: string;
  content: string;
  media_url: string | null;
  post_type: string;
  status: string;
  scheduled_at: string | null;
  created_at: string;
  publication_date?: string | null;
  is_ai_generated?: boolean | null;
  drive_file_id?: string | null;
  instagram_account_id?: number | null;
}

export interface InstagramAccount {
  id: number;
  username: string | null;
  account_name: string | null;
  profile_picture_url?: string | null;
  followers_count?: number | null;
  expires_at?: string | null;
  is_active?: boolean;
  telegram_chat_id?: string | null;
  drive_folder_id?: string | null;
  account_type?: string;
  sector?: string;
  purpose?: string;
  target_audience?: string;
  style_guide?: string;
  default_tone?: string;
  default_language?: string;
  posting_frequency?: string;
  best_times?: string[];
  content_pillars?: string[];
  hashtag_strategy?: string;
  last_agent_sync?: string | null;
}

export interface CalendarSlot {
  day: string;
  post_id?: number | null;
  image_id?: string | null;
  theme: string;
  caption: string;
  post_type?: string;
}

export interface ContentProposal {
  id: string;
  account_id: string;
  week_start: string;
  slots: CalendarSlot[];
  status: 'pending_approval' | 'approved' | 'rejected';
  created_at?: string;
}
