import requests, uuid

BASE = "http://localhost:8000"

# Test 1: Upload without auth
files = {"file": ("test.txt", b"Hello, this is a test file about Python!", "text/plain")}
r = requests.post(BASE + "/file/upload", files=files, timeout=10)
print("Test 1 (no auth):", r.status_code, r.json().get("message", r.text[:100]))

# Register
username = "up_" + uuid.uuid4().hex[:4]
r = requests.post(BASE + "/auth/register", json={"username": username, "password": "test123456"}, timeout=10)
token = r.json().get("access_token", "") or r.json().get("token", "")
h = {"Authorization": "Bearer " + token}

# Test 2: TXT
files = {"file": ("doc.txt", b"This is a document about machine learning.", "text/plain")}
r = requests.post(BASE + "/file/upload", files=files, headers=h, timeout=10)
print("Test 2 (TXT):", r.status_code, r.json().get("message", r.text[:100]))

# Test 3: Python file
files = {"file": ("main.py", b"print('hello world')", "text/plain")}
r = requests.post(BASE + "/file/upload", files=files, headers=h, timeout=10)
print("Test 3 (PY):", r.status_code, r.json().get("message", r.text[:100]))

# Test 4: Unsupported format
files = {"file": ("image.png", b"fake png data", "image/png")}
r = requests.post(BASE + "/file/upload", files=files, headers=h, timeout=10)
print("Test 4 (unsupported):", r.status_code, r.text[:100])

# Test 5: Empty file
files = {"file": ("empty.txt", b"", "text/plain")}
r = requests.post(BASE + "/file/upload", files=files, headers=h, timeout=10)
print("Test 5 (empty file):", r.status_code, r.text[:100])

# Test 6: No file field
r = requests.post(BASE + "/file/upload", headers=h, timeout=10)
print("Test 6 (no file):", r.status_code, r.text[:100])

# Test 7: Large file (11MB) - should be rejected
files = {"file": ("large.txt", b"x" * (11 * 1024 * 1024), "text/plain")}
r = requests.post(BASE + "/file/upload", files=files, headers=h, timeout=30)
print("Test 7 (too large):", r.status_code, r.text[:100])

print("=== UPLOAD TESTS DONE ===")