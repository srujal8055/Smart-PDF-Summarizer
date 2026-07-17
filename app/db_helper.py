import json
from typing import List, Dict, Any, Optional
from database.db_manager import get_db_connection, init_database

# Ensure database is initialized when helper is loaded
try:
    init_database()
except Exception:
    pass

def save_summary_log(
    filename: str,
    file_size: int,
    page_count: int,
    summary_type: str,
    final_summary: str,
    intermediate_summaries: List[str]
) -> int:
    """
    Saves a new summarization report to the SQLite database.
    
    Returns:
        The ID of the newly inserted row.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Serialize intermediate summaries to JSON string
    serialized_intermediates = json.dumps(intermediate_summaries)
    
    cursor.execute("""
        INSERT INTO summaries (filename, file_size, page_count, summary_type, final_summary, intermediate_summaries)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (filename, file_size, page_count, summary_type, final_summary, serialized_intermediates))
    
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def get_all_summaries_history() -> List[Dict[str, Any]]:
    """
    Retrieves metadata for all saved summaries.
    Excludes the detailed summaries for lightweight retrieval.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, filename, file_size, page_count, summary_type, created_at
        FROM summaries
        ORDER BY created_at DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_summary_by_id(summary_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a detailed summary record including text by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, filename, file_size, page_count, summary_type, final_summary, intermediate_summaries, created_at
        FROM summaries
        WHERE id = ?
    """, (summary_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        record = dict(row)
        # Deserialize JSON back into list
        try:
            record["intermediate_summaries"] = json.loads(record["intermediate_summaries"])
        except Exception:
            record["intermediate_summaries"] = []
        return record
    return None

def delete_summary_by_id(summary_id: int) -> bool:
    """Deletes a summary record by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM summaries WHERE id = ?", (summary_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
