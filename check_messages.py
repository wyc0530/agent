"""检查数据库中的对话消息数据"""
import mysql.connector
import os
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

# 按对话统计各角色消息数
c.execute("""
    SELECT cm.conversation_id, cm.role, COUNT(*) as cnt,
           LEFT(c.title, 30) as title
    FROM conversation_messages cm
    JOIN conversations c ON cm.conversation_id = c.id
    GROUP BY cm.conversation_id, cm.role, c.title
    ORDER BY cm.conversation_id, cm.role
""")
print("=== 按对话/角色统计消息数 ===")
for r in c.fetchall():
    print(f"  conv={r['conversation_id'][:20]}... title={r['title']} role={r['role']:10s} count={r['cnt']}")

# 查看最近几个对话的消息详情
c.execute("""
    SELECT cm.conversation_id, cm.role, LEFT(cm.content, 60) as preview,
           cm.id, c.title
    FROM conversation_messages cm
    JOIN conversations c ON cm.conversation_id = c.id
    ORDER BY cm.id DESC LIMIT 20
""")
print("\n=== 最近20条消息 ===")
for r in c.fetchall():
    print(f"  id={r['id']} conv={r['conversation_id'][:20]}... role={r['role']:10s} title={r['title'][:25]} preview={r['preview']}")

# 查找有完整对话的用户
c.execute("""
    SELECT c.id as conv_id, c.user_id, c.title, u.username
    FROM conversations c
    JOIN users u ON c.user_id = u.id
    WHERE c.id IN (
        SELECT conversation_id FROM conversation_messages
        WHERE role = 'assistant'
        GROUP BY conversation_id
    )
    LIMIT 5
""")
print("\n=== 有 assistant 消息的对话 ===")
for r in c.fetchall():
    print(f"  username={r['username']} conv_id={r['conv_id'][:20]}... title={r['title']}")

c.close()
conn.close()