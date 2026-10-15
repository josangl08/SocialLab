"""
Trigger `posts_invalidate_thumbnail` contra la base de datos real (persistent-thumbnails, AD-2, AD-8).

Cada caso trabaja sobre un post existente dentro de una transacción que siempre se revierte:
no deja cambios. Se salta si no hay `DATABASE_URL`.
"""

import os
from typing import Iterator

import pytest

psycopg2 = pytest.importorskip("psycopg2")

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="Requiere DATABASE_URL")

BASE = "https://p.supabase.co/storage/v1/object/public/thumbnails/u/1/k"
IG_URL = "https://scontent.cdninstagram.com/v/t51/123_n.jpg"


@pytest.fixture
def cursor() -> Iterator:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM posts ORDER BY id LIMIT 1 FOR UPDATE")
        row = cur.fetchone()
        if not row:
            pytest.skip("No hay posts en la base de datos")
        # Dos pasos: cambiar la imagen en el mismo UPDATE anularía la base
        cur.execute(
            "UPDATE posts SET media_url = %s, drive_file_id = 'drive-1' WHERE id = %s",
            (f"{IG_URL}?oh=a&oe=1", row[0]),
        )
        cur.execute("UPDATE posts SET thumbnail_url_base = %s WHERE id = %s", (BASE, row[0]))
        yield cur, row[0]
    finally:
        conn.rollback()
        conn.close()


def _base_after(cursor, assignment: str, params: tuple = ()) -> str | None:
    cur, post_id = cursor
    cur.execute(f"UPDATE posts SET {assignment} WHERE id = %s", (*params, post_id))
    cur.execute("SELECT thumbnail_url_base FROM posts WHERE id = %s", (post_id,))
    return cur.fetchone()[0]


def test_new_image_path_invalidates_thumbnail(cursor):
    assert _base_after(cursor, "media_url = %s", ("https://scontent.cdninstagram.com/v/t51/999_n.jpg",)) is None


def test_new_drive_file_invalidates_thumbnail(cursor):
    assert _base_after(cursor, "drive_file_id = 'drive-2'") is None


def test_removing_the_image_invalidates_thumbnail(cursor):
    assert _base_after(cursor, "media_url = NULL") is None


def test_refreshed_instagram_signature_keeps_thumbnail(cursor):
    assert _base_after(cursor, "media_url = %s", (f"{IG_URL}?oh=b&oe=2",)) == BASE


def test_other_columns_keep_thumbnail(cursor):
    assert _base_after(cursor, "content = content || ' '") == BASE
