from .connection import Database

class Repository:
    @staticmethod
    def get_document_by_slug(slug: str):
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, slug, title, source_hash, page_count, root_path FROM documents WHERE slug = %s", (slug,))
                return cur.fetchone()

    @staticmethod
    def insert_document(slug: str, title: str, source_hash: str, page_count: int, root_path: str) -> int:
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO documents (slug, title, source_hash, page_count, root_path)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (slug, title, source_hash, page_count, root_path))
                doc_id = cur.fetchone()[0]
                conn.commit()
                return doc_id
