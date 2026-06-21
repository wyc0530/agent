"""修复缺少 assistant 消息的对话"""
import mysql.connector, os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
conn = mysql.connector.connect(
    host=os.getenv('MYSQL_HOST', 'localhost'),
    port=int(os.getenv('MYSQL_PORT', 3306)),
    user=os.getenv('MYSQL_USER', 'root'),
    password=os.getenv('MYSQL_PASSWORD', ''),
    database=os.getenv('MYSQL_DATABASE', 'users'),
    charset='utf8mb4'
)
c = conn.cursor(dictionary=True)

# Find conversations with only user messages (no assistant messages)
c.execute("""
    SELECT c.id, c.title, c.user_id
    FROM conversations c
    WHERE c.id IN (
        SELECT conversation_id FROM conversation_messages WHERE role = 'user'
    )
    AND c.id NOT IN (
        SELECT conversation_id FROM conversation_messages WHERE role = 'assistant'
    )
""")
broken = c.fetchall()
print(f"Found {len(broken)} broken conversations")
for conv in broken:
    print(f"  Fixing: {conv['id'][:20]}... title={conv['title']}")
    now = datetime.now().isoformat()
    c.execute(
        "INSERT INTO conversation_messages (conversation_id, role, content, created_at) VALUES (%s, %s, %s, %s)",
        (conv['id'], 'assistant', '[系统提示] 响应生成失败，请稍后重试。', now)
    )
    c.execute("UPDATE conversations SET updated_at = %s WHERE id = %s", (now, conv['id']))
    conn.commit()
    print(f"    Fixed!")

if not broken:
    print("No broken conversations found.")

c.close()
conn.close()